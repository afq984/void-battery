set -ex
apk add --no-cache python3 py3-virtualenv go build-base git curl bash samurai
./install.sh
./main.sh
