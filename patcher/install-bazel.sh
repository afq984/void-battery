#!/bin/bash
# Build Go and C++ patcher tools via Bazel and place them where main.sh expects.
#
# Replaces install.sh for the Bazel workflow. After running this, use main.sh
# as normal. The extract binary is a wrapper that delegates to `bazel run`.

set -eux

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$(dirname "$0")"

# Download external data (same as install.sh)
curl -o schema.min.json -fL https://github.com/poe-tool-dev/dat-schema/releases/download/latest/schema.min.json
curl -o scripts/ninja_syntax.py -fL https://github.com/ninja-build/ninja/raw/master/misc/ninja_syntax.py

# Python venv for genbuild.py/datrelease.py/statparse.py (same as install.sh)
virtualenv venv
venv/bin/python -m pip install tqdm

# Build all Bazel targets
bazel build //patcher/cmd/dat2jsonl //patcher/cmd/poepatcher //patcher/extract

# Copy Go binaries to bin/
mkdir -p bin
cp -f "$REPO_ROOT/bazel-bin/patcher/cmd/dat2jsonl/dat2jsonl_/dat2jsonl" bin/dat2jsonl
cp -f "$REPO_ROOT/bazel-bin/patcher/cmd/poepatcher/poepatcher_/poepatcher" bin/poepatcher

# Install extract wrapper so main.sh uses bazel run
mkdir -p extract/build
ln -sf ../../extract_bazel_wrapper.sh extract/build/extract
