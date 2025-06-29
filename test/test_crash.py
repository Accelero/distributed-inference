import argparse
import asyncio
import logging
import random
import subprocess
from traffic_generator import BurstyTrafficGenerator

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

def run_pumba_kill_background(target):
    cmd = [
        "docker", "run", "--rm", "--privileged",
        "-v", "/var/run/docker.sock:/var/run/docker.sock",
        "gaiaadm/pumba:latest",
        "--log-level", "info",
        "kill", "--signal", "SIGKILL", target
    ]
    logging.info(f"Starting Pumba kill (SIGKILL) on {target}")
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

def get_running_workers():
    result = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}"],
        capture_output=True, text=True, check=True
    )
    workers = [name for name in result.stdout.splitlines() if "distributed-inference-worker-" in name]
    return workers

async def main(pre_kill_time, post_kill_time):
    download_pumba_image()
    generator = BurstyTrafficGenerator(
        batch_size=10,
        rate_mean=10,
        rate_noise_time_constant=1,
        rate_noise_std=0.0,
        timeout=10,
        validation_data_path="validation_data.jsonl",
        coordinator_addr="localhost:50050"
    )
    await generator.start()
    workers = get_running_workers()
    if not workers:
        logging.warning("No running worker containers found.")
        await generator.stop()
        return
    worker_name = random.choice(workers)
    logging.info(f"Selected worker for crash: {worker_name}")
    logging.info(f"Waiting {pre_kill_time}s before injecting crash...")
    await asyncio.sleep(pre_kill_time)
    pumba_proc = run_pumba_kill_background(worker_name)
    try:
        pumba_proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        logging.warning("Pumba did not exit, killing...")
        pumba_proc.kill()
    output = pumba_proc.communicate()[0]
    logging.info(f"Pumba output (combined):\n{output.decode().strip()}")
    logging.info(f"Waiting {post_kill_time}s after crash...")
    await asyncio.sleep(post_kill_time)
    await generator.stop()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inject worker crash (SIGKILL) and test system response.")
    parser.add_argument('-b', '--before', type=int, default=10, help='Seconds to wait before kill (default: 5)')
    parser.add_argument('-a', '--after', type=int, default=20, help='Seconds to wait after kill (default: 10)')
    args = parser.parse_args()
    asyncio.run(main(args.before, args.after))
