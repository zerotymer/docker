#!/bin/bash
# https://hub.docker.com/_/busybox
if [ "$#" -gt 0 ]; then 
    echo "----------------------"
    docker run -it --rm busybox:musl sh -c "$*"
    echo "----------------------"
    echo "BUSYBOX STOP"
else
    docker run -it --rm busybox:musl "busybox"

    echo ''
    echo ''
    echo "./busybox-run [COMMAND]"
fi
