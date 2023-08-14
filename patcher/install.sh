#!/bin/bash
set -ex

curl -o schema.min.json -fL https://github.com/poe-tool-dev/dat-schema/releases/download/latest/schema.min.json
curl -o scripts/ninja_syntax.py -fL https://github.com/ninja-build/ninja/raw/master/misc/ninja_syntax.py

virtualenv venv
venv/bin/python -m pip install tqdm

go build -o bin/ ./cmd/...

meson setup --wipe --optimization=2 extract/build extract
ninja -C extract/build
