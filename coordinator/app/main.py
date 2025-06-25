import asyncio
import grpc
from grpc.experimental import aio
from proto import inference_pb2
from proto import inference_pb2_grpc
import itertools
from custom_logging import logger
import logging


MAX_BATCH_SIZE = 8
MAX_WAIT = 0.01  # seconds
WORKER_ADDRESSES = ["worker:50051"]

request_queue = asyncio.Queue()
round_robin_workers = itertools.cycle(WORKER_ADDRESSES)

class CoordinatorServicer(inference_pb2_grpc.CoordinatorServicer):

    async def SubmitTask(self, request, context):
        future = asyncio.get_event_loop().create_future()
        await request_queue.put((request, future))
        logger.debug(f"Received request with {len(request.texts)} texts")
        return await future

async def batching_loop():
    while True:
        batch_requests = []
        futures = []
        all_texts = []
        counts = []

        req, fut = await request_queue.get()
        batch_requests.append(req)
        futures.append(fut)
        all_texts.extend(req.texts)
        counts.append(len(req.texts))

        start = asyncio.get_event_loop().time()
        while len(all_texts) < MAX_BATCH_SIZE:
            elapsed = asyncio.get_event_loop().time() - start
            timeout = MAX_WAIT - elapsed
            try:
                req, fut = await asyncio.wait_for(request_queue.get(), timeout=max(0, timeout))
                if len(all_texts) + len(req.texts) > MAX_BATCH_SIZE:
                    await request_queue.put((req, fut))
                    break
                batch_requests.append(req)
                futures.append(fut)
                all_texts.extend(req.texts)
                counts.append(len(req.texts))
            except asyncio.TimeoutError:
                break

        batch_request = inference_pb2.InferRequest(
            input_data=all_texts,
            request_ids=["" for _ in all_texts]  # Dummy IDs, not used
        )

        worker_addr = next(round_robin_workers)
        logger.info(f"Dispatching batch of {len(all_texts)} texts to {worker_addr}")
        asyncio.create_task(dispatch_batch(batch_request, futures, counts, worker_addr))

async def dispatch_batch(batch_request, futures, counts, worker_addr):
    try:
        async with aio.insecure_channel(worker_addr) as channel:
            stub = inference_pb2_grpc.WorkerStub(channel)
            batch_response = await stub.Infer(batch_request)
            logger.info(f"Received response from {worker_addr} with {len(batch_response.embeddings)} embeddings")
    except grpc.aio.AioRpcError as e:
        logger.error(f"RPC error from {worker_addr}: {e}")
        batch_response = inference_pb2.InferResponse(
            worker_id="error",
            success=False,
            error_message=str(e),
            request_ids=[],
            embeddings=[]
        )

    idx = 0
    for fut, count in zip(futures, counts):
        embeddings = batch_response.embeddings[idx:idx+count]
        response = inference_pb2.EmbedResponse(embeddings=embeddings)
        fut.set_result(response)
        idx += count

async def serve():
    server = aio.server()
    inference_pb2_grpc.add_CoordinatorServicer_to_server(CoordinatorServicer(), server)
    server.add_insecure_port("0.0.0.0:50050")
    await server.start()
    logger.info("Coordinator gRPC server started on port 50050")
    asyncio.create_task(batching_loop())
    await server.wait_for_termination()

if __name__ == "__main__":
    asyncio.run(serve())
