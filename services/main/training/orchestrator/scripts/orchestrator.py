# python drako.py --log-level=0 --script-name=script.txt
import argparse
import os
import signal
import time
import sys
from tkinter.tix import Tree
from xml.etree.ElementInclude import include
sys.path.append("/root/drako/services/main/")

import lib.Training.Trainer.Teardown    as Teardown
import lib.Training.Trainer.Preparation as Preparation
import lib.Common.Utils.Log             as Log
import lib.Common.Utils.Constants       as Constants
from lib.Common.Utils                 import str2bool

import lib.Training.Trainer.Setup as Setup 
from lib.Training.Trainer       import Trainer
from lib.Common.Utils.Db        import Db

from lib.Training.Trainer.Common import execute_command, get_main_training_ids, print_or_log_line, prune_containers

import logging
logging.getLogger('boto3').setLevel(logging.CRITICAL)
logging.getLogger('s3transfer').setLevel(logging.CRITICAL)
logging.getLogger('s3').setLevel(logging.CRITICAL)
logging.getLogger('requests').setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.WARNING)

def prepare_mysql_folder():
    if not os.path.exists(f"{Constants.MYSQL_FOLDER_PATH}"):
        print_or_log_line(f"Creating path for mysql folder")
        execute_command(f"mkdir -p {Constants.MYSQL_FOLDER_PATH}", ignore_errors=True)

def ensure_mysql_is_running():
    # Ram limited to 8g since leaks could make parrot unstable
    execute_command(f'docker build -t mysql-drako -f {Constants.MAIN_SERVICE_PATH}/database/Dockerfile.mysql {Constants.DRAKO_FOLDER_PATH}/resources/')
    res = execute_command(f'docker run --net=host -d -v {Constants.MYSQL_FOLDER_PATH}:/var/lib/mysql --name mysql -t mysql-drako', True)
    if "is already in use by container" not in res:
        print_or_log_line("Waiting for mysql to start for 120 seconds")
        time.sleep(120)

# prepare_mysql_folder()
# ensure_mysql_is_running()
# prune_containers() # TODO: REVIEW

staging_connection = Db(db_host=Constants.DRAGON_STAGING_DB_IP, db_name=Constants.get_dragon_staging_db(), db_password=Constants.DRAGON_DB_PWD)

global teardown_counter
teardown_counter = 0

def close_orchestrator():
    Teardown.teardown(staging_connection, remove=False)
    staging_connection.close()

def signal_handler(sig, frame):
    global teardown_counter
    print('You pressed Ctrl+C! Exiting...')
    teardown_counter += 1
    if teardown_counter > 4:
        sys.exit(0)
    close_orchestrator()
    sys.exit(0)
signal.signal(signal.SIGINT, signal_handler)

argparser = argparse.ArgumentParser(description='Use Trainer from command line')
argparser.add_argument('--orchestrator_id',       dest='orchestrator_id',       type=str,      help='the id for the orchestrator in our db', required=True         )
argparser.add_argument('--training_id',           dest='training_id',           type=str,      help='the id for the training_id in our db',  required=True         )
argparser.add_argument('--profile',               dest='profile',               type=str,      help='profile for orchestrator',                                   choices=('EXPLORE', 'TRAIN', 'EXPLORE_AND_TRAIN'))
argparser.add_argument('--agent_name',            dest='agent_name',            type=str,      help='specify the agent for Drako',          default="GoExplore",              choices=("GoExplore"))
argparser.add_argument('--tester_name',           dest='tester_name',           type=str,      help='specify the tester for Drako',                      choices=("NNRecommendationTester"))
argparser.add_argument('--amount_of_agents',      dest='amount_of_agents',      type=int,      help='number of agents to spawn')
argparser.add_argument('--load_main_training',    dest='load_main_training',    type=str2bool, help='if we should load the main training as a starting point')
argparser.add_argument('--only_status',           dest='only_status',           type=str2bool, help='force a training id instead of creating one')
argparser.add_argument('--cleanup_db',            dest='cleanup_db',            type=str2bool, help='cleans the data in the database',   default=False,)
argparser.add_argument('--hours_per_target',      dest='hours_per_target',      type=int,      help='how many hours to spend in each target')
argparser.add_argument('--minutes_per_target',    dest='minutes_per_target',    type=int,      help='how many minutes to spend in each target')
argparser.add_argument('--config_file',           dest='config_file',           type=str,      help='configuration file')
argparser.add_argument('--iterate_over_targets',  dest='iterate_over_targets',  type=str2bool, help='iterate over targets')
argparser.add_argument('--cleanup_db_and_quit',   dest='cleanup_db_and_quit',   type=str2bool, help='cleanup and quit the process')
argparser.add_argument('--target_source',         dest='target_source',         type=str,      help='target source')
argparser.add_argument('--target_id',             dest='target_id',             type=int,      help='target to focus on')
argparser.add_argument('--force_cpu',             dest='force_cpu',             type=str2bool, help='if we use cpu for NNs', default=True)
argparser.add_argument('--learner_family',        dest='learner_family',        type=str,      help='specify the learner family for Drako', default="dqn",        choices=("dqn",))
argparser.add_argument('--learner_name',          dest='learner_name',          type=str,      help='specify the learner for Drako',        default="DQN",        choices=("PlannerDQN","PlannerPrioDQN","DQN","SimplePrioDQN"))

def update_orchestrator_as_ended(orchestrator_id):
    staging_connection.execute("UPDATE orchestrator SET finished=1 WHERE orchestrator_id=%s", (orchestrator_id, ))

if __name__ == '__main__':
    print("First preparing orchestrator..")

    Log.initialize_log("2", "/share/logs/orchestrator.log")

    configuration = Preparation.prepare_orchestrator(staging_connection, argparser)
    print("=" * 50 + "\n" + "=" * 50)

    trainer = Trainer(staging_connection, configuration)
    # If we are asked for a specific target id we just process that target id
    if configuration.target_id is not None:
        print(f"Will focus on target {configuration.target_id}")
        trainer.start_processing_single_target(configuration.target_source, configuration.target_id)

        update_orchestrator_as_ended(configuration.orchestrator_id)

        print("Now we will stop all agents and terminate the environment")
        Teardown.teardown(staging_connection, remove=False)
    elif configuration.iterate_over_targets:
        raise ValueError("This option is deprecated")
    #     trainer.start_processing_targets(configuration.target_source)
    else:
        print("You did not specify iterating over targets..")

    staging_connection.close()