from unittest import TestCase, mock

import lib.Common.Utils.Log         as Log
import lib.Common.Utils.Constants   as Constants
from lib.Common.Utils.Db import Db
from lib.Common.Exploration.Environment.Environment import NetworkEnvironment

import os

from lib.Common.Exploration.Metasploit import Metasploit

from lib.Common.Exploration.Environment.Observation import RawObservation


class TestEnvironment(TestCase):
    @classmethod
    def setUpClass(cls):
        Log.initialize_log("2")

        cls.connection = Db(db_host=Constants.DRAGON_TEST_DB_IP, db_name=Constants.DRAGON_TEST_DB_NAME,
                            db_password=Constants.DRAGON_DB_PWD, logger=Log.logger)
        cls.episode_length = 50
        cls.episode_runner = "tester"
        cls.playbook = None
        cls.target = "10.10.10.3"
        cls.training_id = 1
        cls.agent_name  = "test"

    @mock.patch.dict(os.environ, {"LOCAL_IP": "127.0.0.1"})
    def test_create_environment(self):
        environment = NetworkEnvironment(self.connection, self.episode_length, self.episode_runner, self.agent_name,
                                         self.target, self.training_id)
        self.assertIsInstance(environment, NetworkEnvironment, "Should be a NetworkEnvironment instance")

    def fake_gather_current_metasploit_information(self):
        Log.logger.debug("Faking fake_gather_current_metasploit_information response")

        return {
            "hosts_list": [{
                "address":   "127.0.0.1",
                "name":      "drako",
                "os_name":   "asdaopmdpoamosdmdomsoadmpdaosmdposmpdaosdosa",
                "os_flavor": "linux"
            }],
            "services_list": [{
                "host":  Constants.PARROT_IP,
                "port":  "22",
                "proto": "tcp",
                "state":  Constants.OPEN_PORT,
                "name":  "httpd",
                "info":  "information"
            }],
            "notes": [],
            "vulns": [],
            "sessions_map": [],
            "jobs_list": [],
        }

    @mock.patch.dict(os.environ, {"LOCAL_IP": "127.0.0.1"})
    @mock.patch.object(Metasploit, 'gather_current_metasploit_information', fake_gather_current_metasploit_information)
    def test_create_raw_observation(self):
        environment = NetworkEnvironment(self.connection, self.episode_length, self.episode_runner,
                                         self.target, self.training_id)
        environment.set_target(Constants.PARROT_IP)

        # Attempting to start metasploit
        metasploit_client = Metasploit(environment)
        environment.set_metasploit_client(metasploit_client)

        action_name      = "action_name"
        action_type      = "action_type"
        env_action       = ""
        env_options      = ""
        observed_output  = {}
        time_taken       = 30
        delay_to_observe = 0

        new_raw_observation = environment.CreateRawObservation(action_name, action_type, env_action, env_options,  observed_output, time_taken, delay_to_observe)
        self.assertIsInstance(new_raw_observation, RawObservation, "Is not RawObservationInstance")
        print(environment.get_json_state())
        self.assertTrue(True)

    # def test_set_agent(self):
    #     self.fail()
    #
    # def test_set_trainable_episode(self):
    #     self.fail()
    #
    # def test_set_test_episode(self):
    #     self.fail()
    #
    # def test_mark_tester_episode_as_failure(self):
    #     self.fail()
    #
    # def test_set_target(self):
    #     self.fail()
    #
    # def test_get_target(self):
    #     self.fail()
    #
    # def test_update_target(self):
    #     self.fail()
    #
    # def test_start_new_episode(self):
    #     self.fail()
    #
    # def test_start_new_test_episode(self):
    #     self.fail()
    #
    # def test_start_new_game(self):
    #     self.fail()
    #
    # def test_mark_current_game_as_finished(self):
    #     self.fail()
    #
    # def test_set_game_type(self):
    #     self.fail()
    #
    # def test_decide_reward(self):
    #     self.fail()
    #
    # def test_record_raw_observation(self):
    #     self.fail()
    #
    # def test_is_finished(self):
    #     self.fail()
    #
    # def test_finish_step(self):
    #     self.fail()
    #
    # def test_finish_episode(self):
    #     self.fail()
    #
    # def test_close(self):
    #     self.fail()
    #
    # def test_get_environment_options(self):
    #     self.fail()
    #
    # def test_get_hosts(self):
    #     self.fail()
    #
    # def test_get_services(self):
    #     self.fail()
    #
    # def test_get_open_ports(self):
    #     self.fail()
    #
    # def test_get_json_state(self):
    #     self.fail()
    #
    # def test_get_json_previous_state(self):
    #     self.fail()
    #
    # def test_get_sessions_dict(self):
    #     self.fail()
    #
    # def test_get_state_pretty(self):
    #     self.fail()
    #
    # def test_get_newest_session_id(self):
    #     self.fail()
    #
    # def test_get_sessions_string(self):
    #     self.fail()
    #
    # def test_get_default_apache_port(self):
    #     self.fail()
    #
    # def test_get_default_server_port(self):
    #     self.fail()
    #
    # def test_get_default_reverse_shell_port(self):
    #     self.fail()
    #
    # def test_get_default_local_ip(self):
    #     self.fail()
    #
    # def test_get_postgressql_port(self):
    #     self.fail()
    #
    # def test_get_msfrpc_port(self):
    #     self.fail()
    #
    # def test_inside_a_container(self):
    #     self.fail()
    #
    # def test_get_container_id(self):
    #     self.fail()
    #
    # def test_get_container_name(self):
    #     self.fail()
    #
    # def test_set_container_waiting(self):
    #     self.fail()
    #
    # def test_set_container_not_waiting(self):
    #     self.fail()
    #
    # def test_get_ports_data(self):
    #     self.fail()
    #
    # def test_get_current_game_type(self):
    #     self.fail()
    #
    # def test_get_previous_game_type(self):
    #     self.fail()
    #
    # def test_create_processed_observation(self):
    #     self.fail()
    #
    # def test_run_shell_command_with_output_in_session(self):
    #     self.fail()
    #
    # def test_create_raw_observation(self):
    #     self.fail()
    #
    # def test_get_current_status(self):
    #     self.fail()
    #
    # def test_session_is_available(self):
    #     self.fail()
    #
    # def test_web_application_available(self):
    #     self.fail()
