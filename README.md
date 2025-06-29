# Distributed Inference Engine

Submission for Distributed AI Engineer - Coding Challenge.

## Future Improvements & Roadmap

- Implement cancellation of timed out requests for workers, so that the queue quickly empties when the requests stop and no unnecessary work is done.
- Make worker ID consistent. Make workers export their ID via health checks and also add log tags with worker ID.

---

**Third-Party Licenses:**

This project includes third-party software components. For details, see the [Third-Party Licenses](licenses/third_party_licenses.md) documentation.

## Installation

1. Make sure WSL2 is up to date.
    ```powershell
    wsl --update
    ```
2. Navigate to project root and execute
    ```powershell
    docker compose up -d
    ```
3. Open Webbrowser on localhost:3000

## Running Test Scripts

The test scripts in ./tests have dependencies and were developed with Python 3.13. Dependencies are listed in the pyproject.toml and can be easily installed and managed with uv. Make sure you have Python 3.13 installed and install uv via pip install uv or install the standalone version of uv and let uv this way handle the download of the Python 3.13 interpreter. The installation of standalone uv is descriped on the [official documentation](https://docs.astral.sh/uv/getting-started/installation/).

After successful installation and making sure uv is on PATH, navigate to the tests folder and execute there uv sync to create a a virtual env in tests/.venv. The scripts can then be executed by activating the virtual env or running scripts via uv run ...