# Set working directory to project root
Set-Location (Join-Path $PSScriptRoot '..')

# Set grpc_comp path
$GRPC_COMP_PATH = "test"

if (-not (Test-Path $GRPC_COMP_PATH)) {
    New-Item -ItemType Directory -Path $GRPC_COMP_PATH | Out-Null
}

python -m grpc_tools.protoc -I. --python_out=$GRPC_COMP_PATH --grpc_python_out=$GRPC_COMP_PATH proto/inference.proto
