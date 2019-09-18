#!/bin/bash
set -eux
pyflakes main.py nebuloch/ tests/
set +e
pycodestyle --ignore=E501 nebuloch/ tests/
pycodestyle --ignore=E501 main.py
