#!/bin/bash

AWS_REGION=$1
AWS_ACCOUNT_ID=$2

echo "Cleaning logs"
rm /share/logs/*

RES=$(aws ecr get-login --no-include-email --region $AWS_REGION)
echo $($RES) # Run the script to login

echo "Stopping all docker containers"
docker stop $(docker ps -aq) && docker container rm -f $(docker container ls -aq)

echo "Starting web_prediction container.."
docker pull $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/web_prediction:latest
docker run -d --name web_prediction -v /share:/share --network="host" -t $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/web_prediction:latest

docker pull $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/web:latest
docker run -d --name web --network="host" -it -t $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/web:latest

#echo "Removing all docker resources not being used.." # this should mean only unused images/containers
#docker system prune -a -f