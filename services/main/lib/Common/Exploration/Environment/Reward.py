import math

from lib.Common.Exploration.Environment.State   import State
from lib.Common.Exploration.Environment.Session import Session
import lib.Common.Utils.Log as Log
import lib.Common.Utils.Constants as Constants

class Reward:
    def __init__(self, game_step: int, transactions_since_step_started: list, time_taken_for_observation: float, previous_state: State, current_state: State, previous_game_type:str, game_type: str, observed_error: str, action_name: str = None):
        self.transactions_since_step_started = transactions_since_step_started
        self.time_taken_for_observation      = time_taken_for_observation
        self.previous_state                  = previous_state
        self.current_state                   = current_state
        self.previous_game_type              = previous_game_type
        self.game_type                       = game_type
        self.observed_error                  = observed_error
        self.game_step                       = game_step
        self.action_name                     = action_name

        self.reward_reasons = []

        self.add_reward_for_network_information = False
        self.add_penalty_for_time_taken         = False
        self.add_penalty_for_steps_taken        = False
        self.add_penalty_for_errors             = False
        self.do_reward_only_ending              = False
        self.do_normalize_rewards               = False

        # The following are flags in place to avoid providing multiple rewards when more than one session is returned
        self.rewarded_super_session          = False
        self.rewarded_regular_session        = False
        self.session_user_became_super_added = False

    def rewarding_only_ending(self, state):
        self.do_reward_only_ending = state

    def normalize_rewards(self, state):
        self.do_normalize_rewards = state

    def penalty_for_time_taken(self, state):
        self.add_penalty_for_time_taken = state

    def penalty_for_steps_taken(self, state):
        self.add_penalty_for_steps_taken = state

    def penalty_for_errors(self, state):
        self.add_penalty_for_errors = state

    def reward_for_network_information(self, state):
        self.add_reward_for_network_information = state

    def calculate_reward(self):
        """
            Calculates all the reward variables
        :return:
        """
        self._calculate_reward_reasons()
        # Log.logger.debug("Starting")
        self.accumulated_reward, self.reward_reasons_with_values = self._calculate_accumulated_reward()
        # Log.logger.debug("Calculated accumulated_reward and reward_reasons_with_values: %s -> %s" (self.accumulated_reward, self.reward_reasons_with_values))

        if self.add_penalty_for_time_taken:
            self._apply_penalty_for_time_taken()
        # Log.logger.debug("Calculated time penalty")
        if self.add_penalty_for_steps_taken:
            self._apply_penalty_for_steps_taken()
        # Log.logger.debug("Calculated steps taken penalty")
        if self.add_penalty_for_errors:
            self._apply_penalty_for_errors()
        # Log.logger.debug("Calculated error penalty")

    def get_reward_reasons_with_values(self):
        return self.reward_reasons_with_values

    def get_reward_reasons(self):
        return self.reward_reasons

    def get_accumulated_reward(self):
        return self.accumulated_reward

    def _apply_penalty_for_errors(self):
        # ADD PENALTIES FOR ERRORS
        if self.observed_error and "Error setting the following information" in self.observed_error:
            self.accumulated_reward = 0
            self.reward_reasons_with_values.append("Error on observation due to lack of necessary state, reset to 0")
        elif self.observed_error and int(self.time_taken_for_observation) <= 1:
            self.accumulated_reward -= 500000
            self.reward_reasons_with_values.append("Error on observation while spending less than one second")
        elif self.observed_error:
            self.accumulated_reward -= 250000
            self.reward_reasons_with_values.append("Error on observation")

    def _apply_penalty_for_steps_taken(self):
        # Provide a discount on log2 as the episodes progress
        previous_reward = self.accumulated_reward
        step_penalty = math.log2(self.game_step + 1)
        self.accumulated_reward /= step_penalty
        self.reward_reasons_with_values.append("Reward %s was reduced by %f due to step position for game %s, now reward is %s" % (previous_reward, step_penalty, self.game_type, self.accumulated_reward))

    def _apply_penalty_for_time_taken(self):
        # ADD PENALTY FOR NO POINTS RECEIVED
        if self.accumulated_reward == 0:
            pentaly_reward = 1000
            # ADD PENALTY FOR TIME TAKEN
            pentaly_reward += int(self.time_taken_for_observation) * 100
            self.accumulated_reward -= pentaly_reward
            self.reward_reasons_with_values.append("Time penalty:-1%d" % pentaly_reward)

    def _decide_extra_rewards_for_commands_result(self, full_path, data_added):
        # Log.logger.info(data_added)
        if len(full_path) == 3:  # We dont have the user in the path
            # Log.logger.info(len(full_path))
            commands_map = data_added[0][1]
        elif len(full_path) == 4:
            # Log.logger.info(len(full_path))
            commands_map = data_added[0]
            commands_map = {commands_map[0]: commands_map[1]}
        elif len(full_path) == 5:
            # Log.logger.info(len(full_path))
            command = full_path[4]
            uuid = data_added[0][0]
            output = data_added[0][1]
            commands_map = {command: {uuid: output}}
        else:
            raise NotImplementedError("Unknown amount of paths %d to process for command" % len(full_path))

    def _decide_reward_for_adding_information_to_state(self, path, full_path, data_added):
        # Adding at top level
        if path == "hosts":
            self.reward_reasons.append("new_host_added")
        # Adding for a particular host
        elif path.startswith("hosts#"):
            path_after_ip = full_path[2]

            if path_after_ip == "information":
                self.reward_reasons.append("new_host_information_added")
            elif path_after_ip == "commands_result":
                self.reward_reasons.append("new_command_result")
                self._decide_extra_rewards_for_commands_result(full_path, data_added)
            elif path_after_ip == "loot":
                loot_type = full_path[3]
                if loot_type == "file_contents":
                    self.reward_reasons.append("new_file_contents")
                elif loot_type == "credentials":
                    self.reward_reasons.append("new_credentials_added")
                elif loot_type == "files_list":
                    self.reward_reasons.append("new_file_discovered")
            elif path_after_ip == "ports":
                if len(full_path) == 4:  # Just the port added
                    # Log.logger.debug([path, full_path, data_added])
                    self.reward_reasons.append("new_port_added")
                    for data in data_added:
                        # Log.logger.info(data)
                        if data[0] == "state" and data[1] == "open":
                            self.reward_reasons.append("new_open_port_added")
                else:
                    if full_path[5] == "information":
                        # Log.logger.debug([path, full_path, data_added])
                        self.reward_reasons.append("new_port_information_added")
                        for data in data_added:
                            # Log.logger.info(data)
                            if data[0] == "state" and data[1] == "open":
                                self.reward_reasons.append("new_port_open_information_added")
                    elif full_path[5] == "notes":
                        self.reward_reasons.append("new_port_note_added")

    def _decide_reward_for_changing_information_in_state(self, path, full_path):
        if path.startswith("hosts#"):
            path_after_ip = full_path[2]
            if path_after_ip == "commands_result":
                self.reward_reasons.append("host_commands_result_information_modified")
            elif path_after_ip == "ports":
                self.reward_reasons.append("host_ports_information_modified")
            else:
                self.reward_reasons.append("host_information_modified")
        elif path.startswith("sessions#"):
            self.reward_reasons.append("session_data_modified")

            for session_id in self.previous_state.sessions:
                previous_session = self.previous_state.sessions[session_id]
                if session_id in self.current_state.sessions:
                    current_session = self.current_state.sessions[session_id]

                    if not previous_session.is_super_user_session() and current_session.is_super_user_session():
                        # WE USED TO Check if we went from non super to super
                        # BUT THIS THEN GIVES US REWARDS FOR RANDOM ACTIONS

                        # self.reward_reasons.append(Constants.REWARD_FOR_SUPER_USER_SESSION_KEY)
                        # self.rewarded_super_session = True

                        if not self.session_user_became_super_added:
                            self.reward_reasons.append("session_user_became_super")
                            self.session_user_became_super_added = True

    def _decide_reward_for_adding_session_information(self, path, data_added):
        if path == "sessions":
            # Log.logger.debug([path, data_added])
            session_id = data_added[0][0]
            # Log.logger.debug("Found session_id %s will check if we have it" % session_id)
            if session_id in self.current_state.sessions:
                new_session_data = self.current_state.sessions[session_id].get_dict()
                # Log.logger.debug([session_id, self.current_state.sessions])

                new_host_is_target        = new_session_data["target_host"] == self.current_state.get_target_address()
                previous_game_was_network = self.previous_game_type == Constants.GAME_TYPE_NETWORK

                if 'via_exploit' not in new_session_data:
                    Log.logger.warning(f"Session data is missing the via_exploit key: {new_session_data}")
                    return
                elif self.action_name is not None and not new_session_data['via_exploit'].endswith(self.action_name):
                    Log.logger.warning(f"REVIEW_THIS: We are not rewarding this step since the step action {self.action_name} is not the one in the session {new_session_data['via_exploit']}")
                    return

                if new_host_is_target:
                    is_super_user_session = Session(new_session_data).is_super_user_session() # TODO: Couldn't we just use the self.current_state.sessions[session_id] object?
                    if is_super_user_session and not self.rewarded_super_session:
                        self.reward_reasons.append(Constants.REWARD_FOR_SUPER_USER_SESSION_KEY)
                        self.rewarded_super_session = True
                    elif previous_game_was_network and not self.rewarded_regular_session:
                            self.reward_reasons.append(Constants.REWARD_FOR_REGULAR_USER_SESSION_KEY)
                            self.rewarded_regular_session = True
                else:
                    Log.logger.warning("REVIEW_THIS: HOST OF SESSION IS NOT OUR TARGET, IGNORING THIS!")
            else:
                Log.logger.warning("REVIEW_THIS: WARNING, WE WERE ASKED TO REWARD FOR A NEW SESSION NOT PRESENT")
        elif path == "jobs":
            self.reward_reasons.append("new_job_added")

    def _calculate_reward_reasons(self):
        for change in self.transactions_since_step_started:
            operation = change[0]
            path = change[1]
            data_added = change[2]

            # to track if there is any added
            init_reward_reasons_amount = len(self.reward_reasons)

            # Log.logger.info(change)
            full_path = path
            if not isinstance(full_path, str):
                path = "#".join(str(e) for e in full_path)  # since port numbers are ints
            else:
                path = full_path.replace(".", "#")

            # Log.logger.info("Need to decide reward for %s of path %s with data %s" % (operation, path, data_added))
            if operation == "add":
                if self.add_reward_for_network_information:
                    self._decide_reward_for_adding_information_to_state(path, full_path, data_added)

                self._decide_reward_for_adding_session_information(path, data_added)
            elif operation == "change":
                self._decide_reward_for_changing_information_in_state(path, full_path)

            # if len(self.reward_reasons) == init_reward_reasons_amount and path != "jobs" and operation != "remove":  # jobs can be missing rewards
            #     if self.add_reward_for_network_information:
            #         raise NotImplementedError("Did not add a reward! This should never happen!")

    def _calculate_accumulated_reward(self) -> (int, list):
        accumulated_reward = 0
        reward_reasons_with_values = []

        for reward_reason in self.reward_reasons:
            if reward_reason == Constants.REWARD_FOR_REGULAR_USER_SESSION_KEY:
                reward_provided = Constants.REWARD_FOR_REGULAR_USER_AMOUNT
            elif reward_reason == Constants.REWARD_FOR_SUPER_USER_SESSION_KEY:
                reward_provided = Constants.REWARD_FOR_SUPER_USER_AMOUNT
            # elif not self.do_reward_only_ending:
            #     if reward_reason == "new_host_added":
            #         reward_provided = 0
            #     elif reward_reason == "new_host_information_added":
            #         reward_provided = 30
            #     elif reward_reason == "host_information_modified":
            #         reward_provided = 25
            #     elif reward_reason == "new_port_added":
            #         reward_provided = 15
            #     elif reward_reason == "new_open_port_added":
            #         reward_provided = 35
            #     elif reward_reason == "new_port_information_added":
            #         reward_provided = 25
            #     elif reward_reason == "new_port_open_information_added":
            #         reward_provided = 35
            #     elif reward_reason == "session_data_modified":
            #         reward_provided = 25
            #     elif reward_reason == "new_job_added":
            #         reward_provided = 0
            #     elif reward_reason == "new_command_result":
            #         reward_provided = 10
            #     elif reward_reason == "escalate_to_admin":
            #         reward_provided = max_reward * 0.7
            #     elif reward_reason == "new_file_contents":
            #         reward_provided = 4
            #     elif reward_reason == "new_credentials_added":
            #         reward_provided = 35
            #     elif reward_reason == "new_port_note_added":
            #         reward_provided = 3
            #     elif reward_reason == "new_file_discovered":
            #         reward_provided = 1
            #     elif reward_reason == "host_ports_information_modified":
            #         reward_provided = 0
            #     elif reward_reason == "host_commands_result_information_modified":
            #         reward_provided = 0
            #     else:
            #         raise NotImplementedError("I dont know what reward to give to %s" % reward_reason)
            else:
                reward_provided = 0

            if self.do_normalize_rewards:
                reward_provided /= 4

            accumulated_reward += reward_provided
            reward_reasons_with_values.append("%s:%d" % (reward_reason, reward_provided))

        return accumulated_reward, reward_reasons_with_values
