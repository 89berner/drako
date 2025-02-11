#!/bin/bash

set -e

. /root/drako/scripts/common/constants.env AWS_REGION AWS_ACCOUNT_ID

push_image () {
    IMAGE_NAME=$1
    IMAGE_ID=$(docker images $IMAGE_NAME |awk '{ print $3 }'|tail -1)
    TIMESTAMP=$(date +%Y%m%d%H%M%S)  

    docker tag $IMAGE_ID $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$IMAGE_NAME:$TIMESTAMP
    docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$IMAGE_NAME:$TIMESTAMP
}

aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

push_image "agent-base"
push_image "agent"
push_image "training_prediction"
push_image "health"
push_image "learner"
push_image "mysql-drako"
