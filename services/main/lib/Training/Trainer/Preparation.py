import yaml
import os
import time
import lib.Common.Utils.Constants as Constants

from lib.Common.Utils.Db import Db
from lib.Training.Trainer.Common import execute_command, prune_containers, stop_agents, download_main_trainings_from_s3, get_main_training_ids, walk_and_clean_directory, cleanup_db
import lib.Common.Utils.Log as Log
import lib.Common.Utils as Utils
import sys

class Configuration:
    def __init__(self, argparser = None):
        # list of attributes to load
        self.mandatory_attributes = {
            "TRAIN":             ["orchestrator_id", "training_id", "learner_family", "learner_name",                     "cleanup_db"                                  ],
            "EXPLORE":           ["orchestrator_id", "training_id", "learner_family", "learner_name", "amount_of_agents", "cleanup_db", "hours_per_target", "agent_name"],
            "EXPLORE_AND_TRAIN": ["orchestrator_id", "training_id", "learner_family", "learner_name", "amount_of_agents", "cleanup_db", "hours_per_target", "agent_name"],
        }
        self.optional_attributes = {
            "TRAIN":             [                                  "load_main_training",                                      "continue_from_latest_point", "cleanup_db_and_quit",                 'force_cpu'],
            "EXPLORE":           ["target_id", "target_source", "iterate_over_targets",                       "only_status", "minutes_per_target",                               "cleanup_db_and_quit", "tester_name", 'force_cpu'],
            "EXPLORE_AND_TRAIN": ["target_id", "target_source", "iterate_over_targets", "load_main_training", "only_status", "minutes_per_target", "continue_from_latest_point", "cleanup_db_and_quit", "tester_name", 'force_cpu']
        }

        # MANDATORY
        self.profile              = None
        self.learner_family       = None
        self.learner_name         = None
        self.agent_name           = None
        self.amount_of_agents     = None
        self.cleanup_db           = None
        self.hours_per_target     = None
        self.orchestrator_id      = None
        self.training_id          = None

        # OPTIONAL
        self.load_main_training         = None
        self.only_status                = None
        self.minutes_per_target         = None
        self.continue_from_latest_point = True
        self.iterate_over_targets       = False
        self.target_id                  = None
        self.target_source              = None
        self.cleanup_db_and_quit        = False
        self.tester_name                = None
        self.force_cpu                  = False  # when this is set, the neural network is trained using the CPU and not the GPU

        if argparser is not None:
            args = argparser.parse_args()
            if args.config_file is not None:
                configuration_file_path = f"/root/drako/services/main/training/orchestrator/config/{args.config_file}"
                self.load_configuration_file(configuration_file_path)
            else:
                self.profile = args.profile.upper()
                self.all_attributes = self.mandatory_attributes[self.profile] + self.optional_attributes[self.profile]
        else: # For testing
            self.all_attributes = []

        # Now for the mandatory attributes missing, set them based on
        for attribute in self.all_attributes:
            # We need to get it from args
            if attribute in args and vars(args)[attribute] is not None:
                Log.logger.debug(f"Setting from args {attribute} => {vars(args)[attribute]}")
                self.__setattr__(attribute, vars(args)[attribute])
            elif not hasattr(self, attribute) and attribute in self.mandatory_attributes:
                raise ValueError(f"Missing required attribute {attribute}")

        # COMBINED VALIDATIONS
        # Log.logger.info(self.cleanup_db_and_quit)
        if self.target_id is None and not self.iterate_over_targets and not self.cleanup_db_and_quit:
            raise ValueError("You need to either specify a target or have flag on iterate_over_targets")

        self.minutes_per_target = self.get_minutes_per_target()

    def get_minutes_per_target(self):
        if self.hours_per_target is not None:
            return self.hours_per_target * 60
        elif self.minutes_per_target is not None:
            return self.minutes_per_target
        else:
            return 60

    def load_configuration_file(self, configuration_file_path):
        with open(configuration_file_path, 'r') as stream:
            try:
                data = yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                Log.logger.warning("Error parsing YAML")
                raise exc

        # First we determine the profile:
        self.profile = data['profile'].upper()

        # We only set attributes needed for the profile
        self.all_attributes = self.mandatory_attributes[self.profile] + self.optional_attributes[self.profile]
        for attribute in self.all_attributes:
            if attribute in data:
                Log.logger.debug(f"Setting from config file {attribute} => {data[attribute]}")
                self.__setattr__(attribute, data[attribute])

        return self.all_attributes

    def to_json(self):
        import lib.Common.Utils as Utils
        data = {}
        for attribute in self.all_attributes:
            data[attribute] = self.__getattribute__(attribute)
        return Utils.dump_json(data)

def stop_all_containers(remove=True):
    execute_command("docker stop $(docker ps -a|egrep 'learner|web_prediction|training_prediction'|cut -d ' ' -f1) 2>/dev/null", ignore_errors=True)

    # if remove:
    #     prune_containers()
    #     #execute_command("docker container rm $(docker ps -a|egrep 'learner|web_prediction|training_prediction'|cut -d ' ' -f1) 2>/dev/null", ignore_errors=True)

def cleanup_shared_folders(main_training_ids):
    Log.logger.warning("Now start cleaning up /share folder")

    walk_and_clean_directory(Constants.LOGS_FOLDER_PATH,     main_training_ids)
    walk_and_clean_directory(Constants.NETWORKS_FOLDER_PATH, main_training_ids)

def prepare_orchestrator(staging_connection, argparser):
    Log.logger.debug("Checking if running the script as root..")
    if os.geteuid() != 0:
        raise ValueError("User must be root to run the script!")

    configuration = Configuration(argparser)

    if configuration.cleanup_db or configuration.cleanup_db_and_quit:
        main_training_ids = get_main_training_ids(staging_connection)

        cleanup_shared_folders(main_training_ids)
        cleanup_db()

        if configuration.cleanup_db_and_quit:
            sys.exit(0)

    if configuration.load_main_training:
        Log.logger.info("Check if we need to download a main training locally")
        import boto3 # Imported here to avoid leaking dependencies to Castle, should be moved somewhere else
        s3 = boto3.resource('s3')
        main_training_ids = get_main_training_ids(staging_connection)
        download_main_trainings_from_s3(s3, staging_connection, main_training_ids)

    if configuration.amount_of_agents is not None:
        Log.logger.info(f"Starting orchestrator for learner:{configuration.learner_family} with amount of agents: {configuration.amount_of_agents}")
    else:
        Log.logger.info(f"Starting orchestrator for learner:{configuration.learner_family}")

    Log.logger.info("First lets ensure all agents are stopped")
    stop_agents(staging_connection)

    Log.logger.info("Then lets stop and remove any containers that might be running..")
    stop_all_containers()

    return configuration
