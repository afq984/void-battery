#!/bin/bash

set -eux

mkdir -p out/release
mkdir -p out/extracted

bin/poepatcher \
	"PathOfExile.exe" \
	"Bundles2/_.index.bin" \
	"Bundles2/_Preload.bundle.bin" \
	"Bundles2/Data.dat.7.bundle.bin" \
	"Bundles2/Data.dat.C.bundle.bin" \
	"Bundles2/Data.dat.D.bundle.bin" \
	"Bundles2/Data.dat.E.bundle.bin" \
	"Bundles2/Data/Traditional Chinese.dat.2.bundle.bin" \
	"Bundles2/Data/Traditional Chinese.dat.6.bundle.bin" \
	"Bundles2/Data/Traditional Chinese.dat.7.bundle.bin" \
	"Bundles2/Data/Traditional Chinese.dat.9.bundle.bin" \
	"Bundles2/Data/Traditional Chinese.dat.B.bundle.bin"

venv/bin/python scripts/genbuild.py
venv/bin/python -m ninja
