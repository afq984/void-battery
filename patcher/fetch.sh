#!/bin/bash
# Download schema and fetch game data. Run main.sh afterwards to process.

set -eux

cd "$(dirname "$0")"

curl -o schema.min.json -fL https://github.com/poe-tool-dev/dat-schema/releases/download/latest/schema.min.json

bazel run //patcher:fetch
