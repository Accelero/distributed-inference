import asyncio
import shutil
import subprocess
import random
import threading
import logging
from traffic_generator import BurstyTrafficGenerator

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

def get_container_runtime():
    if shutil.which("podman"):
        return "podman"
    elif shutil.which("docker"):
        return "docker"
    else:
        raise RuntimeError("Neither podman nor docker is installed.")

def run_pumba_delay(target, duration="20s", delay_ms=100):
    runtime = get_container_runtime()
    cmd = [
        runtime, "run", "--rm", "--privileged",
        "-v", "/var/run/docker.sock:/var/run/docker.sock",
        "gaiaadm/pumba:latest",
        "netem", "--duration", duration, "delay", "--time", str(delay_ms), target
    ]
    logging.info(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

def run_pumba_loss(target, duration="20s", percent=10):
    runtime = get_container_runtime()
    cmd = [
        runtime, "run", "--rm", "--privileged",
        "-v", "/var/run/docker.sock:/var/run/docker.sock",
        "gaiaadm/pumba:latest",
        "netem", "--duration", duration, "loss", "--percent", str(percent), target
    ]
    logging.info(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

def run_pumba_kill(target):
    runtime = get_container_runtime()
    cmd = [
        runtime, "run", "--rm", "--privileged",
        "-v", "/var/run/docker.sock:/var/run/docker.sock",
        "gaiaadm/pumba:latest",
        "kill", "--signal", "SIGKILL", target
    ]
    logging.info(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

def run_pumba_stop(target, duration="10s"):
    runtime = get_container_runtime()
    cmd = [
        runtime, "run", "--rm", "--privileged",
        "-v", "/var/run/docker.sock:/var/run/docker.sock",
        "gaiaadm/pumba:latest",
        "stop", "--duration", duration, target
    ]
    logging.info(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

def get_running_workers():
    runtime = get_container_runtime()
    result = subprocess.run(
        [runtime, "ps", "--format", "{{.Names}}"],
        capture_output=True, text=True, check=True
    )
    workers = [name for name in result.stdout.splitlines() if name.startswith("distributed-inference-worker-")]
    return workers

async def induce_faults():
    # Define possible Pumba faults
    faults = [
        lambda: run_pumba_delay("distributed-inference-coordinator-1", duration="20s", delay_ms=random.choice([50, 100, 200])),
        lambda: run_pumba_loss("distributed-inference-coordinator-1", duration="20s", percent=random.choice([5, 10, 20])),
        lambda: run_pumba_kill("distributed-inference-coordinator-1"),
        lambda: run_pumba_stop("distributed-inference-coordinator-1", duration="10s")
    ]
    # Randomly select and apply 1-2 faults
    num_faults = random.randint(1, len(faults))
    selected_faults = random.sample(faults, num_faults)
    for fault in selected_faults:
        fault()

async def main():
    generator = BurstyTrafficGenerator(
        batch_size=10,
        rate_mean=20,
        rate_noise_time_constant=1,
        rate_noise_std=0.0,  # No stochastic variation
        validation_data_path="validation_data.jsonl",
        coordinator_addr="localhost:50050"
    )
    await generator.start()
    # Delay at coordinator
    logging.info("Injecting delay fault at coordinator...")
    run_pumba_delay("distributed-inference-coordinator-1", duration="20s", delay_ms=100)
    await asyncio.sleep(25)
    # Loss at coordinator
    logging.info("Injecting loss fault at coordinator...")
    run_pumba_loss("distributed-inference-coordinator-1", duration="20s", percent=10)
    await asyncio.sleep(25)
    # Randomly kill a running worker
    workers = get_running_workers()
    if workers:
        worker_name = random.choice(workers)
        logging.info(f"Injecting kill (crash) fault at {worker_name}...")
        run_pumba_kill(worker_name)
    else:
        logging.warning("No running worker containers found.")
    await asyncio.sleep(5)
    await generator.stop()

if __name__ == "__main__":
    asyncio.run(main())
