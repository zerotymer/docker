#!/bin/sh
# https://hub.docker.com/r/nginx/nginx-prometheus-exporter

mkdir -p data
docker run --detach \
        --name nginx-exporter \
        --restart always \
        --publish 9113:9113 \
        nginx/nginx-prometheus-exporter \
        --nginx.scrape-uri=http://192.168.29.70:8080/nginx_status
