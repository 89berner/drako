import datetime
from distutils.log import error
import time
import traceback
import sys

from lib.Training.Trainer.Common import start_agents, review_target_health, set_target_ip

from lib.Training.Trainer.Monitor import Monitor
import lib.Common.Utils.Log as Log
import lib.Training.Trainer.Hackthebox as Hackthebox
import lib.Training.Trainer.Teardown as Teardown
import lib.Training.Trainer.Setup    as Setup
from .Request import request_to_manager

SECONDS_IN_MINUTE = 60 #60

class Trainer:
    def __init__(self, staging_connection, configuration):
        self.staging_connection = staging_connection
        self.configuration      = configuration

        self.learner_family     = configuration.learner_family
        self.hours_per_target   = configuration.hours_per_target
        self.minutes_per_target = configuration.minutes_per_target

        self.already_processed_targets = {}

        self.TOTAL_TARGETS_DESIRED = 999999 # TODO: MAKE THIS A FLAG

    # def start_processing_targets(self, target_source):
    #     Log.add_info_large_ascii("Training")
    #     while len(self.already_processed_targets) < self.TOTAL_TARGETS_DESIRED:
    #         try:
    #             Log.logger.info("(%d/%d) Will request a new target from the API for source %s..." % (len(self.already_processed_targets), self.TOTAL_TARGETS_DESIRED, target_source))
    #             new_target, finished_all_targets = self.generate_and_assign_target(target_source)

    #             if finished_all_targets:
    #                 Log.logger.info("We finished going through all the targets, lets end this")
    #                 break

    #             if new_target is not None:
    #                 self.process_target_wrapper(new_target)
    #             else:
    #                 Log.logger.warning("We were unable to get a target, lets wait a minute and start again")
    #                 time.sleep(SECONDS_IN_MINUTE)
    #         except AttributeError:
    #             error_message = "ERROR trying to exit: %s" % traceback.format_exc()
    #             print(error_message)
    #             sys.exit(0)
    #         except SystemExit:
    #             print("Exiting..")
    #             sys.exit(0)
    #         except Exception:
    #             error_message = "ERROR: Will sleep for 1 minute and start again: %s" % traceback.format_exc()
    #             if Log.logger is not None:
    #                 Log.logger.error(error_message)
    #             else:
    #                 print(error_message)
    #             time.sleep(SECONDS_IN_MINUTE)

    def start_processing_single_target(self, target_source, target_id):
        Log.add_info_large_ascii("Training")

        target = None
        while target is None:
            target = self.generate_and_assign_single_target(target_source, target_id)

            if target is None:
                print("target cannot be None! will try again in 1 minute..")
                time.sleep(60)

        self.process_target_wrapper(target)

    def process_target_wrapper(self, new_target):
        # Lets teardown just in case
        Log.logger.info("Tearing down to cleanup the environment..")
        Teardown.teardown(self.staging_connection)

        setup = Setup.Setup(self.staging_connection, self.configuration)
        setup.setup_environments()
        Log.logger.info("=" * 50 + "\n" + "=" * 50)
        Log.logger.info("Finished tearing down and setting up to cleanup the environment..")
        # SETUP #

        # ACTUAL PROCESS TARGET #
        self.process_target(new_target)
        # ACTUAL PROCESS TARGET #

    def process_target(self, new_target):
        Log.logger.info("Now we need to set as the new target %s" % new_target)
        new_target_ip = new_target['ip']

        Log.logger.info("We will set the new target to %s" % new_target_ip)
        self.set_target(new_target_ip)
        set_target_ip(self.staging_connection, new_target_ip)

        is_healthy = review_target_health(self.staging_connection, new_target)
        if not is_healthy:
            Log.logger.warning("Current target is not healthy, will skip it")
        else:
            start_agents(self.staging_connection)

            monitor = Monitor(self.staging_connection, new_target, self.configuration)

            # HERE WE LOOP UNTIL WE SURPASS THE TIME ALLOWED FOR THE TARGET
            monitor.monitor_target()

        # FINISH PROCESSING TARGET
        self.already_processed_targets[new_target['id']] = datetime.datetime.now()
        Log.logger.info("Finished processing target %s" % new_target)
        time.sleep(10)

    def generate_and_assign_single_target(self, target_source, target_id) -> int:
        data_to_send = {
            "target_id":     target_id,
            "target_source": target_source,
        }

        Log.logger.debug("Will now request to endpoint generate_and_assign_single_target and data %s" % str(data_to_send))
        response, success = request_to_manager("generate_and_assign_single_target", data_to_send)
        Log.logger.debug(response)

        if success:
            return response['target']
        elif 'success' not in response:
            Log.logger.error("Error on request! => %s" % response)
            return None
        elif not response['success']:
            Log.logger.error("Error on request! => %s" % response['message'])
            return None
        else:
            Log.logger.error("Error trying to get target, server said => %s" % response['message'])
            return None

    def generate_and_assign_target(self, target_source):
        data_to_send = {
            "target_source":             target_source,
            "already_processed_targets": self.already_processed_targets,
        }

        RETRIES_AMOUNT = 5
        attempts       = 1
        while True:
            response, success = request_to_manager("generate_and_assign_target", data_to_send)
            attempts += 1

            if success:
                if response['message'] == "RETRY":
                    continue
                elif response['message'] == "FINISHED_ALL_TARGETS":
                    return None, True
                elif response['success']:
                    return response['target'], False
                else:
                    return None, False
            elif attempts < RETRIES_AMOUNT:
                Log.logger.warning("(%d/%d) will retry request after 30 seconds.." % (attempts, RETRIES_AMOUNT))
                time.sleep(30)
                continue
            else:
                return None, False

        return None, False

    def set_target(self, target):
        Log.logger.info("Setting target to %s.." % target)
        stmt = "UPDATE agent_config set value=%s WHERE attribute=\"TESTER_TARGET\" OR attribute=\"TRAINING_TARGET\""
        self.staging_connection.execute(stmt, (target,))