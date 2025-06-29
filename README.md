# Distributed Inference Engine

Submission for Distributed AI Engineer - Coding Challenge.

## 📄 Third-Party Licenses

This project includes third-party software components. For details, see the [Third-Party Licenses](licenses/third_party_licenses.md) documentation.

---

## 🛠️ Installation

1. **Update WSL2 (if using Windows):**
    ```powershell
    wsl --update
    ```
2. **Start the Application:**
    ```powershell
    docker compose up -d
    ```

---

## 🏃 Running the App

- Open your web browser and navigate to [localhost:3000](http://localhost:3000) to access the dashboard.
- The app provides a simple text embedding service using SBERT.
- The gRPC API endpoint is available at `localhost:50050`. The API is defined in `proto/public.proto`.
- Use the provided test scripts to simulate requests and experiment with the system.

---

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
      uv run name_of_script.py -h
      ```

**Note:**
- No formal unit tests are provided. Instead, scripts are available to simulate traffic and experiment with the system.
- The traffic generator can simulate stochastic traffic loads. Adjust parameters in its constructor to experiment with different scenarios.
- Other scripts simulate worker loss, network latency, and packet loss. All scripts accept command-line parameters for flexible testing.

## 🚀 Future Improvements & Roadmap

- **Request Cancellation:** Implement cancellation of timed-out requests for workers, ensuring the queue is quickly cleared when requests stop and preventing unnecessary computation.
- **Consistent Worker IDs:** Standardize worker IDs. Workers should export their ID via health checks and include the worker ID in all log entries for better traceability.