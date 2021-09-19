#!/bin/bash
set -ex

# pypoe
virtualenv -p python3 venv --system-site-packages
venv/bin/pip install git+https://github.com/spadea96334/PyPoE#egg=PyPoE[cli] tqdm

# ooz
rm -rf ooz
git clone --depth=1 https://github.com/zao/ooz.git
sed -i s/TEMP_FAILURE_RETRY//g ooz/libpoe/poe/util/random_access_file.cpp  # for musl
mkdir ooz/build
cmake -S ooz -B ooz/build -G Ninja
ninja -C ooz/build

# poepatcher
go build -o bin/ ./cmd/...
