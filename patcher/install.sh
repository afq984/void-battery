#!/bin/bash
set -ex

curl -o schema.min.json -fL https://github.com/poe-tool-dev/dat-schema/releases/download/latest/schema.min.json

virtualenv venv
venv/bin/python -m pip install tqdm ninja

go build -o bin/ ./cmd/...
