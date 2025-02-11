from abc import ABC, abstractmethod
import lib.Common.Utils.Log as Log
import lib.Common.Utils as utils
import lib.Common.Utils.Constants as Constants

# from lib.Exploration.Agent.Utils import load_agent_options
from lib.Common.Recommendation.PredictionRequest import request_agent_options

class BaseAgent(ABC):
    def __init__(self, environment):
        self.environment = environment
        # self.connection  = environment.connection

        self.agent_options = None
        self.update_agent_options()

        self.target, self.target_ip = self.get_target()

        self.environment.set_target(self.target)
        self.environment.set_target_ip(self.target_ip)

        Log.logger.debug(f"Setting target to {self.target} and target_ip to {self.target_ip}")

        self.state_action_history = {}

        Log.logger.debug("Finished running init for BaseAgent")

    def update_agent_options(self):
        self.agent_options = request_agent_options()

    def get_agent_options(self):
        return self.agent_options

    def get_game_type(self):
        return self.environment.current_state.deduce_game_type()

    def handle_error(self, processed_observation):
        Log.logger.warning("Nothing is done!")

    # def handle_error(self, processed_observation):
    #     # Log.logger.debug("Error was found: %s!" % processed_observation.observed_error)
    #     raise ValueError("Stopping all container function on error => %s" % processed_observation.observed_error)

    def should_we_finish_episode(self):
        return True, "BASE_REASON"

    def should_we_run_step(self):
        return True

    def get_next_action_from_agent(self):
        # THE FOLLOWING IS LOGIC NEEDED JUST TO PICK THE ACTION
        state_hash = self.environment.current_state.get_state_hash(self.get_game_type())
        if state_hash not in self.state_action_history:
            self.state_action_history[state_hash] = []
        action_history = self.state_action_history[state_hash]

        ####### ACTUAL RECOMMENDATION LOGIC ########
        action_recommendation = self.get_next_action_from_agent_specific(action_history)
        ####### ACTUAL RECOMMENDATION LOGIC ########

        # Lets store the actions sent back for later use
        action_history_entry = {
            "action_source":      action_recommendation.action_source,
            "action_name_picked": action_recommendation.action_name,
            "action_options":     action_recommendation.action_options,
        }
        self.state_action_history[state_hash].append(action_history_entry)

        return action_recommendation

    # THIS NEEDS TO RETURN AN action_recommendation object
    @abstractmethod
    def get_next_action_from_agent_specific(self, action_history):
        raise NotImplementedError("You need to implement this method!")

    @abstractmethod
    def get_target(self):
        raise NotImplementedError("You need to implement this method!")

class BaseTrainingAgent(BaseAgent, ABC):
    def __init__(self, *args):
        self.tester_agent = False
        super().__init__(*args)
        self.environment.set_trainable_episode()
        Log.logger.debug("Finished running init for BaseTrainingAgent")
        
    def get_target(self):
        return self.agent_options["TRAINING_TARGET"], self.agent_options["TRAINING_TARGET_IP"]

    def should_we_finish_episode(self):
        """
            Checks if the target has changed
        :return: Whether we should end the episode
        """
        if self.agent_options["STOP_AGENTS"]:
            Log.logger.debug("Stopping agent due to STOP_AGENTS flag")
            return True, "STOP_AGENTS"
        else:
            pass
            # Log.logger.debug("Value for STOP_AGENTS is %d" % agent_options["STOP_AGENTS"])

        if self.agent_options["TRAINING_TARGET"] != self.target:
            Log.logger.debug(f'Stopping agent due to TRAINING_TARGET {self.agent_options["TRAINING_TARGET"]} being different than self.target {self.target}')
            return True, "TRAINING_TARGET_IS_DIFFERENT"
        else:
            return False, "FALSE"

    def handle_error(self, processed_observation):
        err = processed_observation.observed_error
        # TODO: REVIEW TO MAKE THIS UNNECESSARY
        if "invalid start byte" in err or ("Session ID (" in err and ") does not exist" in err) or "SESSION AVAILABLE IS ALREADY METERPRETER SESSION" in err or "File was not saved into our directory" in err or "ValueError: [-] No results from search" in err or "Error setting the following information" in err or "Timed out after waiting for" in err or "Timeout waiting for console to stop being busy after" in err:
            Log.logger.warning("Error happened but we will allow it! => %s" % err)
        else:
            raise ValueError("Error happened, we must stop agent: %s" % err)
            # The reason we do this is since if not exploits get confused output since we cant properly stop them if there is a timeout

    def should_we_run_step(self):
        should_we_pause_agent              = self.agent_options['PAUSE_TRAINING_AGENTS']
        should_we_pause_agents_in_net_game = self.agent_options['PAUSE_TRAINING_AGENTS_IN_NET_GAME']
        Log.logger.debug([should_we_pause_agent, should_we_pause_agents_in_net_game, self.get_game_type()])

        if should_we_pause_agent:
            Log.logger.debug("We need to pause agent due to PAUSE_TRAINING_AGENTS")
            return False
        elif should_we_pause_agents_in_net_game and self.get_game_type() == Constants.GAME_TYPE_NETWORK:
            Log.logger.debug("We need to pause agents in net game")
            return False
        else:
            return True

class BaseTesterAgent(BaseAgent, ABC):
    def __init__(self, *args):
        self.tester_agent = True
        super().__init__(*args)
        self.environment.set_test_episode()
        self.environment.start_new_test_episode()
        Log.logger.debug("Finished running init for BaseTester")

    def get_target(self):
        import numpy #Import here to avoid using the ram unnecessary

        """ Tester should get multiple targets to see how good it is against many """
        # agent_options = load_agent_options(self.connection, attributes=["TESTER_TARGET"])
        target = self.agent_options["TESTER_TARGET"]

        if "," in target:
            return numpy.choice(target.split(",")), self.agent_options["TESTER_TARGET_IP"] # Choose a random target if in comma separated form
        else:
            return target, self.agent_options["TESTER_TARGET_IP"]

    def should_we_finish_episode(self):
        Log.logger.debug("Will check if we should finish the episode.. ")

        if self.agent_options["TESTER_TARGET"] != self.target:
            Log.logger.debug("Stopping agent due to TESTER_TARGET being different")
            self.environment.mark_tester_episode_as_failure()  # If we change target mid test the values are not relevant
            return True, "TESTER_TARGET_IS_DIFFERENT"

        if self.agent_options["STOP_AGENTS"]:
            Log.logger.debug("Stopping agent due to STOP_AGENTS flag")
            return True, "STOP_AGENTS"

        Log.logger.debug(f"Value for STOP_AGENTS is {self.agent_options['STOP_AGENTS']}")

        return False, "FALSE"

    def handle_error(self, processed_observation):
        Log.logger.warning("Error happened but we will allow it for testing! => %s" % processed_observation.observed_error)

    def should_we_run_step(self):
        if self.agent_options['PAUSE_TESTER_AGENTS']:
            return False
        else:
            return True
