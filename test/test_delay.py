import argparse
import asyncio
import logging
import subprocess
from traffic_generator import TrafficGenerator

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

def run_pumba_delay_background(target, latency_ms=100, duration="1h"):
    cmd = [
        "docker", "run", "--rm", "--privileged",
        "-v", "/var/run/docker.sock:/var/run/docker.sock",
        "gaiaadm/pumba:latest",
        "--log-level", "info",
        "netem", "--duration", duration, "delay", "--time", str(latency_ms), target
    ]
    logging.info(f"Starting Pumba network delay: {latency_ms}ms for {duration} on {target}")
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

def download_pumba_image():
    cmd = ["docker", "pull", "gaiaadm/pumba:latest"]
    logging.info("Checking for Pumba image (pulling if needed)...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        logging.info("Pumba image ready.")
    elif "Image is up to date" in result.stdout or "Image is up to date" in result.stderr:
        logging.info("Pumba image already up to date.")
    else:
        logging.warning(f"docker pull failed, but continuing. Output: {result.stdout}\n{result.stderr}")

async def main(test_duration, latency_ms, batch_size, rate_mean, rate_noise_time_constant, rate_noise_std, timeout, validation_data_path, coordinator_addr):
    download_pumba_image()
    generator = TrafficGenerator(
        batch_size=batch_size,
        rate_mean=rate_mean,
        rate_noise_time_constant=rate_noise_time_constant,
        rate_noise_std=rate_noise_std,
        timeout=timeout,
        validation_data_path=validation_data_path,
        coordinator_addr=coordinator_addr
    )
    pumba_proc = run_pumba_delay_background(
        "distributed-inference-coordinator-1",
        latency_ms=latency_ms,
        duration=f"{test_duration+10}s"
    )
    try:
        logging.info("Starting traffic generation test.")
        await generator.start()
        await asyncio.sleep(test_duration)
        await generator.stop()
        logging.info("Traffic generation complete.")
    finally:
        logging.info("Stopping Pumba network delay...")
        pumba_proc.terminate()
        try:
            pumba_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            logging.warning("Pumba did not exit, killing...")
            pumba_proc.kill()
        output = pumba_proc.communicate()[0]
        logging.info(f"Pumba output (combined):\n{output.decode().strip()}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inject network delay and test system response.")
    parser.add_argument('-d', '--duration', type=int, default=20, help='Test duration in seconds (default: 20)')
    parser.add_argument('-l', '--latency', type=int, default=100, help='Injected latency in ms (default: 100)')
    parser.add_argument('--batch-size', type=int, default=10, help='Batch size (default: 10)')
    parser.add_argument('--rate-mean', type=float, default=10, help='Mean request rate (default: 10)')
    parser.add_argument('--rate-noise-time-constant', type=float, default=1, help='Rate noise time constant (default: 1)')
    parser.add_argument('--rate-noise-std', type=float, default=0.5, help='Rate noise standard deviation (default: 0.5)')
    parser.add_argument('--timeout', type=int, default=10, help='Request timeout in seconds (default: 10)')
    parser.add_argument('--validation-data-path', type=str, default="validation_data.jsonl", help='Path to validation data (default: validation_data.jsonl)')
    parser.add_argument('--coordinator-addr', type=str, default="localhost:50050", help='Coordinator gRPC address (default: localhost:50050)')
    args = parser.parse_args()
    asyncio.run(main(
        args.duration, args.latency,
        args.batch_size, args.rate_mean, args.rate_noise_time_constant, args.rate_noise_std,
        args.timeout, args.validation_data_path, args.coordinator_addr
    ))
