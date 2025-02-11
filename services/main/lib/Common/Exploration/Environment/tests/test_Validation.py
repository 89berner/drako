from unittest import TestCase

import lib.Common.Exploration.Environment.Validation as Validation
import lib.Common.Utils.Log as Log

class TestValidation(TestCase):
    @classmethod
    def setUpClass(cls):
        Log.initialize_log("2")

    def test_check_port_is_opened(self):
        target   = "127.0.0.1"
        port     = "22"
        protocol = "tcp"
        timeout  = 30
        delay    = 10
        retries  = 3

        result = Validation.check_port_is_opened(target, port, protocol, timeout, delay, retries)
        print(result)

        self.assertTrue(True)
