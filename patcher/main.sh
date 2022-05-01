#!/bin/bash

set -eux

mkdir -p out/release
mkdir -p out/extracted

venv/bin/python scripts/genbuild.py
ninja
