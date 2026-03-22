FROM gcr.io/bazel-public/bazel:8.6.0 AS patcher

WORKDIR /build
COPY --chown=ubuntu . /build
RUN cd patcher && bash fetch.sh
RUN cd patcher && bash main.sh


FROM docker.io/alpine:latest as web

RUN apk add --no-cache python3 py3-flask py3-lxml py3-gunicorn

ENV PYTHONUNBUFFERED True

WORKDIR /web
COPY web /web
COPY --from=patcher /build/patcher/out/release /web/nebuloch/data

CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 main:app
