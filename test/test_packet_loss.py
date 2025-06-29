import argparse
import asyncio
import logging
import subprocess
from traffic_generator import BurstyTrafficGenerator

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

def run_pumba_loss_background(target, loss_percent=10, duration="1h"):
    cmd = [
        "docker", "run", "--rm", "--privileged",
        "-v", "/var/run/docker.sock:/var/run/docker.sock",
        "gaiaadm/pumba:latest",
        "--log-level", "info",
        "netem", "--duration", duration, "loss", "--percent", str(loss_percent), target
    ]
    logging.info(f"Starting Pumba packet loss: {loss_percent}% for {duration} on {target}")
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

async def main(test_duration, loss_percent):
    download_pumba_image()
    generator = BurstyTrafficGenerator(
        batch_size=10,
        rate_mean=1,
        rate_noise_time_constant=1,
        rate_noise_std=0.0,
        timeout=1,
        validation_data_path="validation_data.jsonl",
        coordinator_addr="localhost:50050"
    )
    pumba_proc = run_pumba_loss_background(
        "distributed-inference-coordinator-1",
        loss_percent=loss_percent,
        duration=f"{test_duration+10}s"
    )
    try:
        logging.info("Starting traffic generation test.")
        await generator.start()
        await asyncio.sleep(test_duration)
        await generator.stop()
        logging.info("Traffic generation complete.")
    finally:
        logging.info("Stopping Pumba packet loss...")
        pumba_proc.terminate()
        try:
            pumba_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            logging.warning("Pumba did not exit, killing...")
            pumba_proc.kill()
        output = pumba_proc.communicate()[0]
        logging.info(f"Pumba output (combined):\n{output.decode().strip()}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inject packet loss and test system response.")
    parser.add_argument('-d', '--duration', type=int, default=20, help='Test duration in seconds (default: 20)')
    parser.add_argument('-p', '--percent', type=int, default=10, help='Packet loss percent (default: 10)')
    args = parser.parse_args()
    asyncio.run(main(args.duration, args.percent))
