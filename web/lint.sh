#!/bin/bash
set -eux
pyflakes nebuloch/ tests/
python2 -m pyflakes main.py
set +e
pycodestyle --ignore=E501 nebuloch/ tests/
pycodestyle --ignore=E501 main.py
