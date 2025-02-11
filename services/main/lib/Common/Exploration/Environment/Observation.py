import json
import lib.Common.Utils as Utils

class RawObservation:
    def __init__(self, action_name, action_type, env_action, env_options, observed_output, time_taken, session_data, session_command,
                 error=None):
        # OBSERVED
        self.action_name     = action_name
        self.action_type     = action_type
        self.env_action      = env_action
        self.env_options     = env_options
        self.observed_output = observed_output

        self.transactions_log = None

        if error is not None:
            self.observed_error = error
        else:
            self.observed_error = None

        # USED
        self.used_session_data = session_data
        self.used_session_command = session_command

        # CONDITIONS
        self.time_taken = time_taken

    def set_transactions_log(self, transactions_log):
        self.transactions_log = transactions_log

    def get_observed_error(self):
        return self.observed_error

    def get_observation_dict(self):
        return {
            "observed": {
                "output": self.observed_output,
                "error": self.observed_error,
                "transactions_log": self.transactions_log,
            },
            "used": {
                "session_command": self.used_session_command,
                "session_data": self.used_session_data,
            },
            "conditions": {
                "time_taken": self.time_taken,
                "env_action": self.env_action,
                "env_options": self.env_options,

            }
        }

    def get_json(self):
        return Utils.dump_json(self.get_observation_dict())


class ProcessedObservation:
    def __init__(self, action_name, description, time_taken, raw_observations, error=None):
        self.action_name = action_name
        self.description = description
        self.raw_observations = raw_observations

        # PROCESS ERRORS
        self.observed_error = error
        if self.observed_error is not None:
            self.description = self.observed_error

        ## DEFAULTS
        self.conditions_is_debug   = False
        self.conditions_time_taken = time_taken
        self.used_session          = None
        self.used_session_command  = None

        # WE SHOULD NOW HAVE THE CURRENT STATE MODIFIED BY ANY RAW OBSERVATIONS PRESENT, SO WE WILL NOW ADD TO THAT ANY 
        # CHANGES FROM OUR PROCESSED OBSERVATION AND THEN COMPARE BACK TO THE ORIGINAL STATE
        self.accumulated_observed_state_transactions = []
        self.local_observed_state_transactions       = []

        ##### FINISH

    def get_accumulated_observed_state_diff(self):
        return self.accumulated_observed_state_transactions

    def get_observed_error(self):
        return self.observed_error

    def set_session_data(self, used_session, used_session_command):
        self.used_session = used_session
        self.used_session_command = used_session_command

    def set_accumulated_observed_state_transactions(self, transactions):
        self.accumulated_observed_state_transactions = transactions

    def set_local_observed_state_transactions(self, transactions):
        self.local_observed_state_transactions = transactions

    def set_debug(self):
        self.conditions_is_debug = True

    def get_summary(self):
        message = self.get_full_json()

        return message

    def _get_observation_dict(self):
        return {
            "observed": {
                "accumulated_state_transactions": self.accumulated_observed_state_transactions,
                "local_state_transactions": self.local_observed_state_transactions,
                "description": self.description,
                "error": self.observed_error,
            },
            "used": {
                "session": self.used_session,
                "session_command": self.used_session_command,
            },
            "conditions": {
                "debug": self.conditions_is_debug,
                "time_taken": self.conditions_time_taken,
            },
        }

    def get_json(self):
        observation_map = self._get_observation_dict()
        # return json.dumps(observation_map, indent=4, sort_keys=True, separators=(',', ': '), cls=Utils.CustomEncoder)

        return Utils.dump_json_with_separators(observation_map, (',', ': '))
