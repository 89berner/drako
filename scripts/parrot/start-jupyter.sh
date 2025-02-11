#!/bin/bash

COMMAND="docker container rm -f $(docker container ls -aq --filter name=jupyter)"
echo $COMMAND
$COMMAND

COMMAND="docker build -t jupyter -f /root/drako/services/main/training/learner/Dockerfile.jupyter services/main/"
echo $COMMAND
$COMMAND

# --gpus all
COMMAND="docker run --name jupyter -d -v /root/drako/services/main/lib:/app/lib -v /root/drako/services/main/shared:/app/shared -v /share:/share -v /shared/notebooks:/app/notebooks/ --network host -t jupyter"
echo $COMMAND
CONTAINER_ID=$($COMMAND)
docker logs -f $CONTAINER_ID