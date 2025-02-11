#!/bin/bash

echo '### STEP 0 - LOADING CONSTANTS'
. /root/drako/scripts/common/constants.env NETWORKS_FOLDER_PATH LOGS_FOLDER_PATH DRAKO_FOLDER_PATH MAIN_SERVICE_PATH AWS_REGION AWS_ACCOUNT_ID WEB_DNS
. /root/drako/scripts/common/constants.env DRAGON_DB_PORT DRAGON_PROD_DNS DRAGON_STAGING_DB_IP STATIC_BUCKET_NAME STATIC_TEMPLATE_LOCATION DRAGON_DB_USER DRAGON_DB_PWD ASSISTANT_DB_NAME
. /root/drako/scripts/common/constants.env ASSISTANT_SAMPLE_TABLE DRAGON_PROD_DB_NAME DRAGON_TEST_DB_NAME DRAGON_PROD_SAMPLE_TABLE WEB_FOLDER_PATH PREDICTION_FOLDER_PATH

build_and_upload_chatbot_js() {
	echo "Moving to the chatbot directory"
	cd $WEB_FOLDER_PATH/resources/chatbot-source/
	echo "Running build script"
	bash build.sh
	echo "Copying file to folder"
	cp $WEB_FOLDER_PATH/resources/chatbot-source/dist/drako.chatbot.js $WEB_FOLDER_PATH/resources/Robogard-final/js/drako.chatbot.js
	# echo "Upload to S3 JS"
	# aws s3 cp $WEB_FOLDER_PATH/resources/chatbot-source/dist/drako.chatbot.js s3://$STATIC_BUCKET_NAME/js/drako.chatbot.js
	echo "Going back"
	cd -
}

pull_and_run_container_in_web_instance() {
	echo "Copy script to ec2"
	scp -o StrictHostKeyChecking=no -i $DRAKO_FOLDER_PATH/.keys/id_rsa $WEB_FOLDER_PATH/scripts/pull_and_run.sh ubuntu@$WEB_DNS:/home/ubuntu/pull_and_run.sh

	echo "Execute script"
	ssh -o StrictHostKeyChecking=no -i $DRAKO_FOLDER_PATH/.keys/id_rsa ubuntu@$WEB_DNS "sudo bash /home/ubuntu/pull_and_run.sh $AWS_REGION $AWS_ACCOUNT_ID"
}

build_web_image() {
	docker build -t web -f $WEB_FOLDER_PATH/Dockerfile.web $MAIN_SERVICE_PATH;
	echo "Tag the web and prediciton images.."
	WEB_IMAGE=$(docker images web|tail -n1| awk '{ print $3 }')
	docker tag $WEB_IMAGE $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/web:latest
	docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/web:latest
}

build_web_prediction_image() {
	docker build -t web_prediction -f $PREDICTION_FOLDER_PATH/Dockerfile.web_prediction $MAIN_SERVICE_PATH;
	PREDICTION_IMAGE=$(docker images web_prediction|tail -n1| awk '{ print $3 }')
	docker tag $PREDICTION_IMAGE $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/web_prediction:latest
	docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/web_prediction:latest
}

login_to_aws_ecr() {
	aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com
}

configure_assistant() {
	RESULT=$(mysql -P $DRAGON_DB_PORT --user=$DRAGON_DB_USER --password=$DRAGON_DB_PWD -h $DRAGON_PROD_DNS $ASSISTANT_DB_NAME -e 'SHOW TABLES;' |grep -o $ASSISTANT_SAMPLE_TABLE)
	if [ "$RESULT" == "$ASSISTANT_SAMPLE_TABLE" ]; then
		echo "Database $ASSISTANT_DB_NAME is already present"
	else
		echo "Now creating assistant mysql database and table on the new RDS instance if it does not exist"
		mysql -P $DRAGON_DB_PORT -h $DRAGON_PROD_DNS --user=$DRAGON_DB_USER --password=$DRAGON_DB_PWD -e "CREATE DATABASE $ASSISTANT_DB_NAME";
		mysql -P $DRAGON_DB_PORT -h $DRAGON_PROD_DNS --user=$DRAGON_DB_USER --password=$DRAGON_DB_PWD $ASSISTANT_DB_NAME < $DRAKO_FOLDER_PATH/resources/assistant_latest.sql;
	fi
}

configure_dragon() {
	RESULT=$(mysql -P $DRAGON_DB_PORT -h $DRAGON_PROD_DNS --user=$DRAGON_DB_USER --password=$DRAGON_DB_PWD $DRAGON_PROD_DB_NAME -e 'SHOW TABLES;' |grep -o $DRAGON_PROD_SAMPLE_TABLE)
	if [ "$RESULT" == "$DRAGON_PROD_SAMPLE_TABLE" ]; then
		echo "Database $DRAGON_PROD_DB_NAME is already present"
	else
		echo "Now creating drako mysql database on the new RDS instance if it does not exist from the latest backup"
		echo "WARNING: ADD THIS SECTION!!!"
		echo "WARNING: ADD THIS SECTION!!!"
		echo "WARNING: ADD THIS SECTION!!!"

		sleep 300

		# TODO: ADD INSERT LATEST DRAGON TO DB

		# mysql --user=$DRAGON_DB_USER --password=$DRAGON_DB_PWD -h $DRAGON_PROD_DNS -e "CREATE DATABASE $DRAGON_PROD_DB_NAME";
		# TEMP_MYSQL_DUMP_FILE="/tmp/mysql_dump_$RANDOM"
		# echo "Dumping current dragon DB without tables with lots of data to $TEMP_MYSQL_DUMP_FILE"
		# mysqldump -h $DRAGON_STAGING_DB_IP -u$DRAGON_DB_USER -p$DRAGON_DB_PWD --no-data --ignore-table=$DRAGON_PROD_DB_NAME.training --ignore-table=$DRAGON_PROD_DB_NAME.training_game dragon > $TEMP_MYSQL_DUMP_FILE
		# mysqldump -h $DRAGON_STAGING_DB_IP -u$DRAGON_DB_USER -p$DRAGON_DB_PWD $DRAGON_PROD_DB_NAME training training_game >> $TEMP_MYSQL_DUMP_FILE

		# # Cleaning the DEFINER due to https://aws.amazon.com/premiumsupport/knowledge-center/definer-error-mysqldump/
		# sed -i -e 's/DEFINER=`root`@`192.168.2.%`//g' $TEMP_MYSQL_DUMP_FILE

		# echo "Now uploading dump to the RDS DB"
		# mysql -h $DRAGON_PROD_DNS --user=$DRAGON_DB_USER --password=$DRAGON_DB_PWD $DRAGON_PROD_DB_NAME < $TEMP_MYSQL_DUMP_FILE

		# echo "Now doing the same for the test database"
		# mysql --user=$DRAGON_DB_USER --password=$DRAGON_DB_PWD -h $DRAGON_PROD_DNS -e "CREATE DATABASE $DRAGON_TEST_DB_NAME";
		# mysqldump -h $DRAGON_STAGING_DB_IP -u$DRAGON_DB_USER -p$DRAGON_DB_PWD --no-data > $TEMP_MYSQL_DUMP_FILE
		# sed -i -e 's/DEFINER=`root`@`192.168.2.%`//g' $TEMP_MYSQL_DUMP_FILE
		# mysql -h $DRAGON_PROD_DNS --user=$DRAGON_DB_USER --password=$DRAGON_DB_PWD $DRAGON_TEST_DB_NAME < $TEMP_MYSQL_DUMP_FILE
	fi
}

MODE=$1

if [[ "$MODE" != "only_web" ]]; then
	echo '### STEP 1.1 - COPYING STATIC FILES'

	# echo "First of all, lets upload the s3 folder in case there were changes"
	# aws s3 sync $STATIC_TEMPLATE_LOCATION s3://$STATIC_BUCKET_NAME/

	echo "### STEP 1.2 BUILDING AND SYNCING THE CHATBOT JS"
	build_and_upload_chatbot_js 

	echo '### STEP 2 - Configure NEW MYSQL DATABASE AND TEST DATABASE'
	echo "Configuring Assistant DB"
	configure_assistant

	echo "Configuring Dragon DB"
	configure_dragon
fi

echo '### STEP 3 - BUILD DOCKER IMAGES'

echo "First authenticate to aws docker registry for account $AWS_ACCOUNT_ID and region $AWS_REGION"
login_to_aws_ecr

echo "Building web image"
build_web_image

echo "Building prediction image"
build_web_prediction_image

echo '### STEP 4 - Prepare EC2 INSTANCE'

pull_and_run_container_in_web_instance
