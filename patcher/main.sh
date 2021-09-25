#!/bin/bash

set -eux

mkdir -p out/release
mkdir -p out/extracted

bin/poepatcher \
	"PathOfExile.exe" \
	"PathOfExile_x64.exe" \
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

bin/extract --ggpkd=Content.ggpk.d/latest --out=out/extracted/stat_descriptions.txt \
	--path=Metadata/StatDescriptions/stat_descriptions.txt


dat2json() {
	bin/extract --ggpkd=Content.ggpk.d/latest --path="$2" --out="$3.dat"
	bin/dat2jsonl --dat="$3.dat" --table-name="$1" --schema=schema.min.json > "$3.jsonl"
}

datfiles=(BaseItemTypes ActiveSkills PassiveSkills SkillGems Words)
for datfile in "${datfiles[@]}"
do
	dat2json "$datfile" "Data/$datfile.dat" "out/extracted/$datfile.en"
	dat2json "$datfile" "Data/Traditional Chinese/$datfile.dat" "out/extracted/$datfile.tc"
done

venv/bin/python scripts/datrelease.py
venv/bin/python scripts/statparse.py out/extracted/stat_descriptions.txt > out/release/stat_descriptions.json
venv/bin/python scripts/charversion.py Content.ggpk.d/latest | tee out/release/version.txt
venv/bin/python scripts/fingerprint.py out/release/{bases.json,stat_descriptions.json,words.json,passives.json,version.txt} | tee out/release/fingerprint.txt
