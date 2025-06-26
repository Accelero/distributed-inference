import asyncio
import grpc
from grpc.experimental import aio
from proto import inference_pb2
from proto import inference_pb2_grpc
import itertools
from custom_logging import logger
import uuid
import time
import socket
import random


MAX_BATCH_SIZE = 20
MAX_WAIT = 0.01  # seconds
# Use a single service name and port for worker discovery
WORKER_SERVICE = "worker"
WORKER_PORT = 50051

request_queue = asyncio.Queue()
worker_ip_cycle = None

class CoordinatorServicer(inference_pb2_grpc.CoordinatorServicer):

    async def SubmitTask(self, request, context):
        future = asyncio.get_event_loop().create_future()
        await request_queue.put((request, future))
        logger.debug(f"Received request with {len(request.texts)} texts")
        return await future

# Helper to resolve all IPs for a service name, returning just IPs
async def resolve_worker_ips(service_host, service_port):
    loop = asyncio.get_event_loop()
    infos = await loop.run_in_executor(None, lambda: socket.getaddrinfo(service_host, service_port, proto=socket.IPPROTO_TCP))
    ips = list({info[4][0] for info in infos})
    return ips

async def batching_loop():
    global worker_ip_cycle
    if worker_ip_cycle is None:
        worker_ips = await resolve_worker_ips(WORKER_SERVICE, WORKER_PORT)
        worker_ip_cycle = itertools.cycle(worker_ips)
    while True:
        requests = []
        futures = []
        all_texts = []
        all_ids = []
        counts = []

        req, fut = await request_queue.get()
        requests.append(req)
        futures.append(fut)
        all_texts.extend(req.texts)
        all_ids.extend([str(uuid.uuid4()) for _ in req.texts])
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
                requests.append(req)
                futures.append(fut)
                all_texts.extend(req.texts)
                all_ids.extend([str(uuid.uuid4()) for _ in req.texts])
                counts.append(len(req.texts))
            except asyncio.TimeoutError:
                break

        worker_request = inference_pb2.InferRequest(
            input_data=all_texts,
            ids=all_ids
        )

        # Pick the next IP in round robin for this batch
        worker_ip = next(worker_ip_cycle)
        worker_addr = f"{worker_ip}:{WORKER_PORT}"
        logger.info(f"Dispatching batch of {len(worker_request.input_data)} texts to worker_ip={worker_ip} with ids={[id[:8] for id in worker_request.ids]}")
        asyncio.create_task(dispatch_batch(worker_request, futures, counts, worker_addr))

async def dispatch_batch(worker_request, futures, counts, worker_addr):
    retry_count = 0
    max_retries = 3
    start_time = time.time()
    while True:
        try:
            async with aio.insecure_channel(worker_addr) as channel:
                stub = inference_pb2_grpc.WorkerStub(channel)
                worker_response = await stub.Infer(worker_request)
                latency = (time.time() - start_time) * 1000  # ms
                logger.info(
                    f"Batch processed: worker_id={worker_response.worker_id:<10} "
                    f"ids={[id[:8] for id in worker_response.ids]} latency={latency:.2f}ms retry_count={retry_count} "
                    f"success={worker_response.success} error={worker_response.error_message}"
                )
            break
        except grpc.aio.AioRpcError as e:
            latency = (time.time() - start_time) * 1000  # ms
            logger.error(
                f"Batch dispatch failed: worker_id=error ids={[id[:8] for id in worker_request.ids]} "
                f"latency={latency:.2f}ms retry_count={retry_count} error={e}"
            )
            retry_count += 1
            if retry_count > max_retries:
                worker_response = inference_pb2.InferResponse(
                    worker_id="error",
                    success=False,
                    error_message=str(e),
                    ids=worker_request.ids,
                    embeddings=[[] for _ in worker_request.ids]
                )
                break
            await asyncio.sleep(0.1 * retry_count)

    idx = 0
    for fut, count in zip(futures, counts):
        embeddings = worker_response.embeddings[idx:idx+count]
        ids = worker_response.ids[idx:idx+count]
        client_response = inference_pb2.EmbedResponse(ids=ids, embeddings=embeddings)
        fut.set_result(client_response)
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
