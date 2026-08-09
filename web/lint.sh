#!/bin/bash
set -eux
pyflakes pobgen.py main.py nebuloch/ tests/ tools/
set +e
pycodestyle --ignore=E501 nebuloch/ tests/ tools/
pycodestyle --ignore=E501 main.py pobgen.py
