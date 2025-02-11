#!/bin/bash

echo "First kill agents screen"
screen -X -S agents quit
echo "Now delete all containers"
docker container rm -f $(docker ps -a|egrep 'agent-'|cut -d ' ' -f1)