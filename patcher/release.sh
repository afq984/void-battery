#!/bin/bash
set -ex
mkdir -p ../web/nebuloch/data
cp out/release/{bases.json,stat_descriptions.json,words.json,passives.json,version.txt,fingerprint.txt} ../web/nebuloch/data/
