import argparse
import asyncio
import logging
from traffic_generator import TrafficGenerator

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

async def main(args):
    generator = TrafficGenerator(
        batch_size=args.batch_size,
        rate_mean=args.rate_mean,
        rate_noise_time_constant=args.rate_noise_time_constant,
        rate_noise_std=args.rate_noise_std,
        timeout=args.timeout,
        validation_data_path=args.validation_data_path,
        coordinator_addr=args.coordinator_addr
    )
    logging.info("Starting traffic generation test.")
    await generator.start()
    await asyncio.sleep(args.duration)
    await generator.stop()
    logging.info("Traffic generation complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the traffic generator with customizable parameters.")
    parser.add_argument('-d', '--duration', type=int, default=20, help='Test duration in seconds (default: 20)')
    parser.add_argument('--batch-size', type=int, default=8, help='Batch size (default: 10)')
    parser.add_argument('--rate-mean', type=float, default=15, help='Mean request rate (default: 10)')
    parser.add_argument('--rate-noise-time-constant', type=float, default=1, help='Rate noise time constant (default: 1)')
    parser.add_argument('--rate-noise-std', type=float, default=0, help='Rate noise standard deviation (default: 0.5)')
    parser.add_argument('--timeout', type=int, default=10, help='Request timeout in seconds (default: 10)')
    parser.add_argument('--validation-data-path', type=str, default="validation_data.jsonl", help='Path to validation data (default: validation_data.jsonl)')
    parser.add_argument('--coordinator-addr', type=str, default="localhost:50050", help='Coordinator gRPC address (default: localhost:50050)')
    args = parser.parse_args()
    asyncio.run(main(args))
