import unittest

Log.initialize_log("0")

import lib.Common.Utils.Constants as Constants
from lib.Common.Utils.Db import Db

class TestDb(unittest.TestCase):
    def test_db_initialization(self):
        """
        Test to check db is initialized correctly
        """
        db_instance = Db(db_host=Constants.DRAGON_TEST_DB_IP, db_name=Constants.DRAGON_TEST_DB_NAME, db_password=Constants.DRAGON_DB_PWD)
        self.assertIsInstance(db_instance, Db.Db, "Should be a Db instance")
        db_instance.close()

if __name__ == '__main__':
    unittest.main()
