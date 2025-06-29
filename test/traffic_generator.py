import asyncio
import grpc
import json
import time
import logging
import math
import random
from proto.public_pb2 import EmbedRequest
from proto.public_pb2_grpc import TextEmbeddingStub

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

def embeddings_match(ref_emb, test_emb, tolerance=1e-10):
    if len(ref_emb) != len(test_emb):
        return False
    return all(math.isclose(a, b, rel_tol=tolerance, abs_tol=tolerance) for a, b in zip(ref_emb, test_emb))

class BurstyTrafficGenerator:
    def __init__(self,
                 batch_size=5,
                 rate_mean=20,
                 rate_noise_time_constant=3,
                 rate_noise_std=0.2,
                 timeout=10,
                 validation_data_path="validation_data.jsonl",
                 coordinator_addr="localhost:50050"):
        self.batch_size = batch_size
        self.rate_mean = rate_mean
        self.rate_noise_time_constant = rate_noise_time_constant
        self.timeout = timeout
        self.rate_noise_std = rate_noise_std
        self.validation_data_path = validation_data_path
        self.coordinator_addr = coordinator_addr
        self._task = None
        self._cancel_event = asyncio.Event()

    def load_verification_data(self):
        with open(self.validation_data_path, "r", encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]

    async def start(self):
        self._cancel_event.clear()
        self._task = asyncio.create_task(self._run())
        return self._task

    async def stop(self):
        self._cancel_event.set()
        if self._task:
            await self._task

    async def _run(self):
        data = self.load_verification_data()
        if not data:
            logging.error("No verification data found.")
            return
        dt = 1.0 / self.rate_mean
        noise = 0.0
        async with grpc.aio.insecure_channel(self.coordinator_addr) as channel:
            stub = TextEmbeddingStub(channel)
            idx = 0
            success_count = 0
            sent_count = 0
            last_log_time = time.time()
            pending = set()
            while not self._cancel_event.is_set():
                # Ornstein-Uhlenbeck colored noise
                alpha = math.exp(-dt / self.rate_noise_time_constant)
                noise = alpha * noise + math.sqrt(1 - alpha**2) * random.gauss(0, 1)
                current_rate = self.rate_mean * math.exp(self.rate_noise_std * noise)
                current_rate = max(0.1, current_rate)
                batch = [data[(idx + i) % len(data)]["text"] for i in range(self.batch_size)]
                batch_embeddings = [data[(idx + i) % len(data)]["embedding"] for i in range(self.batch_size)]
                idx += self.batch_size
                req = EmbedRequest(texts=batch)
                # Fire and forget: schedule the request, log on completion
                async def send_and_log(req, batch, batch_embeddings):
                    try:
                        resp = await stub.Embed(req, timeout=self.timeout)
                        if hasattr(resp, 'embeddings') and len(resp.embeddings) == len(batch_embeddings):
                            mismatches = [i for i, emb_msg in enumerate(resp.embeddings)
                                          if not embeddings_match(batch_embeddings[i], list(emb_msg.vector))]
                            if mismatches:
                                for i in mismatches:
                                    logging.error(f"Embedding mismatch for text: {batch[i]}\nExpected: {batch_embeddings[i][:5]}...\nReturned: {list(resp.embeddings[i].vector)[:5]}...\nResponse code: {resp.code} | Return msg: {resp.return_msg}")
                            # No else: don't increment success_count, just log errors
                        else:
                            logging.error(f"Response does not match request! Sent: {batch} | Response code: {resp.code} | Return msg: {resp.return_msg}")
                    except Exception as e:
                        logging.error(f"Request failed: {e}")
                asyncio.create_task(send_and_log(req, batch, batch_embeddings))
                sent_count += 1
                now = time.time()
                if now - last_log_time >= 5:
                    avg_sent_rate = sent_count / 5
                    logging.info(f"Traffic generator running. Sent avg: {avg_sent_rate:.2f} batches/sec over last 5 seconds")
                    sent_count = 0
                    last_log_time = now
                sleep_time = max(0, 1.0 / current_rate)
                if sleep_time < 0.01:
                    continue  # Skip sleeping if less than 10ms
                try:
                    await asyncio.wait_for(self._cancel_event.wait(), timeout=sleep_time)
                except asyncio.TimeoutError:
                    pass

async def main():
    # Example: bursty traffic with custom parameters
    generator = BurstyTrafficGenerator(
        batch_size=8,
        rate_mean=30,
        rate_noise_time_constant=30,
        rate_noise_std=1,
        timeout=10,
        validation_data_path="validation_data.jsonl",
        coordinator_addr="localhost:50050"
    )
    await generator.start()
    await asyncio.sleep(300)  # Wait for 10 seconds while traffic is generated
    await generator.stop()

# Example usage for test:
if __name__ == "__main__":
    asyncio.run(main())
