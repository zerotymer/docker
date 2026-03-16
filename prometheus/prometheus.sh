#!/bin/sh
# https://hub.docker.com/r/prom/prometheus/

docker run --detach \
        --name prometheus \
        --restart always \
        --publish 9090:9090 \
	--volume $(pwd)/config.yml:/etc/prometheus/prometheus.yml:ro \
        prom/prometheus
