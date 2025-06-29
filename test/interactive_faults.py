import asyncio
import shutil
import subprocess
import random
import threading
from traffic_generator import BurstyTrafficGenerator

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
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

def run_pumba_loss(target, duration="20s", percent=10):
    runtime = get_container_runtime()
    cmd = [
        runtime, "run", "--rm", "--privileged",
        "-v", "/var/run/docker.sock:/var/run/docker.sock",
        "gaiaadm/pumba:latest",
        "netem", "--duration", duration, "loss", "--percent", str(percent), target
    ]
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

def run_pumba_kill(target):
    runtime = get_container_runtime()
    cmd = [
        runtime, "run", "--rm", "--privileged",
        "-v", "/var/run/docker.sock:/var/run/docker.sock",
        "gaiaadm/pumba:latest",
        "kill", "--signal", "SIGKILL", target
    ]
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

def run_pumba_stop(target, duration="10s"):
    runtime = get_container_runtime()
    cmd = [
        runtime, "run", "--rm", "--privileged",
        "-v", "/var/run/docker.sock:/var/run/docker.sock",
        "gaiaadm/pumba:latest",
        "stop", "--duration", duration, target
    ]
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

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

def trigger_delay():
    run_pumba_delay("distributed-inference-coordinator-1", duration="20s", delay_ms=random.choice([50, 100, 200]))

def trigger_loss():
    run_pumba_loss("distributed-inference-coordinator-1", duration="20s", percent=random.choice([5, 10, 20]))

def trigger_kill():
    run_pumba_kill("distributed-inference-coordinator-1")

def trigger_stop():
    run_pumba_stop("distributed-inference-coordinator-1", duration="10s")

def keyboard_listener():
    print("Press 'd' for delay, 'l' for loss, 'k' for kill, 's' for stop (timeout), 'q' to quit fault injection.")
    while True:
        key = input().strip().lower()
        if key == 'd':
            print("Injecting delay fault...")
            trigger_delay()
        elif key == 'l':
            print("Injecting loss fault...")
            trigger_loss()
        elif key == 'k':
            print("Injecting kill (crash) fault...")
            trigger_kill()
        elif key == 's':
            print("Injecting stop (timeout) fault...")
            trigger_stop()
        elif key == 'q':
            print("Exiting fault injection listener.")
            break
        else:
            print("Unknown key. Use 'd' for delay, 'l' for loss, 'k' for kill, 's' for stop, 'q' to quit.")

async def main():
    generator = BurstyTrafficGenerator(
        batch_size=10,
        rate_mean=20,
        rate_noise_time_constant=1,
        rate_noise_std=0.1,
        validation_data_path="validation_data.jsonl",
        coordinator_addr="localhost:50050"
    )
    await generator.start()
    # Start keyboard listener in a separate thread
    listener_thread = threading.Thread(target=keyboard_listener, daemon=True)
    listener_thread.start()
    try:
        while listener_thread.is_alive():
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("KeyboardInterrupt: stopping generator.")
    await generator.stop()

if __name__ == "__main__":
    asyncio.run(main())
