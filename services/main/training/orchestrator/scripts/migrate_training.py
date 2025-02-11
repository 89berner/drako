# This script moves the staging table to production and then creates a snapshot of the production database

import argparse
import os
import shutil
import boto3
import random
import string
import time

# For multipart
import random
from boto3.s3.transfer import TransferConfig
import threading

import sys
import os

sys.path.append("/root/drako/services/main/")

# TODO: Add error handling for different steps and rollback procedure?
# This script is supposed to be ran by selecting a training_id in PROD as MAIN

from lib.Common.Utils.Db import Db
import lib.Common.Utils.Constants as Constants
import lib.Common.Utils.Log       as Log

import lib.Training.Trainer.Common as Common
from lib.Common.Utils                 import str2bool

argparser = argparse.ArgumentParser(description='Use migrate_training.py to migrate a training to production')
argparser.add_argument('--training_id',  dest='training_id',  type=int,      help='specify training_id to set as main',                  required=False)
argparser.add_argument('--training_ids', dest='training_ids', type=str,      help='specify training_ids to set as main comma separated', required=False)
argparser.add_argument('--migrate_all',  dest='migrate_all',  type=str2bool, help='if we want to migrate nn and training data',     required=False, default=False)
argparser.add_argument('--db_name',      dest='db_name',      type=str,      help='db_name',     required=True)

args = argparser.parse_args()

s3  = boto3.resource('s3')
rds = boto3.client('rds', region_name="eu-west-1")

import logging
logging.getLogger('boto3').setLevel(logging.CRITICAL)
logging.getLogger('s3transfer').setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)
logging.getLogger("requests").setLevel(logging.CRITICAL)
logging.getLogger("mysql.connector").setLevel(logging.CRITICAL)
logging.getLogger("s3").setLevel(logging.CRITICAL)
logging.getLogger("nose").setLevel(logging.CRITICAL)

for key in logging.Logger.manager.loggerDict:
    print(key)

prod_connection = Db(db_host=Constants.DRAGON_PROD_DNS, db_name=Constants.DRAGON_PROD_DB_NAME, db_password=Constants.DRAGON_DB_PWD)

def migrate_table(prod_connection, dragon_staging_db_name, table, staging_training_id, prod_training_id):
    Log.logging.info(f"Migrating table {table}")

    Log.logging.debug("First we delete any entry already existing for this training_id %d" % prod_training_id)
    prod_connection.execute(f"DELETE FROM {table} WHERE training_id=%s", (prod_training_id,))
    Log.logger.debug("Finished deleting for training %d" % prod_training_id)

    tables_without_training_id = get_columns_without_training(table)
    stmt = f"INSERT INTO dragon.{table} ({tables_without_training_id}, training_id) SELECT {tables_without_training_id}, {prod_training_id} FROM {dragon_staging_db_name}.{table} WHERE training_id=%s"
    Log.logger.debug("Will now run %s" % stmt)
    prod_connection.execute(stmt, (staging_training_id,))
    Log.logging.info(f"Finished migrating table {table}")

# https://medium.com/@niyazi_erd/aws-s3-multipart-upload-with-python-and-boto3-9d2a0ef9b085
def multi_part_upload_with_s3(s3, bucket_name, file_path, key_path):
    # Multipart upload
    config = TransferConfig(multipart_threshold=1024 * 1024 * 10, max_concurrency=10,
                            multipart_chunksize=1024 * 1024 * 10, use_threads=True) # max chunks are 10k
    s3.meta.client.upload_file(file_path, bucket_name, key_path, Config=config, ExtraArgs={'StorageClass': 'ONEZONE_IA'}, Callback=ProgressPercentage(file_path))

class ProgressPercentage(object):
    def __init__(self, filename):
        self._filename = filename
        self._size = float(os.path.getsize(filename))
        self._seen_so_far = 0
        self._lock = threading.Lock()

    def __call__(self, bytes_amount):
        with self._lock:
            self._seen_so_far += bytes_amount
            percentage = (self._seen_so_far / self._size) * 100
            Log.logger.debug("%s  %s / %s  (%.2f%%)" % ( self._filename, self._seen_so_far, self._size, percentage))

def create_random_string(size):
    return ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(size))

def get_columns_without_training(table):
    res = prod_connection.query(f"DESCRIBE {table}")
    fields = ""
    for entry in res:
        field = entry['Field']
        if field != "training_id":
            if fields != "":
                fields += ","
            fields += field
    # Log.logger.debug(f"{table} => {fields}")

    return fields

def migrate_staging_db_to_production(dragon_staging_db_name):
    mysql_dump_process  = f"mysqldump -P {Constants.DRAGON_DB_PORT} --column-statistics=0 -h {Constants.DRAGON_STAGING_DB_IP} -u{Constants.DRAGON_DB_USER} -p{Constants.DRAGON_DB_PWD} -B {dragon_staging_db_name} --ignore-table=staging_general_metasploitable.training_states --extended-insert=FALSE  --add-drop-database"
    mysql_write_process = f"mysql -P {Constants.DRAGON_DB_PORT} -h {Constants.DRAGON_PROD_DNS} -u{Constants.DRAGON_DB_USER} -p{Constants.DRAGON_DB_PWD}"
    tmp_file            = "/tmp/dragonstagingdump.sql"

    Common.execute_command(f"{mysql_dump_process} > {tmp_file}")
    Common.execute_command(f"cat {tmp_file}|{mysql_write_process}")

def migrate_training_data_to_mysql(staging_training_id, dragon_staging_db):
    staging_connection = Db(db_host=Constants.DRAGON_STAGING_DB_IP, db_name=dragon_staging_db, db_password=Constants.DRAGON_DB_PWD)

    training_res = staging_connection.query("select * from training WHERE training_id=%s", (staging_training_id,))
    if len(training_res) > 1:
        raise ValueError("there should not be more than one training with an id")
    training_res = training_res[0]

    # First we create for each training a new training_id
    staging_orchestrator_id = training_res['orchestrator_id']

    # add orchestrator if missing
    orch_res = staging_connection.query("select * from orchestrator WHERE orchestrator_id=%s", (staging_orchestrator_id,))
    if len(orch_res) > 1:
        raise ValueError("there should not be more than one orchestrator with an id")
    orch_res = orch_res[0]

    # First we create an orchestrator entry in our prod database
    # First get the orchestrator uuid
    res = staging_connection.query("select * from orchestrator")
    if len(res) != 1:
        raise ValueError("You can't have more than 1 orchestrator id per database to migrate")
    castle_uuid = res[0]['description']

    # TODO: We should avoid having multiple orchestrator ids or do all migrations in one go
    res = prod_connection.query("select * from orchestrator WHERE description = %s", (castle_uuid,))
    if len(res) == 0:
        prod_orchestrator_id = Common.create_new_orchestrator(prod_connection, orch_res['target_source'], orch_res['castle_name'], orch_res['data'], castle_uuid)
    else:
        prod_orchestrator_id = res[0]['orchestrator_id']
        Log.logging.warning("Not creating an orchestrator ID since we already have one => %d" % prod_orchestrator_id)

    Log.logger.debug("Migrating the db to prod")
    migrate_staging_db_to_production(dragon_staging_db)

# def create_new_training(connection, orchestrator_id, learner_family, learner_name, trainer_config):
    prod_training_id = Common.create_new_training(prod_connection, prod_orchestrator_id, training_res['learner_family'], training_res['learner_name'], training_res['trainer_config'], castle_uuid)

    ############ NOW WE MOVE DATA AROUND #########################

    # TODO: Add benchmark logic with an example

    migrate_table(prod_connection, dragon_staging_db, "episode",              staging_training_id, prod_training_id)
    migrate_table(prod_connection, dragon_staging_db, "game",                 staging_training_id, prod_training_id)
    migrate_table(prod_connection, dragon_staging_db, "step",                 staging_training_id, prod_training_id)
    migrate_table(prod_connection, dragon_staging_db, "super_episode",        staging_training_id, prod_training_id)
    migrate_table(prod_connection, dragon_staging_db, "training_game",        staging_training_id, prod_training_id)
    migrate_table(prod_connection, dragon_staging_db, "training_target",      staging_training_id, prod_training_id)
    migrate_table(prod_connection, dragon_staging_db, "training_target_path", staging_training_id, prod_training_id)

    # DELETE from episode WHERE training_id=10;
    # DELETE from game WHERE training_id=10;
    # DELETE from raw_observation WHERE training_id=10;
    # DELETE from step WHERE training_id=10;
    # DELETE from super_episode WHERE training_id=10;
    # DELETE from training_game WHERE training_id=10;
    # DELETE from training_target WHERE training_id=10;
    # DELETE from training_target_path WHERE training_id=10;

    staging_connection.close()

    # raise NotImplementedError("Implement with training and benchmark")
    

def create_or_clean_s3_bucket(training_id):
    # random_string = create_random_string(16)
    bucket_name = f"training-data-{Constants.S3_RANDOM_KEY}-{training_id}"

    Log.logger.info(f"Will check if I need to clean or not bucket {bucket_name}")

    bucket_exists = s3.Bucket(bucket_name) in s3.buckets.all()
    if bucket_exists:
        Log.logger.debug(f"Bucket {bucket_name} does exist")
        objects = list(s3.Bucket(bucket_name).objects.all())
        for obj in objects:
            Log.logger.info(f"Will delete object {obj.key}")
            obj.delete()
    else:
        Log.logger.info(f"Will create bucket {bucket_name} in region {Constants.AWS_REGION}")
        s3.create_bucket(Bucket=bucket_name, CreateBucketConfiguration={'LocationConstraint': Constants.AWS_REGION})

    Log.logger.info(f"Finished preparing bucket {bucket_name}")

    return bucket_name

def get_nns_from_training(training_id, db_name):
    staging_connection = Db(db_host=Constants.DRAGON_STAGING_DB_IP, db_name=db_name, db_password=Constants.DRAGON_DB_PWD)
    # Get all training games for each
    stmt = "SELECT neural_network_path, game_type FROM training_game WHERE training_id=%s"
    results = staging_connection.query(stmt, (training_id,))

    networks_map = {}
    for result in results:
        neural_network_path = result['neural_network_path']
        game_type = result['game_type']
        networks_map[game_type] = neural_network_path
    staging_connection.close()

    return networks_map

def upload_nn_to_s3(training_id, bucket_name, db_name):
    Log.logger.info(f"Will now upload NNs of training {training_id} to S3 bucket {bucket_name}")
    networks_map = get_nns_from_training(training_id, db_name)
    for game_type in networks_map:
        nn_path = networks_map[game_type]
        Log.logger.info(f"Uploading network for game {game_type} at {nn_path}")
        s3.Object(bucket_name, Constants.S3_NN_NAME[game_type]).put(Body=open(nn_path, 'rb'), StorageClass='ONEZONE_IA')
    Log.logger.info("Finished uploading data")

def upload_debug_training_data_to_s3(training_id, bucket_name):
    Log.logger.info("First we dump the data and compress it")
    mysql_dump_process          = f"mysqldump -P {Constants.DRAGON_DB_PORT} --column-statistics=0 -h {Constants.DRAGON_STAGING_DB_IP} -u{Constants.DRAGON_DB_USER} -p{Constants.DRAGON_DB_PWD} {Constants.get_dragon_staging_db()}"
    tables_to_dump              = f"training_step training_states"
    tmp_training_data_dump_path = f"/tmp/{Constants.S3_TRAINING_DATA_DUMP}"
    Common.execute_command(f"{mysql_dump_process} {tables_to_dump}|gzip -9 > {tmp_training_data_dump_path}")

    Log.logger.info(f"Uploading to s3 on bucket {bucket_name} under name {Constants.S3_TRAINING_DATA_DUMP}")

    multi_part_upload_with_s3(s3, bucket_name, tmp_training_data_dump_path, Constants.S3_TRAINING_DATA_DUMP)
    #s3.Object(bucket_name, Constants.S3_TRAINING_DATA_DUMP).put(Body=open(tmp_training_data_dump_path, 'rb'), StorageClass='ONEZONE_IA')

def update_training_with_bucket_name(training_id, bucket_name):
    stmt = "UPDATE training set s3_bucket=%s WHERE training_id=%s"
    prod_connection.execute(stmt, (bucket_name, training_id))

def migrate_training(training_id, migrate_all, dragon_staging_db_name):

    # Log.logger.info("Start deleting the data in PROD in case it already exists")
    # Common.delete_all_instances_of_training_in_prod(prod_connection, training_id)

    if migrate_all:
        bucket_name = create_or_clean_s3_bucket(training_id)

        Log.logger.info(f"Will now upload NNs to S3 bucket {bucket_name}")
        upload_nn_to_s3(training_id, bucket_name, dragon_staging_db_name)


    Log.logger.info("Lastly we upload training data to mysql excluding training debug data")
    migrate_training_data_to_mysql(training_id, dragon_staging_db_name)

    if migrate_all:
        Log.logger.info("Now we update the training with the bucket information")
        update_training_with_bucket_name(training_id, bucket_name)

        Log.logger.info(f"Uploading debug training data dump to S3 bucket {bucket_name} for training_id {training_id}")
        upload_debug_training_data_to_s3(training_id, bucket_name)

def get_db_snapshots_map():
    snapshots = rds.describe_db_snapshots(DBInstanceIdentifier=Constants.DRAGON_DB_IDENTIFIER)['DBSnapshots']
    snapshots_map = {}
    for snapshot in snapshots:
        snapshot_identifier = snapshot['DBSnapshotIdentifier']
        snapshots_map[snapshot_identifier] = snapshot
    return snapshots_map

def create_database_snapshot(training_id):
    snapshots_map = get_db_snapshots_map()
    snapshot_identifier_to_create = f"dragon-snapshot-{training_id}"

    if snapshot_identifier_to_create in snapshots_map:
        Log.logger.warning(f"Snapshot identifier {snapshot_identifier_to_create} already exists, will delete it first")
        response = rds.delete_db_snapshot(DBSnapshotIdentifier=snapshot_identifier_to_create)
        Log.logger.debug(response)

    Log.logger.info(f"Will now create snapshot identifier {snapshot_identifier_to_create}")
    response = rds.create_db_snapshot(DBSnapshotIdentifier=snapshot_identifier_to_create, DBInstanceIdentifier=Constants.DRAGON_DB_IDENTIFIER)
    Log.logger.debug(response)

if args.training_id is not None:
    training_ids = [args.training_id]
elif args.training_ids is not None:
    training_ids = args.training_ids.split(",")
else:
    raise ValueError("You need to either set a training_id or training_ids flag")

# 1) Creates an S3 bucket
# 2) Uploads NNs to bucket
# 3) Add bucket name to training
# 4) Upload debug data to s3
# 5) Create db snapshot
for training_id in training_ids:
    Log.initialize_log("2")

    Log.logger.info(f"Will now migrate to PROD the training_id {training_id} from staging")
    migrate_training(training_id, args.migrate_all, args.db_name)

    if args.migrate_all:
        Log.logger.info("Now lets create a snapshot for the new state of the DB")
        # Details on how they work: https://stackoverflow.com/questions/49125889/aws-rds-backups-are-incremental-or-differential
        create_database_snapshot(training_id)

        Log.logger.info(f"Finished migration of training {training_id}!")

        if len(training_ids):
            Log.logger.info("Sleeping for 1 minute before picking the next training_id")
            time.sleep(60)

    Log.close_log()

prod_connection.close()