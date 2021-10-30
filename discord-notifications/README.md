## Deploy

```
gcloud builds submit .
```

## Config

```
gcloud projects add-iam-policy-binding void-battery \
   --member=serviceAccount:service-640057552959@gcp-sa-pubsub.iam.gserviceaccount.com \
   --role=roles/iam.serviceAccountTokenCreator

gcloud iam service-accounts create cloud-run-pubsub-invoker \
  --display-name "Cloud Run Pub/Sub Invoker"

gcloud pubsub topics create cloud-builds

gcloud pubsub subscriptions create cloud-builds-subscriber \
   --topic=cloud-builds \
   --push-endpoint=https://discord-notifier-un6wi6sega-de.a.run.app \
   --push-auth-service-account=cloud-run-pubsub-invoker@void-battery.iam.gserviceaccount.com
```
