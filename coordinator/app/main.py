import asyncio
import logging
import socket
import time
import uuid

import custom_logging
import grpc
from grpc.experimental import aio
from prometheus_client import start_http_server, Gauge, Counter

from proto.public_pb2 import EmbedRequest, EmbedResponse, ReturnCode, Embedding
from proto.public_pb2_grpc import TextEmbeddingServicer, add_TextEmbeddingServicer_to_server
from proto.private_pb2 import InferRequest, InferResponse, HeartbeatRequest, HeartbeatResponse, StatusCode
from proto.private_pb2_grpc import WorkerStub
from utility import DynIncAsyncSemaphore

# Config
MAX_BATCH_SIZE = 20
MAX_BATCH_WAIT = 0.01  # seconds
WORKER_SERVICE_NAME = "worker"
WORKER_PORT = 50051
COORDINATOR_PORT = 50050
MAX_RETRIES = 3
MAX_INFLIGHT_BATCHES_MULT = 4
MAX_QUEUE_SIZE = 250


# --------------------------- Shared State ---------------------------
request_queue = asyncio.Queue(MAX_QUEUE_SIZE)
inflight_semaphore = DynIncAsyncSemaphore(MAX_INFLIGHT_BATCHES_MULT)


class WorkerState:
    worker_ips = []
    worker_health = {}
    worker_index = 0
# --------------------------------------------------------------------

request_count = Counter('coordinator_request_count', 'Total number of requests received by the coordinator')
request_queue_gauge = Gauge('coordinator_queue_size', 'Number of requests in the coordinator queue')
worker_count_gauge = Gauge('coordinator_worker_count', 'Number of workers registered with the coordinator')
request_queue_full_count = Counter('coordinator_queue_full_count', 'Number of requests declined due to full queue')
request_timeout_count = Counter('coordinator_request_timeout_count', 'Number of requests that timed out waiting for a worker')

class TextEmbeddingServicerImpl(TextEmbeddingServicer):
    async def Embed(self, request, context):
        try:
            if len(request.texts) > MAX_BATCH_SIZE:
                logging.warning(
                    f"Request declined: invalid batch size {len(request.texts)} > max batch size {MAX_BATCH_SIZE}.")
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                msg = f"Batch size exceeds maximum of {MAX_BATCH_SIZE}."
                context.set_details(msg)
                return EmbedResponse(
                    ids=[],
                    embeddings=[],
                    code=ReturnCode.ERROR,
                    return_msg=msg)
            if request_queue.full():
                request_queue_full_count.inc()  # Increment the declined counter
                logging.warning(
                    f"Request declined: queue is full.")
                context.set_code(grpc.StatusCode.RESOURCE_EXHAUSTED)
                msg = f"Request queue is full. Try again later."
                context.set_details(msg)
                return EmbedResponse(
                    ids=[],
                    embeddings=[],
                    code=ReturnCode.ERROR,
                    return_msg=msg)
            future = asyncio.get_event_loop().create_future()
            await request_queue.put((request, future))
            logging.debug(f"Received request with batch size {len(request.texts)}.")
            return await future
        except asyncio.CancelledError:
            request_timeout_count.inc()
            msg = f"Request cancelled due to timeout."
            context.set_details(msg)
            return EmbedResponse(
                ids=[],
                embeddings=[],
                code=ReturnCode.ERROR,
                return_msg=msg)
        finally:
            request_count.inc()
            


async def batching_loop():
    """
    Start loop that consumes the request queue and aggregates requests up to MAX_BATCH_SIZE.
    Requests are delayed up to MAX_BATCH_WAIT seconds to allow for more requests to accumulate.
    The actual wait time is dynamically adjusted based on the fill level of the waiting batch. So that
    if the batch is small, it waits longer to allow more requests to come in.

    The aggregated batches are only dispatched to workers if inflight worker requests are below 
    a set threshold. The threshold is dynamically updated based on the number of workers available.
    """
    global inflight_semaphore
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
        ids = [str(uuid.uuid4()) for _ in req.texts]
        all_ids.extend(ids)
        counts.append(len(req.texts))

        start = asyncio.get_event_loop().time()

        while len(all_texts) < MAX_BATCH_SIZE:
            dynamic_wait = MAX_BATCH_WAIT * len(all_texts) / MAX_BATCH_SIZE
            elapsed = asyncio.get_event_loop().time() - start
            timeout = dynamic_wait - elapsed
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

        worker_request = InferRequest(
            input_data=all_texts,
            ids=all_ids
        )
        await inflight_semaphore.acquire()

        async def wrapped_dispatch(worker_request, futures, counts):
            try:
                await dispatch_coro(worker_request, futures, counts)
            finally:
                await inflight_semaphore.release()
        asyncio.create_task(wrapped_dispatch(worker_request, futures, counts))
        # asyncio.create_task(wrapped_dispatch())


async def health_check_loop(interval=5):
    """
    Start loop, that periodically probes workers and updates their health status in the WorkerState.
    """
    while True:
        for k in list(WorkerState.worker_health):
            if k not in WorkerState.worker_ips:
                del WorkerState.worker_health[k]
        await asyncio.gather(*(health_check_coro(ip) for ip in WorkerState.worker_ips), asyncio.sleep(interval))
        logging.debug(f"Worker health report: {WorkerState.worker_health}")


async def health_check_coro(worker_ip):
    '''
    Check the health of a worker and update the shared worker health state.
    '''
    addr = f"{worker_ip}:{WORKER_PORT}"
    try:
        async with aio.insecure_channel(addr) as channel:
            stub = WorkerStub(channel)
            resp = await stub.Heartbeat(HeartbeatRequest(), timeout=2)
            WorkerState.worker_health[worker_ip] = resp.status
    except Exception as e:
        WorkerState.worker_health[worker_ip] = StatusCode.STATUS_UNAVAILABLE
        logging.warning(f"Health check failed for {addr}: {e}")


async def resolve_worker_loop(interval=10):
    """
    Periodically resolve worker IPs and update the shared list in-place.
    """
    while True:
        try:
            infos = socket.getaddrinfo(
                WORKER_SERVICE_NAME, WORKER_PORT, proto=socket.IPPROTO_TCP)
            new_ips = list({info[4][0] for info in infos})
            # Update the list in-place to keep references valid
            WorkerState.worker_ips.clear()
            WorkerState.worker_ips.extend(new_ips)
            logging.debug(f"Resolved worker IPs: {WorkerState.worker_ips}")
            await inflight_semaphore.update_threshold(
                len(WorkerState.worker_ips) * MAX_INFLIGHT_BATCHES_MULT)
        except Exception as e:
            logging.error(f"Could not resolve worker IPs.", exc_info=e)
        await asyncio.sleep(interval)


async def dispatch_coro(worker_request, futures, counts):
    '''
    Dispatch a batch of requests to a worker, retrying on failure.
    Handles the response and fulfills futures with the result or error.
    '''
    retry_count = 0
    while retry_count <= MAX_RETRIES:
        # Send request to worker
        try:
            worker_ip = pick_worker()
            worker_addr = f"{worker_ip}:{WORKER_PORT}"
            async with aio.insecure_channel(worker_addr) as channel:
                stub = WorkerStub(channel)
                start_time = time.time()
                worker_response = await stub.Infer(worker_request)
                latency = (time.time() - start_time) * 1000  # ms
                logging.info(
                    f"Batch processed: worker_id={worker_response.worker_id:<10} "
                    f"ids={[id[:8] for id in worker_response.ids]} latency={latency:.2f}ms retry_count={retry_count} "
                    f"code={worker_response.code} return_msg={worker_response.return_msg}"
                )
            break
        except grpc.aio.AioRpcError as e:
            logging.error(
                f"Batch dispatch failed: worker_ip= {worker_ip} request_ids={[id[:8] for id in worker_request.ids]} "
                f"retry_count={retry_count} error={e}")
            retry_count += 1
            await asyncio.sleep(0.1 * retry_count)
    else:
        # If we exhausted all retries, fulfill futures with an error response
        logging.error(
            f"Max retries exceeded for request_ids={[id[:8] for id in worker_request.ids]}")
        idx = 0
        for fut, cnt in zip(futures, counts):
            ids = worker_request.ids[idx:idx+cnt]
            client_response = EmbedResponse(
                ids=ids, embeddings=[], code=ReturnCode.ERROR,
                return_msg="Downstream worker reached max retries.")
            if not fut.done():
                fut.set_result(client_response)
            idx += cnt
        return

    # Otherwise, fullfill futures with the worker response
    if worker_response.code == ReturnCode.OK:
        # Make sure we have a valid response, otherwise return error based on request ids
        try:
            idx = 0
            for fut, cnt in zip(futures, counts):
                embeddings = worker_response.embeddings[idx:idx+cnt]
                ids = worker_response.ids[idx:idx+cnt]
                client_response = EmbedResponse(
                    ids=ids, embeddings=embeddings, code=ReturnCode.OK, return_msg="")
                if not fut.done():
                    fut.set_result(client_response)
                idx += cnt
        except Exception as e:
            logging.error(
                f"Error processing worker response: request_ids={[id[:8] for id in worker_request.ids]}, exception={e}")
            idx = 0
            for fut, cnt in zip(futures, counts):
                ids = worker_request.ids[idx:idx+cnt]
                client_response = EmbedResponse(
                    ids=ids, embeddings=[], code=ReturnCode.ERROR,
                    return_msg="Error processing result.")
                if not fut.done():
                    fut.set_result(client_response)
                idx += cnt
    else:
        logging.error(
            f"Worker returned not ok: code={worker_response.code} msg={worker_response.return_msg} "
            f"request_ids={[id[:8] for id in worker_request.ids]}")
        idx = 0
        for fut, cnt in zip(futures, counts):
            ids = worker_request.ids[idx:idx+cnt]
            client_response = EmbedResponse(
                ids=ids, embeddings=[], code=ReturnCode.ERROR,
                return_msg="Error processing request")
            if not fut.done():
                fut.set_result(client_response)
            idx += cnt


def pick_worker():
    '''
    Pick a worker in round robin fashion, preferring healthy workers.
    '''
    second_choice = None
    for _ in range(len(WorkerState.worker_ips)):
        worker_ip = WorkerState.worker_ips[WorkerState.worker_index]
        WorkerState.worker_index = (
            WorkerState.worker_index + 1) % len(WorkerState.worker_ips)
        if WorkerState.worker_health.get(worker_ip, StatusCode.STATUS_UNAVAILABLE) == StatusCode.STATUS_OK:
            return worker_ip
        elif WorkerState.worker_health.get(worker_ip, StatusCode.STATUS_UNAVAILABLE) == StatusCode.STATUS_DEGRADED:
            second_choice = worker_ip
    if second_choice:
        return second_choice
    logging.error("No healthy workers available.")
    return worker_ip


async def queue_metrics_loop():
    while True:
        request_queue_gauge.set(request_queue.qsize())
        worker_count_gauge.set(len(WorkerState.worker_ips))
        await asyncio.sleep(2)


async def serve():
    # Start Prometheus metrics server
    start_http_server(8000)  # Expose metrics on port 8000
    asyncio.create_task(queue_metrics_loop())

    # Start background coroutines
    asyncio.create_task(resolve_worker_loop())
    asyncio.create_task(health_check_loop())
    asyncio.create_task(batching_loop())

    server = aio.server()
    add_TextEmbeddingServicer_to_server(
        TextEmbeddingServicerImpl(), server)
    server.add_insecure_port(f"0.0.0.0:{COORDINATOR_PORT}")
    await server.start()
    logging.info(f"Coordinator gRPC server started on port {COORDINATOR_PORT}")

    await server.wait_for_termination()


if __name__ == "__main__":
    asyncio.run(serve())
