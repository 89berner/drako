# This script is supposed to be ran by selecting a training_game_id in PROD as MAIN FOR ITS GAME TYPE

import argparse
import os
import shutil
import boto3

import sys
sys.path.append("/root/drako/services/main/")

from lib.Common.Utils.Db import Db
import lib.Common.Utils.Constants as Constants
import lib.Common.Utils.Log as Log

import lib.Training.Trainer.Common as Common
import lib.Common.Utils            as Utils

argparser = argparse.ArgumentParser(description='Use set_main_training_game.py from command line')
argparser.add_argument('--training_game_id',  dest='training_game_id',  type=int,            help='specify training_game_id to set as main', required=True)
argparser.add_argument('--upload_debug_data', dest='upload_debug_data', type=Utils.str2bool, help='upload debug data of training', default=False)

s3  = boto3.resource('s3')
import logging
logging.getLogger('boto3').setLevel(logging.CRITICAL)
logging.getLogger('s3transfer').setLevel(logging.CRITICAL)

def restart_ec2_web_instance():
    import subprocess

    command_to_execute  = "sudo docker restart web_prediction"
    ssh_command_wrapper = f"timeout -s SIGKILL 120 ssh -oStrictHostKeyChecking=no -i {Constants.DRAKO_FOLDER_PATH}/.keys/id_rsa ubuntu@{Constants.WEB_DNS} '{command_to_execute}';echo 'FINISHED';"

    output = subprocess.check_output(ssh_command_wrapper, stderr=subprocess.STDOUT, shell=True)
    Log.logger.info(output)

    return output

def get_data_for_training_game_id(prod_connection, training_game_id):
    query   = "SELECT training_id, game_type FROM training_game WHERE training_game_id=%s"
    results = prod_connection.query(query, (training_game_id,))
    if len(results) == 0:
        raise ValueError(f"I can't find the training_game_id {training_game_id}")

    return results[0]

def get_game_type_for_training_game_id(prod_connection, training_game_id):
    return get_data_for_training_game_id(prod_connection, training_game_id)['game_type']

def get_training_id_for_training_game_id(prod_connection, training_game_id):
    return get_data_for_training_game_id(prod_connection, training_game_id)['training_id']

def set_main_training(prod_connection, training_game_id):
    # GET THE GAME TYPE OF THE TRAINING_GAME_ID
    game_type = get_game_type_for_training_game_id(prod_connection, training_game_id)

    prod_connection.execute("UPDATE training_game SET main_training=0 WHERE game_type=%s", (game_type,))
    prod_connection.execute("UPDATE training_game SET main_training=1 WHERE training_game_id=%s", (training_game_id,))
    Log.logger.debug(f"Updated in table that training {training_game_id} is now the main training for game_type {game_type}")

def upload_training_logs(prod_connection, training_game_id):
    Log.logger.debug(f"Getting bucket for training {training_game_id}")
    bucket_name = Common.get_training_bucket_name(prod_connection, training_game_id)

    Log.logger.info(f"Downloading training logs for {training_game_id} from {bucket_name}")
    bucket = s3.Bucket(bucket_name)
    local_file_path = f"/tmp/{Constants.S3_TRAINING_DATA_DUMP}"
    bucket.download_file(Constants.S3_TRAINING_DATA_DUMP, local_file_path)
    Log.logger.debug(f"Downloaded file to {local_file_path}")

    Log.logger.info("Will upload now the training data to PROD")
    mysql_insert_command = f"mysql -P {Constants.DRAGON_DB_PORT} -h {Constants.DRAGON_PROD_DNS} -u{Constants.DRAGON_DB_USER} -p{Constants.DRAGON_DB_PWD} {Constants.DRAGON_PROD_DB_NAME}"
    execute_command(f"zcat {local_file_path}|{mysql_insert_command}")

# TODO: Review to move this somewhere else? Maybe the container or pull?
def upload_main_training_to_instance(prod_connection):
    # First you get the paths for each game
    main_training_ids = Common.get_main_training_ids(prod_connection)
    nn_paths          = Common.download_main_trainings_from_s3(s3, prod_connection, main_training_ids)
    Log.logger.debug(nn_paths)
    for nn_path in nn_paths:
        # Upload with rsync to instance
        nn_folder = os.path.dirname(nn_path)
        rsync_command = f"rsync -e\"ssh -o StrictHostKeyChecking=no -i{Constants.DRAKO_FOLDER_PATH}/.keys/id_rsa\" -vz --progress {nn_path} ubuntu@{Constants.WEB_DNS}:{nn_folder}/"
        execute_command(rsync_command)

def execute_command(command_to_execute):
    print("Will now execute command: %s" % command_to_execute)
    os.system(command_to_execute)

if __name__ == '__main__':
    args = argparser.parse_args()

    prod_connection = Db(db_host=Constants.DRAGON_PROD_DNS, db_name=Constants.DRAGON_PROD_DB_NAME, db_password=Constants.DRAGON_DB_PWD)

    training_id = get_training_id_for_training_game_id(prod_connection, args.training_game_id)

    logs_folder = f"{Constants.LOGS_FOLDER_PATH}/{training_id}/"
    if not os.path.exists(logs_folder):
        os.mkdir(logs_folder)
    Log.initialize_log("2", filename=f"{logs_folder}/set_main_training.log")

    Log.logger.info(f"Setting main training to {args.training_game_id}")
    set_main_training(prod_connection, args.training_game_id)

    Log.logger.info("Uploading to EC2 instance the main training on the specified path")
    upload_main_training_to_instance(prod_connection)

    Log.logger.info("Now we will ask the EC2 instance to restart")
    restart_ec2_web_instance()
    Log.logger.info("Finished restarting the web_prediction container")

    if args.upload_debug_data:
        Log.logger.info("And finally also updating debug training data")
        upload_training_logs(prod_connection, args.training_game_id)

    prod_connection.close()