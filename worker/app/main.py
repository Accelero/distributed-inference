import grpc
from concurrent import futures
import time

from proto import inference_pb2
from proto import inference_pb2_grpc

class WorkerServicer(inference_pb2_grpc.WorkerServicer):
    def Infer(self, request, context):
        # Dummy inference logic
        output = f"Processed: {request.input_data}"
        return inference_pb2.InferResponse(
            request_id=request.request_id,
            output_data=output,
            worker_id="worker-1",
            success=True,
            error_message=""
        )

    def Heartbeat(self, request, context):
        return inference_pb2.HeartbeatResponse(alive=True)

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    inference_pb2_grpc.add_WorkerServicer_to_server(WorkerServicer(), server)
    server.add_insecure_port('0.0.0.0:50051')
    server.start()
    print("Worker gRPC server started on port 50051")
    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == "__main__":
    serve()
