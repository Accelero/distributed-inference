import grpc

from proto import inference_pb2, inference_pb2_grpc

def main():
    channel = grpc.insecure_channel('localhost:50050')
    stub = inference_pb2_grpc.CoordinatorStub(channel)
    request = inference_pb2.InferRequest(request_id="test-1", input_data="Hello, world!")
    response = stub.SubmitTask(request)
    print("Response from coordinator:")
    print(response)

if __name__ == "__main__":
    main()
