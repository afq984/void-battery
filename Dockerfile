FROM docker.io/alpine:latest AS patcher

WORKDIR /patcher
COPY patcher /patcher
RUN apk add --no-cache python3 py3-virtualenv go build-base git curl bash samurai
RUN ./install.sh
RUN ./main.sh


FROM docker.io/alpine:latest as web

RUN apk add --no-cache python3 py3-flask py3-lxml py3-gunicorn

ENV PYTHONUNBUFFERED True

WORKDIR /web
COPY web /web
COPY --from=patcher /patcher/out/release /web/nebuloch/data

CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 main:app
