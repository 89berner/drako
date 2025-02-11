import time
import os

from lib.Training.Trainer.Common import execute_command, create_new_training

import lib.Common.Utils.Constants as Constants
import lib.Common.Utils.Log as Log
import sys

class Setup:
    def __init__(self, staging_connection, configuration):
        self.configuration      = configuration
        self.profile            = configuration.profile
        self.staging_connection = staging_connection

        self.orchestrator_id            = configuration.orchestrator_id
        self.learner_family             = configuration.learner_family
        self.learner_name               = configuration.learner_name
        self.agent_name                 = configuration.agent_name
        self.tester_name                = configuration.tester_name
        self.load_main_training         = configuration.load_main_training
        self.amount_of_agents           = configuration.amount_of_agents
        self.continue_from_latest_point = configuration.continue_from_latest_point
        self.force_cpu                  = configuration.force_cpu
        self.target_source              = configuration.target_source

        self.training_id = configuration.training_id

    def prepare_training_folders(self):
        execute_command(f"mkdir -p {Constants.LOGS_FOLDER_PATH}/{self.training_id}", ignore_errors=True)

        # # CREATING LOGS FOLDER OR RESETING IT
        # if os.path.exists(f"{Constants.LOGS_FOLDER_PATH}/{training_id}"):
        #     execute_command(f"rm {Constants.LOGS_FOLDER_PATH}/{training_id}/*", ignore_errors=True)
        # else:
        #     print(f"Creating paths for training {training_id}")
        #     execute_command(f"mkdir -p {Constants.LOGS_FOLDER_PATH}/{training_id}", ignore_errors=True)

    #     # CREATING NETWORK FOLDER OR RESETTING IT
    #     if not os.path.exists(f"{Constants.NETWORKS_FOLDER_PATH}/{training_id}"):
    #         print(f"Creating paths for training {training_id}")
    #         execute_command(f"mkdir -p {Constants.NETWORKS_FOLDER_PATH}/{training_id}", ignore_errors=True)

    def setup_environments(self):
        # training_id = self.create_current_training()
        # self.training_id = training_id

        self.prepare_training_folders()

        Log.initialize_log("2", filename=f"{Constants.LOGS_FOLDER_PATH}/{self.training_id}/orchestrator.log")

        Log.add_info_large_ascii("Setup")
        if self.profile == "EXPLORE" or self.profile == "EXPLORE_AND_TRAIN":
            self.setup_parrot()
            self.setup_castle()
        elif self.profile == "TRAIN":
            self.setup_parrot()
        else:
            raise ValueError(f"I dont know how to handle profile {self.profile}")

    def setup_parrot(self):
        Log.add_info_medium_ascii("Parrot")
        Log.logger.info("Setting up parrot environment..")

        Log.logger.info("Marking current games as not ready in case they already existed so we wait for the learner to be ready again")
        self.mark_current_games_as_not_ready()

    def setup_castle(self):
        Log.add_info_medium_ascii("Castle")
        Log.logger.info("Now we need to start agents to train based on the configuration target")
        self.create_and_start_agents()

    def create_and_start_agents(self):
        Log.logger.info("Starting now agents in CASTLE..")

        counter = 0
        while counter < 10: # We only try ten times after that lets assume its working if the response was "killed"
            # First attempt to create screen for initiate_castle.py
            agents_command  = f'/bin/bash {Constants.ORCHESTRATOR_SCRIPTS_PATH}/initiate_castle.sh {self.agent_name} {self.tester_name} {self.amount_of_agents} '
            agents_command += f'{self.training_id} {self.profile} '
            agents_command += f'{self.learner_name} {self.load_main_training} {self.continue_from_latest_point} {self.force_cpu} {self.target_source}'
            agents_command += " &"

            execute_command(agents_command, ignore_errors=True)
            time.sleep(10) # Sleep for processes to start

            # Now check if its running
            openvpn_or_castle_running = execute_command('ps -ef|egrep "openvpn|initiate_castle"|grep -v grep|grep -v SCREEN', ignore_errors=True)
            Log.logger.debug(openvpn_or_castle_running)

            if self.target_source == Constants.VM_SOURCE_HACKTHEBOX:
                services_running = 'initiate_castle.py' in openvpn_or_castle_running and 'openvpn' in openvpn_or_castle_running
            else:
                services_running = 'initiate_castle.py' in openvpn_or_castle_running

            if services_running:
                break
            elif 'Killed' in openvpn_or_castle_running:
                counter += 1
            else:
                if self.target_source == Constants.VM_SOURCE_HACKTHEBOX:
                    Log.logger.warning("I dont see initiate_castle.sh or openvpn running, will wait for 30 seconds and try again")
                else:
                    Log.logger.warning("I dont see initiate_castle.sh running, will wait for 30 seconds and try again")
                time.sleep(30)

        if counter == 10:
            Log.add_info_medium_ascii("ERROR")
            Log.logger.error("Error after 10 tries to start agents, will exit now")
            sys.exit(1)
    
    def mark_current_games_as_not_ready(self):
        stmt = "UPDATE training_game SET ready=0 WHERE training_id=%s"
        data = (self.training_id,)
        self.staging_connection.execute(stmt, data)

def teardown_castle():
    command = f"/bin/bash {Constants.ORCHESTRATOR_SCRIPTS_PATH}/teardown_castle.sh"
    execute_command(command, ignore_errors=True)
