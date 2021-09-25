#!/bin/bash
set -ex

mkdir -p out/
curl -o out/schema.min.json -fL https://github.com/poe-tool-dev/dat-schema/releases/download/latest/schema.min.json

virtualenv venv
venv/bin/python -m pip install tqdm

go build -o bin/ ./cmd/...
