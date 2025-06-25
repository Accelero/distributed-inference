import asyncio
import grpc
import numpy as np
import onnxruntime as ort
from transformers import AutoTokenizer
from proto import inference_pb2
from proto import inference_pb2_grpc
import os
from custom_logging import logger

MODEL_PATH = "model/all-MiniLM-L6-v2.onnx"
TOKENIZER_PATH = "model/tokenizer"

tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_PATH, local_files_only=True)
session = ort.InferenceSession(MODEL_PATH, providers=["CPUExecutionProvider"])

def mean_pooling(token_embeddings, attention_mask):
    input_mask_expanded = attention_mask[:, :, None]
    return (token_embeddings * input_mask_expanded).sum(1) / input_mask_expanded.sum(1)

def normalize(embeddings):
    return embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)

class WorkerServicer(inference_pb2_grpc.WorkerServicer):
    def __init__(self):
        super().__init__()
        self.worker_id = os.uname().nodename

    async def Infer(self, request, context):
        texts = list(request.input_data)  # tokenizer expects native Python list

        if not texts or not all(isinstance(t, str) for t in texts):
            logger.error(f"Invalid input detected: {texts}")
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("All input_data elements must be strings.")
            return inference_pb2.InferResponse(
                worker_id=self.worker_id,
                success=False,
                error_message="Invalid input: input_data must be a list of strings.",
                request_ids=[],
                embeddings=[]
            )

        try:
            tokenized = tokenizer(texts, padding=True, truncation=True, return_tensors="np")
            ort_inputs = {
                "input_ids": tokenized["input_ids"],
                "attention_mask": tokenized["attention_mask"],
                "token_type_ids": tokenized["token_type_ids"]
            }
            outputs = session.run(None, ort_inputs)[0]
            pooled = mean_pooling(outputs, tokenized["attention_mask"])
            embeddings = normalize(pooled)

            embedding_messages = [
                inference_pb2.Embedding(vector=emb.tolist())
                for emb in embeddings
            ]

            return inference_pb2.InferResponse(
                worker_id=self.worker_id,
                success=True,
                error_message="",
                request_ids=request.request_ids,
                embeddings=embedding_messages
            )
        except Exception as e:
            logger.exception("Error during inference")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return inference_pb2.InferResponse(
                worker_id=self.worker_id,
                success=False,
                error_message=str(e),
                request_ids=[],
                embeddings=[]
            )

    async def Heartbeat(self, request, context):
        return inference_pb2.HeartbeatResponse(alive=True)

async def serve():
    server = grpc.aio.server()
    inference_pb2_grpc.add_WorkerServicer_to_server(WorkerServicer(), server)
    server.add_insecure_port("0.0.0.0:50051")
    await server.start()
    logger.info("Async Worker gRPC server started on port 50051")
    await server.wait_for_termination()

if __name__ == "__main__":
    asyncio.run(serve())
