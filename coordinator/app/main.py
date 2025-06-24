import grpc
from concurrent import futures
import time

from proto import inference_pb2
from proto import inference_pb2_grpc

class CoordinatorServicer(inference_pb2_grpc.CoordinatorServicer):
    def SubmitTask(self, request, context):
        # Forward request to a worker (for now, just call one worker)
        with grpc.insecure_channel('worker:50051') as channel:
            stub = inference_pb2_grpc.WorkerStub(channel)
            response = stub.Infer(request)
            return response

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    inference_pb2_grpc.add_CoordinatorServicer_to_server(CoordinatorServicer(), server)
    server.add_insecure_port('0.0.0.0:50050')
    server.start()
    print("Coordinator gRPC server started on port 50050")
    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == "__main__":
    serve()
