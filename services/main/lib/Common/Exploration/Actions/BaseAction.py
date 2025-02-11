from abc import ABC, abstractmethod


class BaseAction(ABC):
    @abstractmethod
    def execute(self, options):
        # HERE WE SHOULD CALL THE ENVIRONMENT, GET ITS OUTPUT AND CREATE AN OBSERVATION
        # WITH THE FULL RESPONSE AND WHAT WE FILTERED OUT
        pass

    @abstractmethod
    def create_observation(self, raw_observations):
        pass

    @abstractmethod
    def get_options(self):
        pass

    def get_option(self, options, key):
        return options[key.upper()]

    def get_mandatory_options(self):
        options_to_return = {}

        options = self.get_options()
        for option in options:
            if options[option]["required"] == "yes":
                options_to_return[option] = options[option]
                # Log.logger.warning(options[option])

        return options_to_return

    def is_debug(self):
        return False

class DebugBaseAction(BaseAction):
    def is_debug(self):
        # HERE WE SHOULD CALL THE ENVIRONMENT, GET ITS OUTPUT AND CREATE AN OBSERVATION
        # WITH THE FULL RESPONSE AND WHAT WE FILTERED OUT
        return True
