#!/bin/bash
# Set working directory to project root
dirname=$(dirname "$0")
cd "$dirname/.."

GRPC_COMP_PATH="proto/compiled"

# Create compiled directory if it doesn't exist
mkdir -p "$GRPC_COMP_PATH"

python -m grpc_tools.protoc -I. --python_out="$GRPC_COMP_PATH" --grpc_python_out="$GRPC_COMP_PATH" proto/public.proto
python -m grpc_tools.protoc -I. --python_out="$GRPC_COMP_PATH" --grpc_python_out="$GRPC_COMP_PATH" proto/private.proto

# Force create destination folders
mkdir -p coordinator/app/proto
mkdir -p worker/app/proto
mkdir -p test/proto

# Copy all generated files to coordinator, worker, and test proto folders
cp -r $GRPC_COMP_PATH/* coordinator/app/proto/
cp -r $GRPC_COMP_PATH/* worker/app/proto/
cp -r $GRPC_COMP_PATH/* test/proto/

# Delete grpc_comp_path
rm -rf "$GRPC_COMP_PATH"
