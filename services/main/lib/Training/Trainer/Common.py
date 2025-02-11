import subprocess
import time
import lib.Common.Utils.Constants as Constants
import lib.Common.Utils.Log as Log
import os
from lib.Common.Utils.Db import Db
import re

from lib.Common.Training.Learner import get_main_training_ids
from lib.Common.Exploration.Environment import Validation
from lib.Common import Utils
from lib.Training.Trainer.Request import request_to_manager

def generate_castle_name(target_source, target_name):
    target_name_clean = re.sub('[^0-9a-zA-Z_]+', '', target_name).lower()
    return f"{target_source}_{target_name_clean}".lower()

def generate_castle_db_name(castle_name):
    return f"staging_{castle_name}"

def create_new_orchestrator(connection, target_source, castle_name, data, description = ""):
    stmt = "INSERT INTO orchestrator(target_source, castle_name, data, description) VALUES(%s,%s,%s, %s)"
    orchestrator_id = connection.execute(stmt, (target_source, castle_name, data, description))

    return orchestrator_id

def create_new_training(connection, orchestrator_id, learner_family, learner_name, trainer_config, description = ""):
    query = "INSERT INTO training(orchestrator_id, learner_family, learner_name, trainer_config, description) VALUES (%s,%s,%s,%s,%s)"
    new_training_id = connection.execute(query, (orchestrator_id, learner_family, learner_name, trainer_config, description))

    return new_training_id

def prune_containers(): #TODO ADD FILTER
    print_or_log_line("Prunning")
    execute_command(f'docker container prune -f')

def cleanup_db(db_name = None):
    Log.logger.info("Cleaning up the database")

    if db_name is None:
        staging_db_name = Constants.get_dragon_staging_db()
    else:
        staging_db_name = db_name

    # IMPORTANT! THE STAGING DUMP SHOULD ONLY HAVE THE AGENTS (WITHOUT DATA) AND TRAINING_CONFIG TABLES (WITH DATA)

    Log.logger.info("Cleaning up DB based on latest structure for DRAGON PROD")
    load_data_command                = f"mysqldump -P {Constants.DRAGON_DB_PORT} --column-statistics=0 -h{Constants.DRAGON_PROD_DNS} -u{Constants.DRAGON_DB_USER} -p{Constants.DRAGON_DB_PWD} --no-data {Constants.DRAGON_PROD_DB_NAME} --set-gtid-purged=OFF"
    mysql_write_sdtin_command        = f"mysql -P {Constants.DRAGON_DB_PORT} -h{Constants.DRAGON_STAGING_DB_IP} -u{Constants.DRAGON_DB_USER} -p{Constants.DRAGON_DB_PWD}"
    drop_and_create_database_command = f"{mysql_write_sdtin_command} -e 'DROP DATABASE IF EXISTS {staging_db_name}; CREATE DATABASE {staging_db_name}'"

    execute_command(drop_and_create_database_command)
    execute_command(f"{load_data_command}| {mysql_write_sdtin_command} {staging_db_name}")

    # HERE WE LOAD WITH DATA THE TABLE FOR AGENT CONFIG
    mysql_dump_process       = f"mysqldump -P {Constants.DRAGON_DB_PORT} --column-statistics=0 -h {Constants.DRAGON_PROD_DNS} -u{Constants.DRAGON_DB_USER} -p{Constants.DRAGON_DB_PWD} {Constants.DRAGON_PROD_DB_NAME}"
    mysql_dump_options       = f" --no-create-info --complete-insert --set-gtid-purged=OFF"
    tables_to_dump_with_data = "agent_config training_config"

    mysql_insert_command = f"mysql -P {Constants.DRAGON_DB_PORT} -h {Constants.DRAGON_STAGING_DB_IP} -u{Constants.DRAGON_DB_USER} -p{Constants.DRAGON_DB_PWD} {staging_db_name}"
    execute_command(f"{mysql_dump_process} {mysql_dump_options} {tables_to_dump_with_data}|{mysql_insert_command}")

    #execute_command(f"cat {Constants.RESOURCES_FILE_PATH}/dragon_staging_latest.sql| {mysql_write_sdtin_command}")

    Log.logger.info("Finished cleaning up the database!")

def get_benchmark_id(prod_connection, training_id):
    query        = "SELECT benchmark_id FROM training WHERE training_id=%s"
    res          = prod_connection.query(query, (training_id,))
    Log.logger.debug([query, training_id, res])
    if len(res) > 0:
        return res[0]['benchmark_id']

    return None

def delete_all_instances_of_training_in_prod(prod_connection, training_id):
    Log.logger.debug(f"Will start deleting data for training_id {training_id}")

    # FOR BENCHMARK WE NEED A SPECIAL LOGIC SINCE THERE IS NO TRAINING_ID ASSOCIATED
    benchmark_id_for_training_id = get_benchmark_id(prod_connection, training_id)
    if benchmark_id_for_training_id is not None:
        for table in Constants.DRAGON_PROD_BENCHMARK_TABLES:
            stmt = f"DELETE FROM {table} WHERE benchmark_id=%s"
            prod_connection.execute(stmt, (benchmark_id_for_training_id, ))
            reset_auto_increment_of_table(prod_connection, table)

    for table in Constants.DRAGON_PROD_TABLES:
        stmt = f"DELETE FROM {table} WHERE training_id=%s"
        # Log.logger.debug(stmt % training_id)
        prod_connection.execute(stmt, (training_id, ))
        reset_auto_increment_of_table(prod_connection, table)

    Log.logger.info("Finished deleting information from tables")

def reset_auto_increment_of_table(prod_connection, table):
    autoincrement_key = Constants.PRIMARY_KEYS_MAP[table]
    # NOW LETS SET AGAIN THE AUTO INCREMENT
    log_and_execute_command(prod_connection,
                            f"SET @m = (SELECT COALESCE(MAX({autoincrement_key}), 0) + 1 FROM {table})")
    log_and_execute_command(prod_connection, f"SET @s = CONCAT('ALTER TABLE {table} AUTO_INCREMENT=', @m)")
    log_and_execute_command(prod_connection, f"PREPARE stmt1 FROM @s")
    log_and_execute_command(prod_connection, f"EXECUTE stmt1")
    log_and_execute_command(prod_connection, f"DEALLOCATE PREPARE stmt1")

def log_and_execute_command(prod_connection, stmt):
    #Log.logger.debug(stmt)
    prod_connection.execute(stmt)

def download_main_trainings_from_s3(s3, connection, main_training_ids):
    nn_paths = []
    for game_type in ["NETWORK", "PRIVESC"]:
        if game_type not in main_training_ids:
            Log.logger.warning(f"Game {game_type} does not have a main training set, WEB predictor will not work!")
        else:
            main_training_game_id = main_training_ids[game_type]['training_game_id']
            bucket_name           = get_training_bucket_name(connection, main_training_game_id)
            nn_folder, nn_path    = download_training_nn_from_s3(s3, connection, bucket_name, main_training_game_id)
            Log.logger.debug(f"Downloaded main training to folder {nn_folder}")
            nn_paths.append(nn_path)

    connection.close()

    return nn_paths

def download_training_nn_from_s3(s3_resource, prod_connection, bucket_name, training_game_id):
    results = prod_connection.query("SELECT game_type, neural_network_path FROM training_game WHERE training_game_id=%s", (training_game_id,))

    if len(results) == 0:
        raise ValueError("I was unable to find the necessary information")
    result = results[0]

    game_type = result['game_type']
    nn_path   = result['neural_network_path']

    # If folder does not exist create it
    nn_folder = os.path.dirname(nn_path)
    if not os.path.exists(nn_folder):
        os.makedirs(nn_folder)
        Log.logger.warning(f"Creating folder {nn_folder}")

    Log.logger.debug(f"Checking if file {nn_path} already exists")
    if os.path.exists(nn_path):
        [Log.logger.warning(f"File {nn_path} already exists!! Will not download it!") for i in range(3)]
        time.sleep(1)
    else:
        Log.logger.debug("File does not exist, getting bucket name to download from s3..")
        bucket = s3_resource.Bucket(bucket_name)
        Log.logger.debug(f"Retrieved bucket name {bucket} and will download {Constants.S3_NN_NAME[game_type]} into {nn_path}")
        bucket.download_file(Constants.S3_NN_NAME[game_type], nn_path)
        Log.logger.debug(f"Downloaded from s3 bucket {bucket_name} file to {nn_path}")

    return nn_folder, nn_path

def get_training_bucket_name(prod_connection, training_game_id):
    query = """
        SELECT t.s3_bucket 
        FROM training t 
        JOIN training_game tg ON tg.training_id=t.training_id 
        WHERE tg.training_game_id=%s
    """
    Log.logger.debug([query, (training_game_id,)])
    results = prod_connection.query(query, (training_game_id,))
    bucket_name = results[0]['s3_bucket']

    return bucket_name

def stop_agents_and_reset_current_vm(connection, target):
    stop_agents(connection)
    time.sleep(60)
    Log.logger.info("After we waited 1 minute for agents to stop, we will reset the target")

    data_to_send = {
        "target_id":     target['id'],
        "target_source": target['source'],
    }

    response_data, success = request_to_manager("reset_target", data_to_send)

    # reset target
    if success:
        Log.logger.debug("Response for resetting target => %s" % response_data)

        if response_data['status'] == 'success':
            target['ip'] = response_data['target_ip']
        else:
            Log.logger.error("Error with request: %s" % response_data['message'])
    
    start_agents(connection)

def stop_agent_init(connection):
    print("Stopping agents init..")
    stmt = "UPDATE agent_config set value=\"TRUE\" WHERE attribute IN (\"STOP_AGENTS_INIT\")"
    connection.execute(stmt)

    return True


def stop_agents(connection):
    print("Stopping agents..")
    stmt = "UPDATE agent_config set value=\"TRUE\" WHERE attribute IN (\"STOP_AGENTS\", \"STOP_AGENTS_INIT\")"
    connection.execute(stmt)

    return True

def start_agents(connection):
    Log.logger.info("Starting agents..")
    stmt = "UPDATE agent_config set value=\"FALSE\" WHERE attribute IN (\"STOP_AGENTS\", \"STOP_AGENTS_INIT\", \"PAUSE_TRAINING_AGENTS\", \"PAUSE_TESTER_AGENTS\")"
    connection.execute(stmt)

    return True

def print_or_log_line(line):
    if Log.logger is not None:
        Log.logger.debug(line)
    else:
        print(line)

def walk_and_clean_directory(directory, main_training_ids = {}):
    main_training_ids_map = { str(i["training_id"]): 1 for i in main_training_ids.values() }

    list_of_folders = list(os.walk(directory))
    list_of_folders.reverse()
    for dir_data in list_of_folders:
        dir = dir_data[0]
        dir_path = os.path.basename(os.path.normpath(dir))

        if dir != directory and dir_path not in main_training_ids_map:
            execute_command(f"rm {dir}/*",  ignore_errors=True)
            execute_command(f"rmdir {dir}", ignore_errors=True)
            time.sleep(0.1)

# docker build -t visualizer -f /root/drako/services/main/presentation/visualizer/Dockerfile.visualizer /root/drako/services/main
def execute_command(command_to_execute, ignore_errors=False, hide_output=False, verbose=True):
    if verbose:
        print_or_log_line("-" * 50)
        print_or_log_line("Will now execute command: %s" % command_to_execute)
    try:
        output = subprocess.check_output(command_to_execute, stderr=subprocess.STDOUT, shell=True)
    except subprocess.CalledProcessError as e:
        if not ignore_errors:
            raise RuntimeError("command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))
        else:
            output = e.output
    
    output = output.decode("utf-8").strip()
    if not hide_output:
        if not output.isspace() and len(output) > 0:
            print_or_log_line("Command output was:\n%s" % output)
        if verbose:
            print_or_log_line("-" * 50)

    return output

def set_target_ip(connection, target):
    Log.logger.info("Setting target to %s.." % target)
    stmt = "UPDATE agent_config set value=%s WHERE attribute=\"TESTER_TARGET_IP\" OR attribute=\"TRAINING_TARGET_IP\""
    connection.execute(stmt, (target,))

def review_target_health(connection, target, only_target=None):
    """
        Check that target is healthy, if not reset it
    """
    if 'health_check_port' in target:
        port_to_check = target['health_check_port']

        errors_counter = 0
        while errors_counter < 10:#IF ITS THE ONLY TARGET THEN WE KEEP TRYING
            time_to_sleep = (errors_counter ** 2) * 60
            Log.logger.debug("Checking port %s of target %s after sleeping for %d seconds" % (target['ip'], port_to_check, time_to_sleep))
            time.sleep(time_to_sleep)

            healthy = check_health(target['ip'], port_to_check)
            if not healthy:
                Log.logger.warning("We failed the healtcheck, lets restart the machine")
                stop_agents_and_reset_current_vm(connection, target)

                # NOW WE UPDATE THE TARGET IP ADDRESS THAT AGENTS WILL USE, WE NEED TWO DIFFERENT FIELDS SO ONE IS STATIC ON TRAININGS
                # AND THE OTHER ONE ARE THE EPHEMERAL IPS GIVEN
                # WE SHOULD MOVE AWAY FROM IPS TO NAMES OR IDS
                set_target_ip(connection, target['ip'])

                errors_counter += 1
            else:
                # Log.logger.debug("Healthcheck succeeded!")
                return True

        Log.logger.debug("Failed after 3 consecutives bad healthchecks")
        return False
    else:
        Log.logger.debug("No health_check_port assigned to target so we will skip the check")
        return True


def check_health(target_ip, port_to_check):
    """
        Review the health by trying max_attempts times if the port is open
    """
    max_attempts = 10
    counter      = 0
    while counter < max_attempts:
        if counter > 0:
            Log.logger.debug("%d/%d Reviewing health of target %s with port %s" % (counter, max_attempts, target_ip, port_to_check))

        healthy = Validation.check_port_is_opened(target_ip, port_to_check, "tcp", timeout=40) # 30 is the caller

        if healthy:
            return True
        else:
            Log.logger.warning("Healthcheck failed, will try again in 10 seconds")
            counter += 1
            time.sleep(10)

    return False

def wait_for_game_training_to_be_ready(staging_connection, training_id, game_type):
    Log.logger.info(f"Will wait for learner of game {game_type} to be ready")
    while True:
        query_stmt = "SELECT ready FROM training_game WHERE training_id=%d AND game_type=\"%s\" ORDER BY training_game_id DESC" % (
            training_id, game_type)
        results = staging_connection.query(query_stmt)
        if len(results) > 0 and results[0]['ready']:
            break
        else:
            Log.logger.warning("Learner for game %s is still not ready, will wait 5 seconds" % game_type)
        time.sleep(5)
