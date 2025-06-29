import asyncio
import logging
import os

import custom_logging
import grpc
import numpy as np
import onnxruntime as ort
from prometheus_client import start_http_server
from proto.private_pb2 import (HeartbeatRequest, HeartbeatResponse,
                               InferRequest, InferResponse, StatusCode)
from proto.private_pb2_grpc import WorkerServicer, add_WorkerServicer_to_server
from proto.public_pb2 import Embedding, ReturnCode
from transformers import AutoTokenizer

MODEL_PATH = "model/all-MiniLM-L6-v2.onnx"
TOKENIZER_PATH = "model/tokenizer"

tokenizer = AutoTokenizer.from_pretrained(
    TOKENIZER_PATH, local_files_only=True)
session = ort.InferenceSession(MODEL_PATH, providers=["CPUExecutionProvider"])


def mean_pooling(token_embeddings, attention_mask):
    input_mask_expanded = attention_mask[:, :, None]
    return (token_embeddings * input_mask_expanded).sum(1) / input_mask_expanded.sum(1)


def normalize(embeddings):
    return embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)


class WorkerServicerImpl(WorkerServicer):
    def __init__(self):
        super().__init__()
        self.worker_id = os.environ.get("HOSTNAME", os.uname().nodename)

    async def Infer(self, request, context):
        texts = list(request.input_data)
        logging.info(f"Received Infer request: {len(texts)} texts")

        if not texts or not all(isinstance(t, str) for t in texts):
            logging.error(f"Invalid input detected: {texts}")
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("All input_data elements must be strings.")
            return InferResponse(
                worker_id=self.worker_id,
                code=ReturnCode.INPUT_ERROR,
                return_msg="Invalid input: input_data must be a list of strings.",
                ids=[],
                embeddings=[]
            )

        try:
            tokenized = tokenizer(texts, padding=True,
                                  truncation=True, return_tensors="np")
            ort_inputs = {
                "input_ids": tokenized["input_ids"],
                "attention_mask": tokenized["attention_mask"],
                "token_type_ids": tokenized["token_type_ids"]
            }
            outputs = session.run(None, ort_inputs)[0]
            pooled = mean_pooling(outputs, tokenized["attention_mask"])
            embeddings = normalize(pooled)

            embedding_messages = [
                Embedding(vector=emb.tolist())
                for emb in embeddings
            ]

            logging.info(f"Successfully processed Infer request: {len(texts)} texts.")
            return InferResponse(
                worker_id=self.worker_id,
                code=ReturnCode.OK,
                return_msg="",
                ids=request.ids,
                embeddings=embedding_messages
            )
        except Exception as e:
            logging.exception("Error during inference")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return InferResponse(
                worker_id=self.worker_id,
                code=ReturnCode.SERVICE_ERROR,
                return_msg=str(e),
                ids=[],
                embeddings=[]
            )

    async def Heartbeat(self, request, context):
        return HeartbeatResponse(status=StatusCode.STATUS_OK)


async def serve():
    start_http_server(8000)  # Expose metrics on port 8000
    server = grpc.aio.server()
    add_WorkerServicer_to_server(WorkerServicerImpl(), server)
    server.add_insecure_port("0.0.0.0:50051")
    await server.start()
    logging.info("Async Worker gRPC server started on port 50051")
    await server.wait_for_termination()

if __name__ == "__main__":
    # Prometheus server is already started above
    asyncio.run(serve())
