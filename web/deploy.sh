#!/bin/bash
set -ex
gcloud run deploy v0 \
    --project=void-battery \
    --image=gcr.io/void-battery/v0 \
    --max-instances=1 --platform=managed \
    --allow-unauthenticated \
    --region=asia-east1 \
    --set-env-vars=VOID_BATTERY_UPDATED=`TZ=CST-8 date +%Y%m%dt%H%M%S` \
    --set-env-vars=VOID_BATTERY_VERSION=`git rev-parse --verify HEAD`
