FROM docker.io/alpine:latest
RUN apk add --no-cache python3 python3-dev py3-virtualenv py3-brotli py3-cffi go build-base git cmake pkgconf libsodium-dev libunistring-dev ninja bash
COPY . /patcher/
WORKDIR /patcher
RUN bash install.sh
CMD ["bash"]
