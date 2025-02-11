import os
import dataclasses

from lib.Common.Exploration.Actions.BaseAction import DebugBaseAction
import lib.Common.Utils as Utils
import lib.Common.Exploration.Actions as Actions

import lib.Common.Recommendation.PredictionRequest as PredictionRequest

class DebugHosts(DebugBaseAction):
    def __init__(self, environment, action_name):
        self.environment = environment
        self.action_name = action_name

    def execute(self, options):
        hosts = self.environment.get_hosts()

        output = "Hosts are: %s" % hosts
        processed_observation = self.create_observation(output)

        return processed_observation

    def create_observation(self, message):
        processed_observation = self.environment.CreateProcessedObservation(self.action_name, message, time_taken=0,
                                                                            raw_observations=[])
        processed_observation.set_debug()

        return processed_observation

    def get_options(self):
        return {}


class DebugServices(DebugBaseAction):
    def __init__(self, environment, action_name):
        self.environment = environment
        self.action_name = action_name

    def execute(self, options):
        services = self.environment.get_services()

        output = "Services are: %s" % Utils.dump_json(services)
        processed_observation = self.create_observation(output)

        return processed_observation

    def create_observation(self, message):
        processed_observation = self.environment.CreateProcessedObservation(self.action_name, message, time_taken=0,
                                                                            raw_observations=[])
        processed_observation.set_debug()

        return processed_observation

    def get_options(self):
        return {}


class DebugListAllActions(DebugBaseAction):
    def __init__(self, environment, action_name):
        self.environment = environment
        self.action_name = action_name

    def execute(self, options):
        actions_list = Actions.client.get_all_actions()

        output = "All actions available are:\n%s" % "\n".join(actions_list)
        processed_observation = self.create_observation(output)

        return processed_observation

    def create_observation(self, message):
        processed_observation = self.environment.CreateProcessedObservation(self.action_name, message, time_taken=0,
                                                                            raw_observations=[])
        processed_observation.set_debug()

        return processed_observation

    def get_options(self):
        return {}


class DebugListMainActions(DebugBaseAction):
    def __init__(self, environment, action_name):
        self.environment = environment
        self.action_name = action_name

    def execute(self, options):
        actions_list = Actions.client.get_main_actions()

        output = "Main actions available are:\n%s" % "\n".join(actions_list)
        processed_observation = self.create_observation(output)

        return processed_observation

    def create_observation(self, message):
        processed_observation = self.environment.CreateProcessedObservation(self.action_name, message, time_taken=0,
                                                                            raw_observations=[])
        processed_observation.set_debug()

        return processed_observation

    def get_options(self):
        return {}


class DebugStatus(DebugBaseAction):
    def __init__(self, environment, action_name):
        self.environment = environment
        self.action_name = action_name

    def execute(self, options):
        status_message = self.environment.get_current_status()

        output = "Status is:\n%s" % status_message
        processed_observation = self.create_observation(output)

        return processed_observation

    def create_observation(self, message):
        processed_observation = self.environment.CreateProcessedObservation(self.action_name, message, time_taken=0,
                                                                            raw_observations=[])
        processed_observation.set_debug()

        return processed_observation

    def get_options(self):
        return {}


class DebugClear(DebugBaseAction):
    def __init__(self, environment, action_name):
        self.environment = environment
        self.action_name = action_name

    def execute(self, options):
        os.system('clear')

        processed_observation = self.create_observation("")

        return processed_observation

    def create_observation(self, message):
        processed_observation = self.environment.CreateProcessedObservation(self.action_name, message, time_taken=0,
                                                                            raw_observations=[])
        processed_observation.set_debug()

        return processed_observation

    def get_options(self):
        return {}


class DebugHelp(DebugBaseAction):
    def __init__(self, environment, action_name):
        self.environment = environment
        self.action_name = action_name

    def execute(self, options):
        message = """Drako command line interface, you can use the following commands:

actions:     Shows main available actions
all_actions: Shows all available actions
status:      Shows the current state of the game
hosts:       Shows current known hosts in state
services:    Shows current known services in state
clear:       Clear the console
help:        Display this message"""

        processed_observation = self.create_observation(message)

        return processed_observation

    def create_observation(self, message):
        processed_observation = self.environment.CreateProcessedObservation(self.action_name, message, time_taken=0,
                                                                            raw_observations=[])
        processed_observation.set_debug()

        return processed_observation

    def get_options(self):
        return {}


class DebugExit(DebugBaseAction):
    def __init__(self, environment, action_name):
        self.environment = environment
        self.action_name = action_name

    def execute(self, options):
        message = "Exiting..."
        processed_observation = self.create_observation(message)

        return processed_observation

    def create_observation(self, message):
        processed_observation = self.environment.CreateProcessedObservation(self.action_name, message, time_taken=0,
                                                                            raw_observations=[])
        processed_observation.set_debug()

        return processed_observation

    def get_options(self):
        return {}


class ListSessions(DebugBaseAction):
    def __init__(self, environment, action_name):
        self.environment = environment
        self.action_name = action_name

    def execute(self, options):
        message = self.environment.get_sessions_string()
        processed_observation = self.create_observation(message)

        return processed_observation

    def create_observation(self, message):
        processed_observation = self.environment.CreateProcessedObservation(self.action_name, message, time_taken=0,
                                                                            raw_observations=[])
        processed_observation.set_debug()

        return processed_observation

    def get_options(self):
        return {}

class PredictAction(DebugBaseAction):
    def __init__(self, environment, action_name):
        self.environment = environment
        self.action_name = action_name

    def execute(self, options):
        extra_data                 = {"skip_payload": "1"}
        prediction_name            = options['PREDICTION_NAME'].upper()
        action_recommendation      = PredictionRequest.request_action(self.environment, self.environment.get_target(), self.environment.current_state, [], prediction_name, extra_data)
        action_recommendation_dict = dataclasses.asdict(action_recommendation)

        message = Utils.dump_json(action_recommendation_dict)

        processed_observation = self.create_observation(message)

        return processed_observation

    def create_observation(self, message):
        processed_observation = self.environment.CreateProcessedObservation(self.action_name, message, time_taken=0, raw_observations=[])
        processed_observation.set_debug()

        return processed_observation

    def get_options(self):
        return {
            "PREDICTION_NAME": {
                "required": "yes",
                "type": "string",
                "description": "Name of the prediction to request",
            }
        }