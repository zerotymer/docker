#!/bin/bash
# https://hub.docker.com/_/busybox
TEMP_FOLDER="tmp"
#rm -rf "$(pwd)/$TEMP_FOLDER/*"
mkdir -p "$(pwd)/$TEMP_FOLDER"

docker run -it --rm --mount type=bind,source=$(pwd)/$TEMP_FOLDER,target=/tmp busybox:musl
