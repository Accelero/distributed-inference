import shutil
import subprocess
import random
import logging
import asyncio
import argparse
from traffic_generator import BurstyTrafficGenerator

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

def get_container_runtime(cli_runtime=None):
    if cli_runtime:
        if shutil.which(cli_runtime):
            return cli_runtime
        else:
            raise RuntimeError(f"{cli_runtime} is not installed.")
    if shutil.which("podman"):
        return "podman"
    elif shutil.which("docker"):
        return "docker"
    else:
        raise RuntimeError("Neither podman nor docker is installed.")

def run_pumba_kill(target, runtime):
    cmd = [
        runtime, "run", "--rm", "--privileged",
        "-v", "/var/run/docker.sock:/var/run/docker.sock",
        "gaiaadm/pumba:latest",
        "kill", "--signal", "SIGKILL", target
    ]
    logging.debug(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

def get_running_workers(runtime):
    result = subprocess.run(
        [runtime, "ps", "--format", "{{.Names}}"],
        capture_output=True, text=True, check=True
    )
    workers = [name for name in result.stdout.splitlines() if "distributed-inference-worker-" in name]
    return workers

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", choices=["podman", "docker"], help="Container runtime to use")
    args = parser.parse_args()

    runtime = get_container_runtime(args.runtime)

    generator = BurstyTrafficGenerator(
        batch_size=10,
        rate_mean=20,
        rate_noise_time_constant=1,
        rate_noise_std=0.0,
        validation_data_path="validation_data.jsonl",
        coordinator_addr="localhost:50050"
    )
    await generator.start()

    workers = get_running_workers(runtime)
    if workers:
        worker_name = random.choice(workers)
        logging.info(f"Injecting kill (crash) fault at {worker_name}...")
        run_pumba_kill(worker_name, runtime)
    else:
        logging.warning("No running worker containers found.")

    # Let the generator run a bit after the crash
    await asyncio.sleep(10)
    await generator.stop()

if __name__ == "__main__":
    asyncio.run(main())
