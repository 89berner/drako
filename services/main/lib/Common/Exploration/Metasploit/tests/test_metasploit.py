from unittest import TestCase, mock

import lib.Common.Exploration.Metasploit as Metasploit
from lib.Common.Exploration.Environment.Environment import NetworkEnvironment

import lib.Common.Utils.Log         as Log
import lib.Common.Utils.Constants   as Constants
from lib.Common.Utils.Db import Db

import lib.Common.Exploration.Actions as Actions

import os

class TestMetasploit(TestCase):
    @classmethod
    def setUpClass(cls):
        Log.initialize_log("2")

        cls.connection     = Db(db_host=Constants.DRAGON_TEST_DB_IP, db_name=Constants.DRAGON_TEST_DB_NAME, db_password=Constants.DRAGON_DB_PWD, logger=Log.logger)
        cls.episode_length = 50
        cls.episode_runner = "tester"
        cls.playbook       = None
        cls.target         = "10.10.10.3"
        cls.training_id    = 1
        self.agent_name    = "test"

    def initialize_metasploit(self):
        environment = NetworkEnvironment(self.connection, self.episode_length, self.episode_runner, self.agent_name, self.target, self.training_id)
        print(environment)

    @mock.patch.dict(os.environ, {"LOCAL_IP": "127.0.0.1"})
    def test_metasploit_initialization(self):
        """
        Test to check db is initialized correctly
        """
        # Creating a test environment
        environment = NetworkEnvironment(self.connection, self.episode_length, self.episode_runner, self.agent_name, self.target, self.training_id)
        metasploit_client = Metasploit.Metasploit(environment)
        self.assertIsInstance(metasploit_client, Metasploit.Metasploit, "Should be a Metasploit instance")

    # def test__add_metasploit_action_to_map(self):
    #     self.fail()
    #
    # def test__initialize_metasploit_actions(self):
    #     self.fail()
    #
    # def test_gather_all_metasploit_information(self):
    #     self.fail()
    #
    # def test_gather_current_metasploit_information(self):
    #     self.fail()
    #
    # def test_get_current_metasploit_sessions(self):
    #     self.fail()
    #
    # def test_perform_execution(self):
    #     self.fail()
    #
    # def test_perform_execution_single_command(self):
    #     self.fail()
    #
    # def test_get_newest_session_id(self):
    #     self.fail()
    #
    # def test_delete_all_metasploit_data(self):
    #     self.fail()