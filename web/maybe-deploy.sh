#!/bin/bash
set -e

remote_fingerprint="$(curl --fail https://void-battery.appspot.com/pob/fingerprint)"
echo fingerprints:
echo "remote: $remote_fingerprint"

local_fingerprint="$(cat nebuloch/data/fingerprint.txt)"
echo " local: $local_fingerprint"

if [[ "$remote_fingerprint" == "$local_fingerprint" ]]
then
    echo "Fingerprint same, skip deployment"
else
    gcloud app deploy --stop-previous-version
fi
