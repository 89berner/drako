#!/bin/bash

LOCAL_PATH="/Users/juanberner/Raen/projects/drako/services/lawliet";
REMOTE_PATH="/root/drako/services/lawliet";

run_command () {
	COMMAND=$1;
	echo $COMMAND;
	$COMMAND;
}


DATA_PATH="data";
SCREENSHOTS_PATH="screenshots";
LOGS_PATH="logs";

run_command "rm -rf $LOCAL_PATH/$DATA_PATH/*"
run_command "scp -C -r -i .keys/id_rsa root@192.168.2.11:$REMOTE_PATH/$DATA_PATH/ $LOCAL_PATH/"

run_command "rm -rf $LOCAL_PATH/$SCREENSHOTS_PATH/*"
run_command "scp -C -r -i .keys/id_rsa root@192.168.2.11:$REMOTE_PATH/$SCREENSHOTS_PATH/ $LOCAL_PATH/"

run_command "rm -rf $LOCAL_PATH/$LOGS_PATH/*"
run_command "scp -C -r -i .keys/id_rsa root@192.168.2.11:$REMOTE_PATH/$LOGS_PATH/ $LOCAL_PATH/"

echo "Opening Sublime"
subl -n -a $LOCAL_PATH/data/ $LOCAL_PATH/logs/ $LOCAL_PATH/screenshots/