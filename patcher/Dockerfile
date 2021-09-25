FROM docker.io/alpine:latest
RUN apk add --no-cache python3 py3-virtualenv go build-base git curl bash
COPY . /patcher/
WORKDIR /patcher
RUN bash install.sh
CMD ["bash"]
