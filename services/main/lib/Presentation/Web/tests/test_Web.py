from unittest import TestCase

import lib.Common.Utils.Log as Log

from lib.Common.Utils.Db import Db
import lib.Common.Utils.Constants as Constants

import lib.Presentation.Web as Web
import lib.Common.Utils     as Utils
import lib.Common.Exploration.Environment.State as State

import random

class TestWeb(TestCase):
    @classmethod
    def setUpClass(cls):
        Log.initialize_log("2")

        cls.connection = Db(db_host=Constants.ASSISTANT_DB_DNS, db_name=Constants.ASSISTANT_DB_NAME, db_password=Constants.ASSISTANT_DB_PWD, logger=Log.logger)
        cls.lex_client = Web.create_lex_client()
        cls.ses_client = Web.create_ses_client()

        cls.session = {}
        Web.set_new_session(cls.session)

    @classmethod
    def tearDownClass(cls):
        cls.connection.close()

    def test_send_email(self):
        success = Web.send_email(ses_client=self.ses_client, name="Juan", email="89berner@gmail.com", message="This is part of the test suite", test=True)
        self.assertTrue(success)

    def test_send_normal_message(self):
        received_message = "hello"
        intention_data, lex_response = Web.get_intention_from_message(self.session, self.connection, self.lex_client, received_message)
        print(Utils.dump_json(intention_data))
        print(Utils.dump_json(lex_response))
        self.assertTrue(intention_data is not None)

        response, flag_for_new_session = Web.process_intention_and_slots(self.session, self.connection, received_message, intention_data, lex_response)
        print(Utils.dump_json(response))
        self.assertTrue(response is not None)
        self.assertTrue(flag_for_new_session is False)

    def test_recommend_action(self):
        response = "You should try to use #ACTION_NAME#."
        recommended_action_entry, response = Web.recommend_action(self.session, self.connection, "NETWORK", State.State(), response)
        print([recommended_action_entry, response])

    def test_send_prediction_message(self):
        received_message = "what do you recommend"
        intention_data, lex_response = Web.get_intention_from_message(self.session, self.connection, self.lex_client, received_message)
        # print(Utils.dump_json(intention_data))
        # print(Utils.dump_json(lex_response))
        self.assertTrue(intention_data is not None)

        response, flag_for_new_session = Web.process_intention_and_slots(self.session, self.connection, received_message, intention_data, lex_response)
        # print(Utils.dump_json(response))
        self.assertTrue(response is not None)
        self.assertTrue(flag_for_new_session is False)
        self.assertTrue('message' in response and "You should try to use" in response['message'])

    def test_get_history(self):
        history = Web.get_history(self.session, self.connection)
        print(history)
        self.assertTrue(len(history) >= 0)

    def test_get_action_annotation(self):
        action_name        = "auxiliary/scanner/http/epmp1000_dump_hashes"
        action_annotations = Web.get_action_annotation(self.connection, action_name)
        print(action_annotations)
        self.assertTrue("description" in action_annotations)
        self.assertTrue("link"        in action_annotations)

    def test_get_missing_action_annotation(self):
        action_name = "missingactionanme"
        action_annotations = Web.get_action_annotation(self.connection, action_name)
        self.assertTrue(action_annotations is None)

    def test_get_port_annotation(self):
        port_number        = "tcp_80"
        port_annotations = Web.get_port_annotation(self.connection, port_number)
        print(port_annotations)
        self.assertTrue("description" in port_annotations)
        self.assertTrue("link"        in port_annotations)

    def test_get_application_annotation(self):
        application_name        = "http"
        application_annotations = Web.get_application_annotation(self.connection, application_name)
        print(application_annotations)
        self.assertTrue("description" in application_annotations)
        self.assertTrue("link"        in application_annotations)


