#!/bin/bash

# SHARED CONSTANTS
. /root/drako/scripts/common/constants.env ORCHESTRATOR_SCRIPTS_PATH

ORCHESTRATOR_ID=$1
PROFILE=$2
AMOUNT_OF_AGENTS=$3
LOAD_MAIN_TRAINING=$4
HOURS_PER_TARGET=$5
TARGET_SOURCE=$6
TARGET_ID=$7
TRAINING_ID=$8
LEARNER_FAMILY=$9
LEARNER_NAME="${10}"

if [ -z "$ORCHESTRATOR_ID" ]; then
	echo "You need to set ORCHESTRATOR_ID!"
    exit 1
fi

if [ -z "$PROFILE" ]; then
	echo "You need to set PROFILE!"
    exit 1
fi

if [ -z "$AMOUNT_OF_AGENTS" ]; then
	echo "You need to set AMOUNT_OF_AGENTS!"
    exit 1
fi

if [ -z "$LOAD_MAIN_TRAINING" ]; then
	echo "You need to set LOAD_MAIN_TRAINING!"
    exit 1
fi

if [ -z "$HOURS_PER_TARGET" ]; then
	echo "You need to set HOURS_PER_TARGET!"
    exit 1
fi

if [ -z "$TARGET_SOURCE" ]; then
	echo "You need to set TARGET_SOURCE!"
    exit 1
fi

if [ -z "$TRAINING_ID" ]; then
	echo "You need to set TRAINING_ID!"
    exit 1
fi

if [ -z "$LEARNER_FAMILY" ]; then
	echo "You need to set LEARNER_FAMILY!"
    exit 1
fi

if [ -z "$LEARNER_NAME" ]; then
	echo "You need to set LEARNER_NAME!"
    exit 1
fi

echo "Try to kill orchestrator screen"
screen -X -S orchestrator quit

echo "Starting orchestrator.."
screen -S orchestrator -d -m;

COMMAND="python3 $ORCHESTRATOR_SCRIPTS_PATH/orchestrator.py --orchestrator_id $ORCHESTRATOR_ID --profile $PROFILE --amount_of_agents $AMOUNT_OF_AGENTS --load_main_training $LOAD_MAIN_TRAINING --hours_per_target $HOURS_PER_TARGET --target_source $TARGET_SOURCE --training_id $TRAINING_ID --learner_family $LEARNER_FAMILY --learner_name $LEARNER_NAME"

if [ ! -z "$TARGET_ID" ]; then
    COMMAND="${COMMAND} --target_id $TARGET_ID"
fi
echo $COMMAND

screen -r orchestrator -X stuff "${COMMAND}\n";