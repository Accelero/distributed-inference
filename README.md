# Distributed Inference Engine

Submission for Distributed AI Engineer - Coding Challenge.

## 📄 Third-Party Licenses

This project includes third-party software components. For details, see the [Third-Party Licenses](licenses/third_party_licenses.md) documentation.

## 🛠️ Installation

1. **Update WSL2 (if using Windows):**
    ```powershell
    wsl --update
    ```
2. **Start the Application:**
    ```powershell
    docker compose up -d
    ```

## 🏃 Running the App

- Open your web browser and navigate to [localhost:3000](http://localhost:3000) to access the dashboard.
- The app provides a simple text embedding service using SBERT.
- The gRPC API endpoint is available at `localhost:50050` (see `proto/public.proto` for the API definition).
- Use the provided test scripts to simulate requests and experiment with the system.

## 🧪 Running Test Scripts

Test scripts are located in the `./test` directory. They require Python 3.13 and use dependencies listed in `pyproject.toml`. The recommended way to manage dependencies is with [uv](https://docs.astral.sh/uv/getting-started/installation/):

1. **Install Python 3.13** (ensure it's available on your system).
2. **Install uv:**
    ```shell
    pip install uv
    # or follow the standalone installation instructions in the uv documentation
    ```
3. **Set up the test environment:**
    - Navigate to the `test` folder:
      ```shell
      cd test
      ```
    - Create a virtual environment and install dependencies:
      ```shell
      uv sync
      ```
4. **Run test scripts:**
    - Activate the virtual environment, or run scripts directly with uv:
      ```shell
      uv run ./name_of_script.py
      ```
    - For script usage information:
      ```shell
      uv run ./name_of_script.py -h
      ```

Performance metrics such as timeout rate and queue size are highly dependent on your machine's capabilities. Experiment with the test parameters to determine how many requests your system can handle and observe its behavior under overload conditions. The rate of failed or unfulfilled requests is strongly influenced by the client-defined timeout in the test scripts and the time required by the inference engine to process each request. When the queue stacks up and the timeout set by the client is too low, fail to fullfill rate quickly goes up to 100%.

**Notes:**
- No formal unit tests are provided. Instead, scripts are available to simulate traffic and experiment with the system.
- The traffic generator can simulate stochastic traffic loads. Adjust parameters in its constructor to experiment with different scenarios.
- Other scripts simulate worker loss, network latency, and packet loss. All scripts accept command-line parameters for flexible testing.
- **Container Restart Behavior:** After running the crash simulation scripts, containers may not automatically restart—even if `restart: always` is set in the Docker Compose file. This is likely due to the use of `SIGKILL` (or similar signals) to terminate containers, which can prevent Docker from performing a clean restart. Manual intervention may be required to restart affected containers.

## 🧑‍💻 Development & Debugging

A devcontainer setup is provided to streamline development and debugging:
- You can use the devcontainer as a drop-in replacement for a service and develop/debug in the loop.
- First, run `docker compose up -d` to start all services.
- In VS Code, use the command palette (`F1`) and select **Dev-Containers: Reopen in Container**. VS Code will spin up the devcontainer and connect you directly to it for development.

## ⚠️ Known Issues

- In the devcontainer, `uv` may fail to install the Python virtual environment and dependencies on the first startup after `docker compose up`. If this happens, rebuild the devcontainer (`F1` > **Dev-Containers: Rebuild Container**) and it should work. This issue is likely caused by a race condition when mounting the persisted venv volume.
- After running the crash simulation scripts, containers may not automatically restart—even if `restart: always` is set in the Docker Compose file. This is likely because terminating containers with `SIGKILL` (or similar signals) can prevent Docker from performing a clean restart. If this occurs, you may need to manually restart the affected containers.

## 🚀 Future Improvements & Roadmap

- **Request Cancellation:** Implement full propagation of request cancellation to workers. Currently, all requests are dispatched and processed even if the client cancels, resulting in wasted computation. Enabling cancellation would improve efficiency and resource utilization.
- **Decline Unserviceable Requests:** Proactively reject client requests with timeouts that are too short to be fulfilled. Estimate the required processing time based on the current queue size and average per-request processing time, and immediately decline requests that cannot be serviced within the client's deadline. This prevents wasted effort and improves system responsiveness under load.
- **Consistent Worker Identification:** Unify worker identification across the system. At present, workers are inconsistently identified by IP or container ID. Standardizing to a single, consistent worker ID (exported via health checks and used in logs) will improve traceability and maintainability.
- **Log Quality & Observability:** Enhance log structure and quality to better leverage the Grafana/Loki stack. This includes harmonizing log fields and tags, parsing fields on ingestion, and ensuring tracebacks are stored in the `exc_info` field rather than the message. Improved logs will make monitoring, debugging, and alerting more effective.
- **Exception Handling:** Refactor exception handling for clarity and robustness. Adopt a systematic approach: use custom exception classes where appropriate, ensure all functions have proper exception coverage, and follow best practices (e.g., only log exceptions when caught, not when raised). This will make the codebase more reliable and easier to maintain.
- **Object-Oriented Design:** Refactor to a more object-oriented architecture. As the project grows, encapsulating worker state, request batching, and related logic into classes will improve code readability, modularity, and extensibility.

---

This project was completed in one week as part of an assignment, alongside my full-time job. Given more time, I would focus on the above improvements to further enhance robustness, maintainability, and observability.