from unittest import TestCase

import random
import lib.Training.Trainer.Common as Common

from lib.Common.Utils.Db import Db
import lib.Common.Utils.Constants   as Constants
import lib.Common.Utils.Log as Log

class Test(TestCase):
    @classmethod
    def setUpClass(cls):
        Log.initialize_log("2")
        cls.connection = Db(db_host=Constants.DRAGON_TEST_DB_IP, db_name=Constants.DRAGON_TEST_DB_NAME, db_password=Constants.DRAGON_DB_PWD, logger=Log.logger)

    @classmethod
    def tearDownClass(cls) -> None:
        Log.close_log()
        cls.connection.close()

    def test_execute_command(self):
        """
        Test to check we perform OS commands correctly
        """

        random_num = str(int(random.random()))
        echo_result = Common.execute_command(f"echo {random_num}")
        self.assertTrue(random_num in echo_result)

        uname_result = Common.execute_command("uname")
        self.assertEqual(uname_result, "Linux")
        # self.fail()

    def test_stop_agents(self):
        result = Common.stop_agents(self.staging_connection)
        self.assertTrue(result)

    def test_start_agents(self):
        result = Common.start_agents(self.staging_connection)
        self.assertTrue(result)

    # TODO: Add test for review_target_health