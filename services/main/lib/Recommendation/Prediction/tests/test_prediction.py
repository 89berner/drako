from unittest import TestCase

import lib.Common.Utils.Log as Log

import lib.Recommendation.Prediction as Prediction
import lib.Common.Utils.Constants as Constants
import lib.Common.Utils     as Utils
from lib.Common.Utils.Db          import Db
import lib.Common.Exploration.Actions       as Actions

from lib.Common.Exploration.Environment.State import State

from lib.Common.Exploration.Metasploit import Metasploit

import lib.Recommendation.Prediction.Helper as Helper

from werkzeug.datastructures import MultiDict

class Test(TestCase):
    @classmethod
    def setUpClass(cls):
        Log.initialize_log("2")
        Actions.initialize()
        Actions.client.load_metasploit_actions()

        cls.connection      = Db(db_host=Constants.DRAGON_TEST_DB_IP, db_name=Constants.DRAGON_TEST_DB_NAME, db_password=Constants.DRAGON_DB_PWD)
        # TODO: We are using prod since we don't have data in TEST, we need to create a TEST one
        cls.prod_connection = Db(db_host=Constants.DRAGON_PROD_DNS, db_name=Constants.DRAGON_PROD_DB_NAME, db_password=Constants.DRAGON_DB_PWD)
        cls.training_id      = 1
        cls.training_game_id = 1
        cls.target      = "10.10.10.3"
        cls.game_type   = "NETWORK"

        cls.environment_options = {
            "target":             cls.target,
            "local_ip":           "127.0.0.1",
            "reverse_shell_port": "12345",
            "server_port":        "34567"
        }

        cls.state = State().get_json()

        cls.form_data = MultiDict([
            ('game_type',           cls.game_type),
            ('environment_options', Utils.dump_json(cls.environment_options)),
            ('state',               cls.state),
            ('action_history',      Utils.dump_json([])),
            ('exploration_method',  None)
        ])

    @classmethod
    def tearDownClass(cls):
        cls.connection.close()
        cls.prod_connection.close()

    def test_exploration_network_prediction(self):
        network_information = Helper.load_network_information(self.prod_connection, self.training_id)
        # Log.add_debug_medium_ascii("Network")
        # print(network_information)
        result = Prediction.predict(self.form_data, network_information)
        Log.add_debug_medium_ascii("Result")
        # print(Utils.dump_json(result))
        self.assertTrue(True)

    def test_exploration_greedy_prediction(self):
        network_information = Helper.load_network_information(self.prod_connection, self.training_id)
        # Log.add_debug_medium_ascii("Network")
        # print(network_information)
        self.form_data["exploration_method"] = "EPSILON_GREEDY"
        result = Prediction.predict(self.form_data, network_information)
        Log.add_debug_medium_ascii("Result")
        # print(Utils.dump_json(result))
        self.assertTrue(True)

    def test_exploration_counter_prediction(self):
        network_information = Helper.load_network_information(self.prod_connection, self.training_id)
        Log.add_debug_medium_ascii("Network")
        # print(Utils.dump_json(network_information))
        # print(network_information)
        self.form_data["exploration_method"] = "COUNTER"
        result = Prediction.predict(self.form_data, network_information)
        Log.add_debug_medium_ascii("Result")
        # print(Utils.dump_json(result))
        self.assertTrue(True)

    def test_web_prediction(self):
        main_training_ids   = Helper.get_main_training_id(self.prod_connection)
        network_information = Helper.load_network_information(self.prod_connection, main_training_ids)
        Log.add_debug_medium_ascii("Network")
        # print(network_information)
        result = Prediction.predict_web(network_information, self.form_data)
        Log.add_debug_medium_ascii("prediction_result")
        # print(Utils.dump_json(result))
        self.assertTrue(True)

    def test_options_generation(self):
        action_name = "auxiliary/scanner/smb/smb_version"
        game_type   = "NETWORK"

        import lib.Recommendation.Prediction.Options as Options
        from lib.Recommendation.Prediction.Options.OptionsRecommender import OptionsRecommender

        options_recommender = OptionsRecommender(self.prod_connection, self.training_game_id)
        state = State()
        raise ValueError("Fix line below!")
        options_generated, options_source, options_errors = Options.generate_options(state, self.target, game_type, action_name, self.environment_options, options_recommender)
        # print(Utils.dump_json(options_generated))
        self.assertTrue(True)