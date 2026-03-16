#!/bin/sh
# https://hub.docker.com/_/nginx

mkdir -p data
docker run --detach \
        --name nginx \
        --restart always \
        --publish 80:80 \
        --env NGINX_HOST='example.com' \
        --env NGINX_PORT=80 \
	--volume $(pwd)/data:/usr/share/nginx/html:ro \
        nginx:stable-alpine
