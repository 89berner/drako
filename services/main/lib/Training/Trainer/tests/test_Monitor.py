from unittest import TestCase
import lib.Training.Trainer.Monitor as Monitor

import lib.Common.Utils.Log         as Log
import lib.Common.Utils.Constants   as Constants
from lib.Common.Utils.Db import Db

import lib.Training.Trainer.Preparation as Preparation

class TestMonitor(TestCase):
    # Called when the whole class starts
    @classmethod
    def setUpClass(self):
        Log.initialize_log("2")
        self.connection   = Db(db_host=Constants.DRAGON_TEST_DB_IP, db_name=Constants.DRAGON_TEST_DB_NAME, db_password=Constants.DRAGON_DB_PWD, logger=Log.logger)

        training_id        = 1
        target             = {
            "id": 1,
            "ip": "10.10.10.3"
        }

        configuration = Preparation.Configuration()
        configuration.learner.family     = 'DQN'
        configuration.minutes_per_target = 60
        configuration.amount_of_agents   = 100

        self.test_episode_id    = 1
        self.test_transition_id = 1
        self.test_training_id   = 1

        hackthebox_client = None

        self.monitor = Monitor(hackthebox_client, self.connection, training_id, target, configuration)

    # set when the whole class is destroyed
    @classmethod
    def tearDownClass(cls) -> None:
        Log.close_log()
        cls.monitor.staging_connection.close()
        # clean up database and close

    def setUp(self):
        # On every method we will clean the test database
        self.monitor.staging_connection.clean_test_database()

    def test_update_target_statistics(self):
        """
        Test to check we are updating the correct training stats
        """
        # There is no entry already, so it creates it
        self.monitor.update_target_statistics()

        # Now we have an entry, so we update it
        self.monitor.update_target_statistics()

        self.assertTrue(True)

    def test_get_amount_of_actions_used_for_target(self):
        amount_of_actions_count = self.monitor.get_amount_of_actions_used_for_target()
        print(f"test_get_amount_of_actions_used_for_target: {amount_of_actions_count}")
        self.assertTrue(amount_of_actions_count >= 0)

    def test_get_amount_of_positive_steps_for_target(self):
        positive_actions_count = self.monitor.get_amount_of_positive_steps_for_target()
        print(f"test_get_amount_of_positive_steps_for_target: {positive_actions_count}")
        self.assertTrue(positive_actions_count >= 0)

    def insert_test_result(self):
        stmt = """
                INSERT INTO episode(episode_id, positive_steps, total_steps, finished, test_episode, training_id)
                VALUES(%s,%s,%s,%s,%s,%s)
        """

        positive_steps   = 1
        total_steps      = 2
        episode_finished = 1
        test_episode     = 1
        self.connection.execute(stmt, (self.test_episode_id, positive_steps, total_steps, episode_finished, test_episode, self.test_training_id))

        stmt = """
            INSERT INTO test_episode(episode_id, training_id)
            VALUES(%s,%s)
        """
        self.connection.execute(stmt, (self.test_episode_id, self.test_transition_id))

        return True

    def test_get_latest_test_result(self):
        # TODO: Insert test training result and change assertion
        self.insert_test_result()

        latest_results = self.monitor.get_latest_test_result()
        print(f"test_get_latest_test_result: {latest_results}")
        print(latest_results['total_steps'])
        self.assertEqual(latest_results['total_steps'], 2)

    def test_get_steps_per_minute(self):
        total_steps, steps_with_reward = self.monitor.get_steps_per_minute()
        print(f"test_get_steps_per_minute: {[total_steps, steps_with_reward]}")

        self.assertTrue(total_steps >= 0)
        self.assertTrue(steps_with_reward >= 0)
