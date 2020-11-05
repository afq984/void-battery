#!/bin/bash
set -eux
pyflakes pobgen.py main.py nebuloch/ tests/
set +e
pycodestyle --ignore=E501 nebuloch/ tests/
pycodestyle --ignore=E501 main.py pobgen.py
