import asyncio
import json
import math
from grpc.experimental import aio
from proto import inference_pb2
from proto import inference_pb2_grpc

COORDINATOR_ADDR = "localhost:50050"
DATA_PATH = "verification_data.jsonl"

BATCH_SIZE = 10  # Configurable
CYCLES = 10  # Number of cycles to run the validation data
DELAY_BETWEEN_BATCHES = 0  # seconds
TOLERANCE = 1e-4  # Allow small float differences due to precision


def load_validation_data():
    with open(DATA_PATH, "r") as f:
        for line in f:
            item = json.loads(line)
            yield item["text"], item["embedding"]


def embeddings_match(ref_emb, test_emb, tolerance=TOLERANCE):
    if len(ref_emb) != len(test_emb):
        return False
    return all(math.isclose(a, b, rel_tol=tolerance, abs_tol=tolerance) for a, b in zip(ref_emb, test_emb))


async def verify():
    import time
    start_time = time.time()
    async with aio.insecure_channel(COORDINATOR_ADDR) as channel:
        stub = inference_pb2_grpc.CoordinatorStub(channel)

        validation_data = list(load_validation_data())
        total_passed = 0
        total_failed = 0
        for cycle in range(CYCLES):
            num_passed = 0
            num_failed = 0

            async def send_batch(batch):
                texts = [item[0] for item in batch]
                expected_embeddings = [item[1] for item in batch]

                request = inference_pb2.EmbedRequest(texts=texts)
                response = await stub.SubmitTask(request)

                for j, emb_msg in enumerate(response.embeddings):
                    returned = list(emb_msg.vector)
                    expected = expected_embeddings[j]
                    if embeddings_match(expected, returned):
                        nonlocal num_passed
                        num_passed += 1
                    else:
                        nonlocal num_failed
                        num_failed += 1
                        print(f"Mismatch for text: {texts[j]}\nExpected: {expected[:5]}...\nReturned: {returned[:5]}...\n")

            tasks = []
            for i in range(0, len(validation_data), BATCH_SIZE):
                batch = validation_data[i:i + BATCH_SIZE]
                task = send_batch(batch)
                if DELAY_BETWEEN_BATCHES == 0:
                    tasks.append(task)
                else:
                    await task
                    await asyncio.sleep(DELAY_BETWEEN_BATCHES)

            if DELAY_BETWEEN_BATCHES == 0:
                await asyncio.gather(*tasks)

            print(f"Cycle {cycle + 1}/{CYCLES} completed. Passed: {num_passed}, Failed: {num_failed}")
            total_passed += num_passed
            total_failed += num_failed
        total_time = time.time() - start_time
        print(f"\nVerification completed. Total Passed: {total_passed}, Total Failed: {total_failed}")
        print(f"Total time elapsed: {total_time:.2f} seconds")


if __name__ == "__main__":
    asyncio.run(verify())
