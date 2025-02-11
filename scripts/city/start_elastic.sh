#!/bin/bash

docker pull docker.elastic.co/elasticsearch/elasticsearch:7.13.2
docker run -d --name elastic01 --net host -v /elasticsearch/data:/usr/share/elasticsearch/data -e "discovery.type=single-node" -e ES_JAVA_OPTS="-Xms128g -Xmx128g" docker.elastic.co/elasticsearch/elasticsearch:7.13.2

docker pull docker.elastic.co/kibana/kibana:7.13.2
docker run -d --name kib01 --net host -e "ELASTICSEARCH_REQUESTTIMEOUT=300000" -e "ELASTICSEARCH_HOSTS=http://localhost:9200" docker.elastic.co/kibana/kibana:7.13.2
# -p 5601:5601