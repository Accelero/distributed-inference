#!/bin/bash

# Set working directory to project root
cd "$(dirname "$0")/.."

# Set grpc_comp path
GRPC_COMP_PATH="coordinator/app"

mkdir -p "$GRPC_COMP_PATH"

python -m grpc_tools.protoc -I. --python_out="$GRPC_COMP_PATH" --grpc_python_out="$GRPC_COMP_PATH" proto/inference.proto