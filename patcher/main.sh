#!/bin/bash

set -eux

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

bazel build //patcher/pipeline:release \
  --override_repository=gamedata+="$REPO_ROOT/patcher/Content.ggpk.d/latest"

mkdir -p out/release
tar xf "$REPO_ROOT/bazel-bin/patcher/pipeline/release.tar" -C out/release/
