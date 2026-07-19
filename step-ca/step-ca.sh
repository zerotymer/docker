#!/bin/sh
# https://hub.docker.com/r/smallstep/step-ca

mkdir -p data
docker run --detach \
        --name step-ca \
        --restart unless-stopped \
        --publish 9000:9000 \
	--volume "$(pwd)/data:/home/step" \
        smallstep/step-ca
