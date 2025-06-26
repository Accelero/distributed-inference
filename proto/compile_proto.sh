#!/bin/bash
# Set working directory to project root
dirname=$(dirname "$0")
cd "$dirname/.."

# Set grpc_comp path
grpc_comp_path="proto/compiled"

mkdir -p "$grpc_comp_path"

python -m grpc_tools.protoc -I. --python_out="$grpc_comp_path" --grpc_python_out="$grpc_comp_path" proto/inference.proto

# Copy the entire generated proto directory contents to coordinator, worker, and test
cp -r $grpc_comp_path/proto/* coordinator/app/proto/
cp -r $grpc_comp_path/proto/* worker/app/proto/
cp -r $grpc_comp_path/proto/* test/proto/

# Delete grpc_comp_path
rm -rf "$grpc_comp_path"
