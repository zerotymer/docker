#!/bin/sh
# https://hub.docker.com/r/grafana/grafana
mkdir -p data

docker run --detach \
        --name grafana \
        --restart always \
	--user $(id -u) \
	--env "GF_SECURITY_ADMIN_PASSWORD=password" \
        --env "GF_PLUGINS_PREINSTALL=grafana-clock-panel, grafana-simple-json-datasource" \
        --publish 3000:3000 \
	--volume "$PWD/data:/var/lib/grafana" \
        grafana/grafana-enterprise
