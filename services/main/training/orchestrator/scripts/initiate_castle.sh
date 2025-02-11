#!/bin/bash

# bash initiate_castle.sh GoExplore NNRecommendationTester 2 1 EXPLORE_AND_TRAIN 

# SHARED CONSTANTS
. /root/drako/scripts/common/constants.env ORCHESTRATOR_SCRIPTS_PATH AWS_REGION AWS_ACCOUNT_ID

AGENT_NAME=$1
TESTER_NAME=$2
SCALE=$3
TRAINING_ID=$4
PROFILE=$5
LEARNER_NAME=$6
LOAD_MAIN_TRAINING=$7
CONTINUE_FROM_LATEST_POINT=$8
FORCE_CPU="${9}"
TARGET_SOURCE="${10}"

echo "Try to kill agents screen"
screen -X -S agents quit

echo "Starting agents.."
screen -S agents -d -m;

if [ -z "$LEARNER_NAME" ]; then
	LEARNER_NAME="False"
fi

if [ -z "$LOAD_MAIN_TRAINING" ]; then
	LOAD_MAIN_TRAINING="False"
fi

if [ -z "$CONTINUE_FROM_LATEST_POINT" ]; then
	CONTINUE_FROM_LATEST_POINT="False"
fi

if [ -z "$FORCE_CPU" ]; then
	FORCE_CPU="False"
fi

# FIRST LETS LOGIN TO AWS
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

screen -r agents -X stuff "python3 $ORCHESTRATOR_SCRIPTS_PATH/initiate_castle.py -a $AGENT_NAME -t $TESTER_NAME -s $SCALE -i $TRAINING_ID -p $PROFILE -l $LEARNER_NAME -m $LOAD_MAIN_TRAINING -c $CONTINUE_FROM_LATEST_POINT -u $FORCE_CPU -g $TARGET_SOURCE -b build_and_run\n";
echo "Finished starting SCREEN agent FOR initiate_castle!"