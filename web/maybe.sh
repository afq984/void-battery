#!/bin/bash
set -e

container=gcr.io/void-battery/v0

remote_fingerprint="$(curl -s --fail https://void-battery.afq984.org/pob/fingerprint)"
echo fingerprints:
echo "remote: $remote_fingerprint"

local_fingerprint="$(docker run --rm $container cat nebuloch/data/fingerprint.txt)"
echo " local: $local_fingerprint"

remote_version="$(curl -s --fail https://void-battery.afq984.org/version)"
echo versions:
echo "remote: $remote_version"

local_version="$(git rev-parse --verify HEAD)"
echo " local: $local_version"

if [[ "$remote_fingerprint" == "$local_fingerprint" && "$remote_version" == "$local_version" ]]
then
    echo "Fingerprint and version same, command skipped"
else
    exec "$@"
fi
