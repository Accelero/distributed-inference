import asyncio
import json
from grpc.experimental import aio
from proto import inference_pb2
from proto import inference_pb2_grpc

COORDINATOR_ADDR = "localhost:50050"

# More diverse dummy test texts (100 examples)
topics = ["weather", "technology", "sports", "history", "science", "music", "travel", "food", "education", "health"]
verbs = ["discusses", "explores", "examines", "introduces", "describes", "analyzes", "presents", "compares", "evaluates", "reviews"]
texts = [
    f"This sentence {verbs[i % len(verbs)]} a topic related to {topics[i % len(topics)]}. ({i+1})"
    for i in range(100)
]

OUTPUT_PATH = "verification_data.jsonl"

async def send_and_record():
    async with aio.insecure_channel(COORDINATOR_ADDR) as channel:
        stub = inference_pb2_grpc.CoordinatorStub(channel)

        with open(OUTPUT_PATH, "w") as f:
            for text in texts:
                request = inference_pb2.EmbedRequest(texts=[text])
                response = await stub.SubmitTask(request)
                emb = list(response.embeddings[0].vector)

                record = {
                    "text": text,
                    "embedding": emb
                }
                f.write(json.dumps(record) + "\n")
                print(f"Wrote embedding for: '{text}'")

if __name__ == "__main__":
    asyncio.run(send_and_record())