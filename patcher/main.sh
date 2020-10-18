#!/bin/bash

set -eux

mkdir -p out/release
mkdir -p out/extracted

poepatcher/poepatcher \
	"PathOfExile.exe" \
	"PathOfExile_x64.exe" \
	"Bundles2/_.index.bin" \
	"Bundles2/_Preload.bundle.bin" \
	"Bundles2/Data.dat.bundle.bin" \
	"Bundles2/Data.dat_4.bundle.bin" \
	"Bundles2/Data/Traditional Chinese.dat.bundle.bin" \
	"Bundles2/Data/Traditional Chinese.dat_2.bundle.bin" \
	"Bundles2/Data/Traditional Chinese.dat_3.bundle.bin"

venv/bin/python scripts/extract.py \
	"Metadata/StatDescriptions/stat_descriptions.txt"

datfiles=(BaseItemTypes ActiveSkills PassiveSkills SkillGems Words.dat)
venv/bin/python scripts/exporter.py dat json --files "${datfiles[@]}" -lang 'English' out/extracted/dat.en.json
venv/bin/python scripts/exporter.py dat json --files "${datfiles[@]}" -lang 'Traditional Chinese' out/extracted/dat.tc.json

venv/bin/python scripts/datrelease.py
venv/bin/python scripts/statparse.py out/extracted/stat_descriptions.txt > out/release/stat_descriptions.json
venv/bin/python scripts/charversion.py Content.ggpk.d/latest | tee out/release/version.txt
