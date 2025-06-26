# Set working directory to project root
Set-Location (Join-Path $PSScriptRoot '..')

# Set grpc_comp path
$GRPC_COMP_PATH = "proto/compiled"

if (-not (Test-Path $GRPC_COMP_PATH)) {
    New-Item -ItemType Directory -Path $GRPC_COMP_PATH | Out-Null
}

python -m grpc_tools.protoc -I. --python_out=$GRPC_COMP_PATH --grpc_python_out=$GRPC_COMP_PATH proto/inference.proto

# Copy the entire generated proto directory contents to coordinator, worker, and test
Copy-Item -Path "$GRPC_COMP_PATH/proto/*" -Destination "coordinator/app/proto" -Recurse -Force
Copy-Item -Path "$GRPC_COMP_PATH/proto/*" -Destination "worker/app/proto" -Recurse -Force
Copy-Item -Path "$GRPC_COMP_PATH/proto/*" -Destination "test/proto" -Recurse -Force

# Delete grpc_comp_path
Remove-Item -Path "$GRPC_COMP_PATH" -Recurse -Force
