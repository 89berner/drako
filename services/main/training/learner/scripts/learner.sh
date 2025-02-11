#!/bin/bash

echo "LEARNER_NAME=$LEARNER_NAME";
echo "GAME_TYPE=$GAME_TYPE";
echo "TRAINING_ID=$TRAINING_ID";
echo "LOAD_MAIN_TRAINING=$LOAD_MAIN_TRAINING";
echo "PROFILE=$PROFILE";
echo "CONTINUE=$CONTINUE"
echo "FORCE_CPU=$FORCE_CPU"

COMMAND="python3 learner.py --log-level=2 --learner_name=$LEARNER_NAME --game_type=$GAME_TYPE --training_id=$TRAINING_ID --load_main_training=$LOAD_MAIN_TRAINING --profile=$PROFILE --continue_from_latest_point=$CONTINUE --force_cpu=$FORCE_CPU"
echo $COMMAND
$COMMAND