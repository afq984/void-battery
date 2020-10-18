FROM alpine:edge
RUN apk add --no-cache python3 python3-dev py3-virtualenv py3-brotli py3-cffi go build-base git cmake pkgconf libsodium-dev libunistring-dev ninja bash
COPY . /patcher/
WORKDIR /patcher
RUN bash install.sh
ARG UID=1000
ARG GID=1000
RUN addgroup -g $GID patcher
RUN adduser -G patcher -u $UID -D patcher
USER $UID:$GID
ENTRYPOINT bash
