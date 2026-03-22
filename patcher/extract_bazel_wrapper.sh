#!/bin/bash
# Drop-in replacement for extract/build/extract that uses the Bazel-built binary.
#
# Usage: symlink or copy this to extract/build/extract, then run main.sh as normal.
#   ln -sf ../../extract_bazel_wrapper.sh extract/build/extract
#
# The script delegates to `bazel run --run_in_cwd` so that:
# - Runfiles are set up (liblibooz.so is found automatically)
# - The working directory is preserved (genbuild.py/ninja paths work)
# - The environment matches what the eventual full Bazel build will use

exec bazel run --run_in_cwd --ui_event_filters=-info,-stdout,-stderr \
    //patcher/extract:extract -- "$@"
