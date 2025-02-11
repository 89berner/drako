import copy
import time
import subprocess
import os
import traceback

import lib.Common.Exploration.Environment.Analysis as analysis

from lib.Common.Exploration.Environment.State   import State
from lib.Common.Exploration.Environment.Reward  import Reward
from lib.Common.Exploration.Environment.Session import Session

from lib.Common.Exploration.Environment.Observation import RawObservation
from lib.Common.Exploration.Environment.Observation import ProcessedObservation
import lib.Common.Utils.Log as Log
import lib.Common.Utils as Utils
import lib.Common.Utils.Constants as Constants

import lib.Common.Exploration.Environment.Validation as Validation
from   lib.Common.Recommendation.PredictionRequest import create_episode, create_game, request_agent_id, send_db_operation

terminating_strs = "AxnFopRwmlSanw92DngldA"

class Environment:
    def __init__(self, episode_length, episode_runner, episode_agent_name, environment_type, target, training_id):
        self.previous_state = State()
        self.current_state  = State()

        self.metasploit_client = None
        if training_id == None:
            self.training_id = 0 # We give a 0 to avoid database errors when None and request sent to predictor
        else:
            self.training_id = training_id
        self.agent_id          = None

        self.episode_id     = None
        self.target         = None
        self.target_ip      = None # This is different than the target since ips could change for a target and we want to avoid rewriting everything to use ids
        self.target_source  = None

        self.step_id        = 1
        self.positive_steps = 0
        self.game_steps = {
            "NETWORK": 1,
            "PRIVESC": 1,
        }

        self.agent_episode_points = 0
        self.agent_game_points    = 0

        self.episode_reward_reasons = []
        self.game_reward_reasons    = []

        self.had_error = False
        self.finished = False

        self.previous_game_type = "NETWORK"  # We always start from network
        self.current_game_type  = "NETWORK"  # We always start from network
        self.current_game_id    = None

        self.environment_type = environment_type

        # self.connection = connection

        self.episode_runner     = episode_runner
        self.episode_agent_name = episode_agent_name

        # CONSTANTS
        self.MAX_STEPS = {
            "total":   episode_length*2,
            "NETWORK": episode_length,
            "PRIVESC": episode_length
        }

        self.episode_configuration = {
            "ports": self.get_ports_data(),
        }
        self.set_target(target)

        # TODO: WE COULD MOVE THIS TO THE AGENT
        self.start_new_episode()
        self.start_new_game(self.current_game_type)

        self.last_gathered_metasploit_information = {}

    def set_metasploit_client(self, metasploit_client):
        self.metasploit_client = metasploit_client

    # EPISODE LOGIC
    def set_agent(self, agent):
        self.agent = agent

        if self.inside_a_container():
            agent_id = request_agent_id(self.training_id, self.get_container_id(),self.get_container_name())
            if agent_id != "":
                self.agent_id = agent_id
            else:
                Log.logger.Error("Error requesting an agent_id")

    def set_trainable_episode(self):
        stmt = "UPDATE episode set trainable=1 WHERE episode_id=%s AND training_id=%s"
        data = (self.episode_id, self.training_id)
        # self.connection.execute(stmt, data)
        send_db_operation(stmt, data)

    def set_test_episode(self):
        stmt = "UPDATE episode set test_episode=1 WHERE episode_id=%s AND training_id=%s"
        data = (self.episode_id, self.training_id)
        # self.connection.execute(stmt, data)
        send_db_operation(stmt, data)

    def mark_tester_episode_as_failure(self):
        stmt = "UPDATE test_episode set test_failed=1 WHERE episode_id=%s AND training_id=%s"
        data = (self.episode_id, self.training_id)
        # self.connection.execute(stmt, data)
        send_db_operation(stmt, data)

    def set_target(self, target):
        self.target = target
        self.update_target(target)
        self.previous_state.set_target(target)
        self.current_state.set_target(target)
        # Also set target ip as we set the initial target
        self.set_target_ip(target)

    def set_target_ip(self, target_ip):
        self.target_ip = target_ip
        self.previous_state.set_target_ip(target_ip)
        self.current_state.set_target_ip(target_ip)

    def get_target(self):
        return self.target

    def get_target_ip(self):
        return self.target_ip

    def update_target(self, target):
        stmt = "UPDATE episode set target=%s WHERE episode_id=%s AND training_id=%s"
        data = (target, self.episode_id, self.training_id)
        # self.connection.execute(stmt, data)
        send_db_operation(stmt, data)

    def start_new_episode(self):
        episode_configuration_json = Utils.dump_json(self.episode_configuration)

        # stmt = "INSERT INTO episode(target, runner, agent_name, environment, configuration, training_id) VALUES (%s,%s,%s,%s,%s,%s)"
        # data = (self.target, self.episode_runner, self.episode_agent_name, self.environment_type, episode_configuration_json, self.training_id)
        # self.episode_id = self.connection.execute(stmt, data)

        agent_name = ""
        if self.episode_agent_name is not None:
            agent_name = self.episode_agent_name

        self.episode_id = create_episode(self.target, self.episode_runner, agent_name, self.environment_type, episode_configuration_json, self.training_id)

        Log.logger.debug("Starting a new episode:%d" % self.episode_id)

    def start_new_test_episode(self):
        stmt = "INSERT INTO test_episode(episode_id, training_id) VALUES (%s,%s)"
        data = (self.episode_id, self.training_id)
        # self.connection.execute(stmt, data)
        send_db_operation(stmt, data)

    def start_new_game(self, game_type):
        # stmt = "INSERT INTO game(episode_id, training_id, name) VALUES (%s,%s,%s)"
        # data = (self.episode_id, self.training_id, game_type)
        # self.current_game_id = self.connection.execute(stmt,data)

        self.current_game_id = create_game(self.episode_id, self.training_id, game_type)

        Log.logger.debug("Starting a new game ot type:%s" % self.current_game_type)

        return True

    def mark_current_game_as_finished(self):
        Log.logger.debug("Will mark the current game as finished")
        stmt = "UPDATE game set accumulated_reward=%s, reward_reasons=%s, finished=1 WHERE game_id=%s AND training_id=%s"
        data = (self.agent_game_points, "|".join(self.game_reward_reasons), self.current_game_id, self.training_id)
        # self.connection.execute(stmt, data)
        send_db_operation(stmt, data)

    def set_game_type(self, game_type):
        # Log.logger.debug("Setting game type..")
        if self.current_game_type is None:
            raise ValueError("Gametype should never be None!")
        elif self.current_game_type != game_type:
            # This would happen when we are in the middle of one game and change to another one

            Log.logger.debug("Marking the previous game as finished")
            self.mark_current_game_as_finished()
            Log.logger.debug("Creating a new game entry")
            self.start_new_game(game_type)
        else:
            # Log.logger.debug("Nothing being done for game")
            # We are in the same game so no action is needed
            pass

        self.current_game_type  = game_type

    # REWARDS LOGIC

    def decide_reward(self, action_recommendation, processed_observation):
        Log.logger.debug("Will now decide the reward..")
        action_source  = action_recommendation.action_source
        action_reason  = action_recommendation.action_reason
        action_name    = action_recommendation.action_name
        action_options = action_recommendation.action_options
        action_extra   = action_recommendation.action_extra

        ###########################################################################################
        # Now lets go over all the changes to the state and add rewards
        ###########################################################################################

        # Get transactions
        transactions_since_step_started = processed_observation.get_accumulated_observed_state_diff()
        time_taken_for_observation      = processed_observation.conditions_time_taken
        previous_game_type              = self.get_previous_game_type()
        game_type                       = self.get_current_game_type()
        game_step                       = self.game_steps[game_type]
        observed_error                  = processed_observation.observed_error

        # Calculate reward reasons
        reward = Reward(game_step, transactions_since_step_started, time_taken_for_observation, self.previous_state, self.current_state, previous_game_type, game_type, observed_error, action_name)

        # DISABLED DUE TO DIFFICULTIES CONVERGING
        # reward.enable_penalty_for_errors()
        # reward.enable_penalty_for_steps_taken()
        # reward.enable_penalty_for_time_taken()
        # reward.enable_reward_for_network_information()
        reward.calculate_reward()

        reward_reasons             = reward.get_reward_reasons()
        reward_reasons_with_values = reward.get_reward_reasons_with_values()
        accumulated_reward         = reward.get_accumulated_reward()
        if accumulated_reward == 0:
            self.positive_steps += 1

        # ADD THE REWARDS TO THE GAME AND EPISODE ARRAYS
        for reward in reward_reasons_with_values:
            self.episode_reward_reasons.append(reward)
            self.game_reward_reasons.append(reward)

        ###########################################################################################
        # Finally store the information of the current step
        ###########################################################################################

        # 3) STORE INFORMATION OF OBSERVATION AND UPDATED STATE

        previous_state_json                  = self.previous_state.get_json()
        used_session_json                    = Utils.dump_json(processed_observation.used_session)
        action_options_json                  = Utils.dump_json(action_options)
        observation_json                     = processed_observation.get_json()
        current_state_json                   = self.get_json_state()
        reward_reasons_with_values_json      = Utils.dump_json(reward_reasons_with_values)
        transactions_since_step_started_json = Utils.dump_json(processed_observation.accumulated_observed_state_transactions)

        # REVIEW IF EPISODE FINISHED
        if self.step_id == self.MAX_STEPS['total']:
            Log.logger.debug("Setting environment as finished since we reached the max amount of steps")
            self.finished = True
        if Constants.REWARD_FOR_SUPER_USER_SESSION_KEY in reward_reasons:
            Log.logger.debug("Setting environment as finished since got a super user session!")
            self.finished = True

        # CREATE STATE HASH
        current_game_id    = self.current_game_id
        previous_game_type = self.get_previous_game_type()
        if previous_game_type is not None:
            prev_state_hash = self.previous_state.get_state_hash(self.get_previous_game_type())
        else:
            # prev_state_hash = "00000"
            raise ValueError("Previous game type cannot be None!")

        #### DEFINING GAME TYPE
        next_game_type  = self.agent.get_game_type()
        next_state_hash = self.current_state.get_state_hash(next_game_type)
        self.set_game_type(next_game_type)

        action_extra_json = Utils.dump_json_sorted_by_values(action_extra)

        # debug_data = {
        #     prev_state_hash: prev_state_observation.tolist(),
        #     next_state_hash: next_state_observation.tolist(),
        # }
        debug_data      = {}
        if self.agent.get_agent_options()['ADD_METASPLOIT_DATA_TO_STEP']:
            debug_data['metasploit_state'] = self.last_gathered_metasploit_information
        debug_data_json = Utils.dump_json_pretty(debug_data)

        # INSERTING STEP INTO DATABASE
        insert_statement = "INSERT INTO step(step_id, episode_id, training_id, game_id, agent_id, target, transactions_since_step_started, prev_state_hash, next_state_hash, prev_game_type, next_game_type, prev_state, next_state, session_data, session_command, action_source, action_reason, action_name, action_parameters, action_extra, processed_observation, accumulated_reward, reward_reasons, error, episode_finished, debug_data, time_spent) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
        data             = (
            self.step_id, self.episode_id, self.training_id, current_game_id, self.agent_id, self.target,
            transactions_since_step_started_json, prev_state_hash, next_state_hash, previous_game_type, next_game_type, previous_state_json, current_state_json,
            used_session_json,
            processed_observation.used_session_command, action_source, action_reason, action_name, action_options_json,
            action_extra_json,
            observation_json, accumulated_reward, reward_reasons_with_values_json,
            processed_observation.observed_error, self.finished, debug_data_json, processed_observation.conditions_time_taken
        )
        # self.connection.execute(insert_statement, data)
        send_db_operation(insert_statement, data)

        update_stmt = "UPDATE episode set positive_steps=%d, total_steps=%d,accumulated_reward=%d WHERE episode_id=%d AND training_id=%s" % (
        self.positive_steps, self.step_id, self.agent_episode_points, self.episode_id, self.training_id)
        # self.connection.execute(update_stmt)
        send_db_operation(update_stmt, [])

        # UPDATING DATABASE FOR ERRORS
        if self.had_error is False and processed_observation.observed_error is not None:
            Log.logger.debug(
                "Updating episode %d and game %d since it has an error.." % (self.episode_id, self.current_game_id))

            stmt = "UPDATE episode SET has_error = 1, episode_error=%s WHERE episode_id = %s AND training_id=%s"
            data = (processed_observation.observed_error, self.episode_id, self.training_id)
            # self.connection.execute(stmt, data)
            send_db_operation(stmt, data)

            stmt = "UPDATE game SET has_error = 1, game_error=%s WHERE game_id=%s AND training_id=%s"
            data = (processed_observation.observed_error, self.current_game_id, self.training_id)
            # self.connection.execute(stmt, data)
            send_db_operation(stmt, data)

            self.had_error = True

        # INCREMENTING EPISODE AND GAME REWARDS
        self.agent_episode_points += accumulated_reward
        self.agent_game_points    += accumulated_reward

        # Log.logger.debug("Finished writing..")
        self.step_id += 1
        self.game_steps[self.get_current_game_type()] += 1

        ###########################################################################################
        # Now lets make previous and current state the same
        ###########################################################################################

        self.previous_state     = copy.deepcopy(self.current_state)
        self.previous_game_type = self.current_game_type

        return accumulated_reward, reward_reasons_with_values

    def record_raw_observation(self, raw_observation):
        recording_raw_observation_enabled = False
        if recording_raw_observation_enabled:
            raw_observation_json = raw_observation.get_json()
            # Log.logger.debug(raw_observation_json)
            env_options_json = Utils.dump_json(raw_observation.env_options)
            session_user = None
            if raw_observation.used_session_data is not None:
                session_user = raw_observation.used_session_data["user"]

            stmt = "INSERT INTO raw_observation(episode_id, step_id, environment, action_name, action_type, env_action, env_options, data, session_data, session_user, error) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
            data = (self.episode_id, self.step_id, self.environment_type, raw_observation.action_name, raw_observation.action_type,
                 raw_observation.env_action, env_options_json, raw_observation_json,
                 Utils.dump_json(raw_observation.used_session_data), session_user, raw_observation.observed_error)
            # self.connection.execute(stmt, data)
            send_db_operation(stmt, data)
            # Log.logger.debug(res)

        return True

    def is_finished(self):
        # Log.logger.debug("Step for game %s is %d" % (self.current_game_type, self.game_steps[self.current_game_type]))
        if self.step_id > self.MAX_STEPS["total"]:
            Log.logger.debug("We finished after reaching %d total steps" % self.step_id)
            return True, "REACHED_MAX_TOTAL_STEPS"
        elif self.game_steps[self.current_game_type] > self.MAX_STEPS[self.current_game_type]:
            Log.logger.debug("We finished after reaching %d steps for game %s" % (self.step_id, self.current_game_type))
            return True, "REACHED_MAX_GAME_STEPS"
        elif self.finished:
            Log.logger.debug("We finished due to the flag finished being set")
            return True, "FINISH_FLAG"
        else:
            return False, ""

    def finish_step(self):
        finished, finish_reason = self.is_finished()
        if finished:
            self.close(finish_reason)
            Log.logger.warning("Closed the environment")

    def finish_episode(self, finish_reason, error_message=None):
        self.finished = True

        if error_message is not None:
            stmt = "UPDATE episode SET has_error = 1, episode_error=%s WHERE episode_id=%s AND training_id=%s"
            data = (error_message, self.episode_id, self.training_id)
            # self.connection.execute(stmt, data)
            send_db_operation(stmt, data)

        if finish_reason != None:
            stmt = "UPDATE episode SET finish_reason = %s WHERE episode_id=%s AND training_id=%s"
            data = (finish_reason, self.episode_id, self.training_id)
            # self.connection.execute(stmt, data)
            send_db_operation(stmt, data)

    def close(self, finish_reason):
        Log.logger.debug("Finishing episode..")
        self.finish_episode(finish_reason)

        Log.logger.debug("Closing step..")
        stmt = "UPDATE step SET episode_finished = 1 WHERE step_id = %s AND episode_id=%s AND training_id=%s" % (self.step_id - 1, self.episode_id, self.training_id)
        # self.connection.execute(stmt)
        send_db_operation(stmt, [])

        Log.logger.debug("Closing game..")
        self.mark_current_game_as_finished()

        Log.logger.debug("Closing environment..")

        stmt = "UPDATE episode SET accumulated_reward = %s, reward_reasons = %s, finished = 1 WHERE episode_id = %s AND training_id=%s"
        data = (self.agent_episode_points, "|".join(self.episode_reward_reasons), self.episode_id, self.training_id)
        # Log.logger.debug([stmt, data])
        # self.connection.execute(stmt, data)
        send_db_operation(stmt, data)

        Log.logger.debug("Closing agent")
        stmt = "UPDATE agent SET running=%s,has_session=0 WHERE agent_id=%s"
        data = (0, self.agent_id)
        send_db_operation(stmt, data)

        Log.logger.debug("Closing connection")
        # self.connection.close()

    def get_environment_options(self):
        return {
            'target':               self.target_ip,
            'target_source':        self.agent.get_agent_options()['TARGET_SOURCE'],
            'local_ip':             self.get_default_local_ip(),
            'reverse_shell_port':   self.get_default_reverse_shell_port(),
            'reverse_shell_port_2': self.get_default_reverse_shell_port_2(),
            'server_port':          self.get_default_server_port(),
        }

    def get_hosts(self):
        return self.current_state.get_hosts()

    def get_services(self):
        services = {
            "tcp": {},
            "udp": {},
        }
        for address in self.current_state.hosts:
            if 'ports' in self.current_state.hosts[address]:
                for protocol in self.current_state.hosts[address]["ports"]:
                    for port in self.current_state.hosts[address]["ports"][protocol]:
                        services[protocol][port] = self.current_state.hosts[address]["ports"][protocol][port]

        return services

    def get_open_ports(self):
        return self.current_state.get_open_ports()

    def get_json_state(self):
        return self.current_state.get_json()

    def get_json_previous_state(self):
        return self.previous_state.get_json()

    def get_sessions_dict(self):
        return self.current_state.get_sessions()

    def get_state_pretty(self):
        message = "State: %s" % self.current_state.get_json()
        return message

    def get_newest_session_id(self):
        return self.current_state.get_newest_session_id()

    def get_sessions_string(self):
        sessions_list = self.get_sessions_dict()
        print(sessions_list)

        message = "Active sessions\n==============="
        for session_id in sessions_list:
            session_data = sessions_list[session_id].get_dict()
            connection = "%s => %s (%s)" % (
                session_data["tunnel_local"], session_data["tunnel_peer"], session_data["target_host"])

            message += "\nID:%s\tType:%s\tInfo:%s\tConnection:%s" % (
                session_id, session_data["type"], session_data["info"], connection)

        return message

    # UTILS
    def get_default_apache_port(self):
        port = os.getenv('APACHE_PORT')
        if port is None:
            return Constants.AGENT_DEFAULT_APACHE_PORT
        return port

    def get_default_server_port(self):
        port = os.getenv('SRV_PORT')
        if port is None:
            return Constants.AGENT_DEFAULT_SRV_PORT
        return port

    def get_default_reverse_shell_port(self):
        port = os.getenv('REVSHELL_PORT')
        if port is None:
            return Constants.AGENT_DEFAULT_REVSHELL_PORT
        return port

    def get_default_reverse_shell_port_2(self):
        port = os.getenv('REVSHELL_PORT_2')
        if port is None:
            return Constants.AGENT_DEFAULT_REVSHELL_PORT_2
        return port

    def get_default_local_ip(self):
        local_ip = os.getenv('LOCAL_IP')
        if local_ip is None:
            raise ValueError("Variable LOCAL_IP is missing")
        return local_ip

    def get_postgressql_port(self):
        return Constants.AGENT_DEFAULT_POSTGRESSQL_PORT

    def get_msfrpc_port(self):
        return Constants.AGENT_DEFAULT_MSFRPC_PORT

    def inside_a_container(self):
        inside_docker = os.getenv('INSIDE_DOCKER')
        if inside_docker is None:
            return False
        return True

    def get_container_id(self):
        container_id = os.getenv('CONTAINER_ID')
        if container_id is None:
            return None
        return container_id

    def get_container_name(self):
        container_name = os.getenv('CONTAINER_NAME')
        if container_name is None:
            return None
        return container_name

    def set_container_waiting(self):
        has_session = int(self.session_is_available())
        # try:
        stmt = "UPDATE agent SET running=1, waiting=1, booting=0, has_session=%s WHERE container_id=%s AND training_id=%s"
        data = (has_session, self.get_container_id(), self.training_id)
        # self.connection.execute(stmt, data)

        send_db_operation(stmt, data)
        # except:
        #     Log.logger.error("Error trying to set container as waiting, will let it slide..")

    def set_container_not_waiting(self):
        has_session = int(self.session_is_available())
        # try:
        stmt = "UPDATE agent SET running=1, waiting=0, has_session=%s WHERE container_id=%s AND training_id=%s"
        data = (has_session, self.get_container_id(), self.training_id)
        # self.connection.execute(stmt, data)
        send_db_operation(stmt, data)
        # except:
        #     Log.logger.error("Error trying to set container as not waiting, will let it slide..")

    def get_ports_data(self):
        ports_configuration = {
            "APACHE_PORT":     self.get_default_apache_port(),
            "SRV_PORT":        self.get_default_server_port(),
            "REVSHELL_PORT":   self.get_default_reverse_shell_port(),
            "LOCAL_IP":        self.get_default_local_ip(),
            "POSTGRESQL_PORT": self.get_postgressql_port(),
            "MSFRPCD_PORT":    self.get_msfrpc_port(),
        }

        return ports_configuration

    # GETTERS

    def get_current_game_type(self):
        return self.current_game_type

    def get_previous_game_type(self):
        return self.previous_game_type

    def CreateProcessedObservation(self, action_name, description, time_taken, raw_observations, error=None,
                                   observed_data={}):

        # LETS ADD THE TIME OF ALL OBSERVATIONS
        accumulated_time_taken = time_taken
        for observation in raw_observations:
            try:
                accumulated_time_taken += observation.time_taken
            except:
                # TODO: Remove when we fixed the RawObservations
                # TODO: add an error if we try to use a processed observation here
                Log.logger.warning("IMPORTANTMARKHERE => This triggered a problem with observation.time_taken that should not happen")
                accumulated_time_taken += observation.conditions_time_taken

            observed_error = observation.get_observed_error()
            if observed_error is not None:
                if error is not None:
                    error += "\n"
                else:
                    error = ""
                error += observed_error

        processed_observation = ProcessedObservation(action_name, description, accumulated_time_taken, raw_observations, error)

        ###########################################################################################
        # now lets add information to the current state
        ###########################################################################################

        ## PROCESS THE OBSERVED DATA, ADDING TO STATE INFORMATION
        loot_discovered = []
        for observed_type in observed_data:
            if observed_type == "loot":
                loot_data = observed_data[observed_type]
                for loot_type in loot_data:
                    if loot_type == "file_content":
                        for entry in loot_data[loot_type]:
                            self.current_state.add_file_content(entry)
                            # perform analysis on the file contents of the file
                            loot_discovered += analysis.discover_loot(entry["address"], entry["file_contents"])
                    elif loot_type == "files_list":
                        address = loot_data[loot_type]["address"]
                        files_map = loot_data[loot_type]["files"]
                        for file in files_map:
                            filesize = files_map[file]
                            self.current_state.add_file_found(address, file, filesize)

        # PROCESS ANY LOOT DISCOVERED
        for loot in loot_discovered:
            loot_type = loot["loot_type"]
            loot_space = loot["loot_space"]
            if loot_type == "credentials":
                self.current_state.add_credentials(loot["address"], loot_space, loot)
            else:
                raise NotImplementedError("Unknown loot type: %s" % loot_type)

        ###########################################################################################
        # Now we get the transactions since the start of the step and since the last raw observation (what the processed obs generated)
        ###########################################################################################

        transactions_since_step_started        = self.current_state.get_and_clean_transactions_since_step_started()
        transactions_since_last_raw_observaton = self.current_state.get_and_clean_transactions_since_last_raw_observaton()

        processed_observation.set_accumulated_observed_state_transactions(transactions_since_step_started)
        processed_observation.set_local_observed_state_transactions(transactions_since_last_raw_observaton)

        return processed_observation

    def run_shell_command_with_output_in_session(self, session, session_command, timeout):
        session_command_with_terminating_str = session_command + ";echo %s" % terminating_strs

        if str(type(session)) != "<class 'pymetasploit3.msfrpc.ShellSession'>":
            Log.logger.debug("Running in meterpreter command: %s" % session_command_with_terminating_str)
            output = session.run_with_output(session_command_with_terminating_str, [terminating_strs], timeout=timeout,
                                             timeout_exception=False).strip()
        else:
            Log.logger.debug("Running in shell command: %s" % session_command)
            output = session.run_with_output(session_command_with_terminating_str, [terminating_strs], timeout=timeout).strip()

        Log.logger.debug("Output of shell command %s" % output)
        # CLEAN THE SHELL OUTPUT BASED ON TERMINATING_STR
        output = output.replace(terminating_strs, "").strip()  # remove terminating string added

        return output

    def add_port_to_state(self, host, port, protocol, state, name, info):
        # WE DO A HC EVEN IF THE PORT WAS KNOWN SINCE WE COULD BE ADDING WRONG DATA TO THE PORT IF IT WAS DOWN NOW
        valid_port = Validation.check_port_is_opened(host, port, protocol, timeout=5, delay=1, retries=3)
        if valid_port:
            # If valid lets add it
            self.current_state.add_service(host, port, protocol, state, name, info)
            return True
        else:
            Log.logger.warning(f"Port {port}({protocol}) is closed")
            return False

    def CreateRawObservation(self, action_name, action_type, env_action, env_options, observed_output, time_taken, delay_to_observe,
                             session_data=None, session_command=None, error=None):
        ### 
        ### Raw observations when created should immediatly update the environment with any new information
        ### So that we can track what a raw observation gets back
        ###
        # to avoid too much logging
        # Flag to add extra debugging
        # Log.setup_super_logger()

        raw_observation = RawObservation(action_name, action_type, env_action, env_options, observed_output, time_taken,
                                         session_data, session_command, error)

        if error is None:
            Log.logger.debug("Sleeping for %s seconds to delay observation.." % delay_to_observe)
            time.sleep(int(delay_to_observe))  # lets wait before observing

        metasploit_data = self.metasploit_client.gather_current_metasploit_information()
        self.last_gathered_metasploit_information = metasploit_data # to use to store in our step

        ###########################################################################################
        # Lets add information to the state
        ###########################################################################################

        # NEW HOSTS
        hosts_list = metasploit_data['hosts_list']
        # Log.logger.warning(hosts_list)
        for host in hosts_list:
            # Validate OS NAME and OS FLAVOR
            os_name, os_flavor = Validation.check_os_name_and_port(host['os_name'], host['os_flavor'])

            self.current_state.add_host(host["address"], host['name'], os_name, os_flavor)

        # NEW SERVICES
        services_list = metasploit_data['services_list']
        # Log.logger.warning(services_list)
        for service in services_list:
            # First we validate that the information we got is correct
            if service['state'] == Constants.OPEN_PORT:
                port_added = self.add_port_to_state(service['host'], service["port"], service['proto'], service['state'], service['name'], service["info"])

                if not port_added:
                    message = f"Port {service['port']}({service['proto']}) is closed according to the Validator\n"
                    if error is None:
                        error = message
                    else:
                        error += message
            else:
                pass
                #Log.logger.warning(f"Ignoring port not opened, state is {service['state']}")

        # NEW NOTES
        # TODO: REVIEW IF WE SHOULD USE NOTES
        notes = metasploit_data['notes']
        for note in notes:
            # Log.logger.warning(note)
            address   = note["host"]
            port      = note["service"]
            note_type = note["type"]

            if 'proto' in note:
                protocol = note["proto"]
            else:
                protocol = "tcp"
                # Log.logger.debug(f"No proto in note: {note}")

            if note_type == "smb.shares":
                self.current_state.add_note(address, port, note_type, note["data"], protocol)
                # FIRST ADD PORT

        # NEW VULNS
        vulns = metasploit_data['vulns']
        for vuln in vulns:
            Log.logger.warning(vuln)

        # NEW EVENTS
        # events = metasploit_data['events']
        # for event in events:
        #     Log.logger.warning(event)

        # NEW COMMANDS
        if session_data is not None and session_command is not None:
            address = session_data['tunnel_peer'].split(":")[0]

            if "platform" in session_data:
                platform = session_data['platform']
            else:
                platform = ""

            self.current_state.add_session_command(address, platform, session_data['info'], session_command,
                                                   observed_output)

        # Set maps to new values
        sessions_map = metasploit_data['sessions_map']
        Log.super_logger.warning(sessions_map)

        for session_id in sessions_map:
            session_data = sessions_map[session_id]
            session_obj  = Session(session_data)
            Log.super_logger.warning(session_obj.get_dict())

            if session_obj.no_user_is_known():
                # TODO: THIS NEEDS TO RUN IN THE METERPRETER SHELL

                # Log.logging.debug("METHOD 1:")
                # Log.logging.debug("METHOD 1:")
                # Log.logging.debug("METHOD 1:")
                # if session_obj.username_is_unknown():
                #     Log.logger.debug("Will try with \"getuid\" to get the user of the session...")

                #     session = self.metasploit_client.client.sessions.session(session_id)

                #     try:
                #         output = self.run_shell_command_with_output_in_session(session, "getuid", 20)
                #         # output = session.run_with_output("getuid", terminating_strs, timeout=20).strip()
                #         Log.logger.debug("output of running getuid: %s" % output)
                #     except:
                #         Log.logger.warning("Exception trying to get user with getuid: %s" % traceback.format_exc())

                #     session_data_map = self.metasploit_client.get_current_metasploit_sessions()
                #     if session_id in session_data_map:
                #         session_obj = Session(session_data_map[session_id])
                #     else:
                #         raise ValueError(f"Lost session {session_id} after trying to execute the getuid command to get a user")

                # Log.logging.debug("METHOD 2:")
                # Log.logging.debug("METHOD 2:")
                # Log.logging.debug("METHOD 2:")

                # if session_obj.username_is_unknown():
                #     Log.logger.debug("Will try with \"whoami\" to get the user of the session...")
                #     session = self.metasploit_client.client.sessions.session(session_id)

                #     try:
                #         # def run_shell_command_in_session(self, action_name, action_type, delay_to_observe, session_id, session_command,
                #         #          timeout=20):

                #         # output = self.run_shell_command_in_session("test", "test", 20, session_id, "whoami", 20)

                #         # TODO: MERGE WITH RUN COMMAND IN SESSION
                #         if str(type(session)) != "<class 'pymetasploit3.msfrpc.ShellSession'>":
                #             retries = 1
                #             while retries <= 5:
                #                 # start shell, rewrite of session.start_shell() since it does not allow to specify endstr
                #                 Log.logger.debug("[%d] Attempting to get inside meterpreter shell" % retries)
                #                 cmd      = 'shell'

                #                 end_strs = ['Process']
                #                 session  = self.metasploit_client.client.sessions.session(session_id)
                #                 output   = session.run_with_output(cmd, end_strs, timeout=10, timeout_exception=False).strip()
                #                 if "[-] Unknown command: shell." in output:
                #                     Log.logger.error("Error creating shell!")
                #                     retries += 1
                #                 else:
                #                     break

                #             # Log.logger.debug("Running in shell command: %s" % session_command)
                #             # output = session.run_with_output(session_command_with_terminating_str, [terminating_strs], timeout=timeout,
                #             #                                  timeout_exception=False).strip()
                #             output = self.run_shell_command_with_output_in_session(session, "whoami", 20)
                #         else:
                #             # Log.logger.debug("Running in shell command: %s" % session_command)
                #             # output = session.run_with_output(session_command_with_terminating_str, [terminating_strs], timeout=timeout).strip()
                #             output = self.run_shell_command_with_output_in_session(session, "whoami", 20)

                #         Log.logger.debug("Got as output of whoami: %s" % output)
                #     except:
                #         Log.logger.warning("Exception trying to get user with whoami: %s" % traceback.format_exc())

                #     session_data_map = self.metasploit_client.get_current_metasploit_sessions()
                #     if session_id in session_data_map:
                #         session_obj = Session(session_data_map[session_id])
                #     else:
                #         raise ValueError(f"Lost session {session_id} after trying to execute the whoami command to get a user")


                # Lets try with whoami if we still don't have the data
                counter   = 0
                MAX_TRIES = 3
                while counter <= MAX_TRIES: # Lets try 3 times
                    counter += 1
                    if session_obj.username_is_unknown():
                        Log.logger.debug("(%d/%d) Will try with \"whoami\" to get the user of the session..." % (counter, MAX_TRIES))
                        session = self.metasploit_client.client.sessions.session(session_id)

                        output = ""
                        try:
                            output = self.run_shell_command_with_output_in_session(session, "whoami", 20)
                            output = output.split("\n")[0]
                            Log.logger.debug("Got as output of whoami: %s" % output)
                        except:
                            Log.logger.warning("Exception trying to get user with whoami: %s" % traceback.format_exc())
                            continue

                        if output in Constants.SUPER_USERS_LIST:
                            session_obj.set_username(output)
                            session_obj.set_user(output)
                        else:
                            Log.logging.debug("output of %s does not match a super user to set")

                        break

                        # session_data_map = self.metasploit_client.get_current_metasploit_sessions()
                        # if session_id in session_data_map:
                        #     session_obj = Session(session_data_map[session_id])
                        # else:
                        #     raise ValueError(f"Lost session {session_id} after trying to execute the whoami command to get a user")
                    else:
                        break

            Log.super_logger.warning(session_obj.get_dict())
            self.current_state.add_session(session_id, session_obj.get_dict())

        # Remove any extra sessions
        self.current_state.remove_missing_sessions(sessions_map)

        self.current_state.set_jobs_map(metasploit_data['jobs_list'])

        ###########################################################################################
        # Now lets update thra transactions log for the raw observation
        ###########################################################################################

        transactions_log = self.current_state.get_and_clean_transactions_since_last_raw_observaton()
        raw_observation.set_transactions_log(transactions_log)

        # Log.teardown_super_logger()

        return raw_observation

    def get_current_status(self):
        current_status_message = "Episode_id: %s\nStep_id: %s\nState: \n%s\nAgent accumulated points: %s" % (
            self.episode_id, self.step_id, self.current_state.get_json(), self.agent_episode_points)

        return current_status_message

    def session_is_available(self):
        if len(self.current_state.sessions) > 0:
            return True
        else:
            return False

    def web_application_available(self):
        return False


class NetworkEnvironment(Environment):
    def __init__(self, episode_length, episode_runner, agent_name, target, training_id):
        Environment.__init__(self, episode_length, episode_runner, agent_name, "NETWORK", target, training_id)

    def run_command_in_session(self, action_name, action_type, delay_to_observe, session_id, session_command,
                               terminating_strs):
        env_action = "run_command_in_session"
        env_options = {
            "session_command": session_command,
            "terminating_strs": terminating_strs,
        }

        start_time = time.time()
        session = self.metasploit_client.client.sessions.session(session_id)

        # Log.logger.debug("CLASS: %s" % str(type(session)))

        error_msg = None
        if str(type(session)) == "<class 'pymetasploit3.msfrpc.ShellSession'>":
            error_msg = "Cannot run meterpreter comand on shell session!"
            Log.logger.error(error_msg)
            output = error_msg
        else:
            # Log.logger.debug(session)
            # if (str(type(session)) == "<class 'pymetasploit3.msfrpc.ShellSession'>"):
            #     output  = session.run_with_output(session_command, terminating_strs, timeout=20).strip()
            # else:
            output = session.run_with_output(session_command, terminating_strs, timeout=20,
                                             timeout_exception=False).strip()

        time_taken = time.time() - start_time

        # Create and record raw observation
        session_data    = self.current_state.sessions[session_id].get_dict()
        raw_observation = self.CreateRawObservation(action_name, action_type, env_action, env_options, output, time_taken,
                                                    delay_to_observe, session_data, session_command, error=error_msg)
        self.record_raw_observation(raw_observation)
        # ! Create and record raw observation

        # Ensure we leave the session
        try:
            self.metasploit_client.perform_execution("auxiliary", "background", {})
        except:
            Log.logger.warning("Error trying to leave session: %s" % traceback.format_exc())

        return raw_observation

    def run_shell_command_in_session(self, action_name, action_type, delay_to_observe, session_id, session_command,
                                     timeout=20):
        env_action = "run_shell_command_in_session"
        env_options = {
            "session_command": session_command,
        }

        start_time = time.time()

        session = self.metasploit_client.client.sessions.session(session_id)

        # end_strs  = ['Process']
        error_msg = None
        # No point in opening a shell if we have a shell session

        # WE CAN BE EITHER DEALING WITH A SHELL SESSION OR A MTERPRETER SESSION THAT NEEDS TO DROP DOWN TO SHELL
        if str(type(session)) != "<class 'pymetasploit3.msfrpc.ShellSession'>":
            retries = 1
            while retries <= 5:
                # start shell, rewrite of session.start_shell() since it does not allow to specify endstr
                Log.logger.debug("[%d] Attempting to get inside meterpreter shell" % retries)
                cmd      = 'shell'

                end_strs = ['Process']
                session  = self.metasploit_client.client.sessions.session(session_id)
                output   = session.run_with_output(cmd, end_strs, timeout=10, timeout_exception=False).strip()
                if "[-] Unknown command: shell." in output:
                    Log.logger.error("Error creating shell!")
                    retries += 1
                else:
                    break

            # Log.logger.debug("Running in shell command: %s" % session_command)
            # output = session.run_with_output(session_command_with_terminating_str, [terminating_strs], timeout=timeout,
            #                                  timeout_exception=False).strip()
            output = self.run_shell_command_with_output_in_session(session, session_command, timeout)
        else:
            # Log.logger.debug("Running in shell command: %s" % session_command)
            # output = session.run_with_output(session_command_with_terminating_str, [terminating_strs], timeout=timeout).strip()
            output = self.run_shell_command_with_output_in_session(session, session_command, timeout)

        extra = session.read()  # Clear buffer
        # Log.logger.debug("EXTRA IS => %s" % extra)

        if str(type(session)) != "<class 'pymetasploit3.msfrpc.ShellSession'>": 
            res = session.detach()

            if 'result' in res and res['result'] != 'success':
                Log.logger.debug(res)
                raise ValueError("Shell failed to exit on meterpreter session %s => %s" % (session.sid, res['result']))
        else:
            Log.logger.warning("Once inside a shell session it cannot be detached!")

        time_taken = time.time() - start_time

        # Create raw observation
        session_data = self.current_state.sessions[session_id].get_dict()
        raw_observation = self.CreateRawObservation(action_name, action_type, env_action, env_options, output, time_taken,
                                                    delay_to_observe, session_data, session_command, error=error_msg)
        self.record_raw_observation(raw_observation)

        # # Ensure we leave the session
        # try:
        #     self.metasploit_client.perform_execution("auxiliary", "background", {})
        # except:
        #     Log.logger.warn("Error trying to leave session: %s" % traceback.format_exc())

        return raw_observation

    def execute_meterpreter_command(self, action_name, action_type, delay_to_observe, command, options):
        env_action = "execute_meterpreter_command"
        env_options = {
            "command": command,
            "options": options,
        }

        error_msg = None
        start_time = time.time()
        try:
            output = self.metasploit_client.perform_execution(action_type, command, options)
        except:
            # TODO: Review if we should treat this as a normal error or like now
            # which means we still capture whatever information comes back
            error_msg = "ERROR: %s" % traceback.format_exc()
            output = error_msg
            Log.logger.debug(error_msg)
            self.metasploit_client.terminate_running_jobs_for_workspace()
        # Log.logger.debug(output)
        time_taken = time.time() - start_time

        # Create raw observation
        raw_observation = self.CreateRawObservation(action_name, action_type, env_action, env_options, output, time_taken,
                                                    delay_to_observe, error=error_msg)
        self.record_raw_observation(raw_observation)
        # ! Create and record raw observation

        return raw_observation

    def execute_meterpreter_oneliner_command(self, action_name, action_type, delay_to_observe, command, options):
        ## this should cater for one liners that are faked as having options like db_nmap
        return self.execute_meterpreter_command(action_name, action_type, delay_to_observe, command,
                                                {})  # We don't pass the options to avoid metasploit running them

    def run_local_command(self, action_name, action_type, delay_to_observe, command_array):
        env_action = "run_local_command"
        env_options = {
            "command_array": command_array,
        }

        start_time = time.time()
        result = subprocess.run(command_array, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time_taken = time.time() - start_time

        command_output = result.stdout.decode("utf-8").strip()

        error = None
        if result.returncode != 0:
            error = result.stderr.decode("utf-8").strip()

        # Create raw observation
        raw_observation = self.CreateRawObservation(action_name, action_type, env_action, env_options, command_output, time_taken,
                                                    delay_to_observe, error=error)
        Log.logger.debug(raw_observation.get_observation_dict())
        self.record_raw_observation(raw_observation)
        # ! Create and record raw observation

        return raw_observation

    def execute_meterpreter_command_that_downloads_file(self, action_name, action_type, delay_to_observe, command,
                                                        options):
        env_action = "execute_meterpreter_command_that_downloads_file"
        env_options = {
            "command": command,
            "options": options,
        }

        start_time = time.time()
        output = self.metasploit_client.perform_execution(action_type, command, options)

        # log.add_debug_separator()
        Log.logger.debug("Output for command is: %s" % output)

        # NOW PARSE THE FILENAME
        file_path = ""
        for line in output.split("\n"):
            Log.logger.debug(line)
            if "saved as: " in line:
                file_path = line.split("saved as: ")[1]

        if file_path == "":
            raise ValueError("File was not saved into our directory")

        with open(file_path, 'r') as file:
            file_contents = file.read().strip()

        time_taken = time.time() - start_time

        # Create raw observation
        raw_observation = self.CreateRawObservation(action_name, action_type, env_action, env_options, file_contents, time_taken,
                                                    delay_to_observe)
        self.record_raw_observation(raw_observation)
        # ! Create and record raw observation

        return raw_observation

class DreamatoriumEnvironment(Environment):
    def __init__(self, episode_length, episode_runner, agent_name, target, training_id):
        raise NotImplemented("This has been disabled!")

# class DreamatoriumEnvironment(Environment):
#     def __init__(self, episode_length, episode_runner, agent_name, target, training_id):
#         Environment.__init__(self, episode_length, episode_runner, agent_name, "DREAMATORIUM", target, training_id)

#     def modify_key_in_path(self, current_state_dict, path, value):
#         if len(path) > 1:
#             Log.logger.debug("Path is larger than 1, will enter: %s" % path)
#             key_to_enter = path.pop(0)
#             if key_to_enter not in current_state_dict:
#                 current_state_dict[key_to_enter] = {}
#             self.modify_key_in_path(current_state_dict[key_to_enter], path, value)
#         else:
#             Log.logger.debug("Got to the final path, will modify the value in: %s" % current_state_dict)

#             key = path.pop()
#             if value in current_state_dict:
#                 Log.logger.debug("Value was %s" % current_state_dict[key])
#             else:
#                 Log.logger.debug("There was no value to replace")
#             current_state_dict[key] = value

#     def add_key_in_path(self, current_state_dict, path, key, value):
#         Log.logger.debug("Got current_state_dict:%s path:%s key:%s value:%s" % (current_state_dict, path, key, value))
#         if len(path) > 0:
#             Log.logger.debug("Path is not empty, will go inside the path")
#             Log.logger.debug(path)
#             key_to_enter = path.pop(0)
#             if key_to_enter not in current_state_dict:
#                 current_state_dict[key_to_enter] = {}
#             self.add_key_in_path(current_state_dict[key_to_enter], path, key, value)
#         else:
#             Log.logger.debug("Got an empty path, will insert now the key and value in %s" % current_state_dict)
#             # NOW CHECK IF THE KEY IS MISSING OR THE VALUE IS NOT A DICTIONARY
#             if key not in current_state_dict or not isinstance(current_state_dict[key], dict):
#                 if key in current_state_dict and current_state_dict[key] != "":
#                     Log.logger.warning(
#                         "Add operationg wants to modify data that already exists! Current value is \"%s\" and it would modify it to \"%s\". We won't for now." % (
#                             current_state_dict[key], value))
#                 else:
#                     current_state_dict[key] = value
#             else:
#                 value_dict = value
#                 Log.logger.debug(
#                     "We need to now enter the dictionary %s\n to add %s as much as possible to avoid removing data" % (
#                         current_state_dict, value_dict))
#                 dict_where_to_replace = current_state_dict[key]
#                 for key_to_add in value_dict.keys():
#                     if key_to_add not in dict_where_to_replace:
#                         Log.logger.debug("Should add data on %s" % key_to_add)
#                     else:
#                         Log.logger.debug("Should enter %s to add more data" % key_to_add)
#                         self.add_key_in_path(dict_where_to_replace, [], key_to_add, value_dict[key_to_add])

#                 Log.logger.debug("Current state dict now:\n%s" % current_state_dict)
#                 # We already had the key, so lets perform the same inside
#                 # add_key_in_path(current_state_dict[key], [], key,value):
#                 # time.sleep(100)

#     def patch_dictionary(self, list_diff_state, current_state_dict):
#         # log.add_debug_separator()
#         # list_diff_state = list(diff_state)
#         Log.logger.debug("diff_state:\n%s" % list_diff_state)
#         Log.logger.debug("current state dict:\n%s" % current_state_dict)

#         for patch in list_diff_state:
#             operation = patch[0]
#             path = patch[1]
#             # Make paths a list
#             if isinstance(path, str):
#                 if "." in path:
#                     path = path.split(".")
#                 else:
#                     path = [path]
#             entry_data = patch[2]

#             Log.logger.debug(
#                 "Will now apply the \"%s\" patch for \"%s\" with data:\n%s" % (operation, path, entry_data))
#             if operation == "add":
#                 # if (not isinstance(entry_data[0], str)):
#                 data = entry_data[0]
#                 # else:
#                 #     data = entry_data

#                 key = data[0]
#                 value = data[1]
#                 Log.logger.debug("Key:%s => Value:%s" % (key, value))

#                 # MODIFY STATE UPDATING TRANSACTION
#                 previous_state = copy.deepcopy(self.current_state.get_state_dict())
#                 self.add_key_in_path(current_state_dict, path, key, value)
#                 self.current_state.save_state_change_transaction(previous_state)

#             elif operation == "change":
#                 data = entry_data

#                 prev_value = data[0]
#                 new_value = data[1]
#                 Log.logger.debug("Prev value:\"%s\" New value:\"%s\"" % (prev_value, new_value))

#                 # MODIFY STATE UPDATING TRANSACTION
#                 previous_state = copy.deepcopy(self.current_state.get_state_dict())
#                 self.modify_key_in_path(current_state_dict, path, new_value)
#                 self.current_state.save_state_change_transaction(previous_state)

#                 # time.sleep(2)
#             elif operation == "remove":
#                 Log.logger.warning("Will not patch a remove operation for now")
#                 # time.sleep(1000)

#             Log.logger.debug("After operation state is:\n%s" % current_state_dict)

#     def CreateRawObservation(self, action_name, action_type, data):
#         env_action      = data["conditions"]["env_action"]
#         env_options     = data["conditions"]["env_options"]
#         observed_output = data["observed"]["output"]
#         time_taken      = data["conditions"]["time_taken"]
#         session_data    = data["used"]["session_data"]
#         session_command = data["used"]["session_command"]
#         error           = data["observed"]["error"]

#         raw_observation = RawObservation(action_name, action_type, env_action, env_options, observed_output, time_taken,
#                                          session_data, session_command, error)

#         transactions = data["observed"]["transactions_log"]
#         Log.logger.debug(transactions)

#         self.patch_dictionary(transactions, self.current_state.get_state_dict())

#         Log.logger.debug("Resulting current state")
#         Log.logger.debug(self.current_state.get_state_dict())

#         return raw_observation

#     def _load_raw_observation(self, action_name, env_action, env_options, session_user=None):
#         env_options_json = Utils.dump_json(env_options)

#         # LOAD RAW OBSERVATION FROM DB
#         if session_user is None:
#             stmt = "SELECT data, action_type FROM raw_observation WHERE env_action=%s AND env_options=%s LIMIT 1"  # ORDER BY RAND() removed for debugging
#             data = (env_action, env_options_json)
#             results = self.connection.query(stmt, data)
#         else:
#             stmt = "SELECT data, action_type FROM raw_observation WHERE env_action=%s AND env_options=%s AND session_user=%s LIMIT 1"  # ORDER BY RAND() removed for debugging
#             data = (env_action, env_options_json, session_user)
#             results = self.connection.query(stmt, data)
#             if len(results) == 0:
#                 Log.logger.warning("Did not dream of a command for user %s, will get any" % session_user)

#                 stmt = "SELECT data, action_type FROM raw_observation WHERE env_action=%s AND env_options=%s LIMIT 1"  # ORDER BY RAND() removed for debugging
#                 data = (env_action, env_options_json)
#                 results = self.connection.query(stmt, data)

#         if len(results) > 0:
#             # Log.logger.debug(results[0]["data"])
#             data        = Utils.json_loads(results[0]["data"])
#             action_type = results[0]['action_type']
#             raw_observation = self.CreateRawObservation(action_name, action_type, data)

#             return raw_observation
#         else:
#             raise ValueError("There is no data to dream about")

#     def run_command_in_session(self, action_name, action_type, delay_to_observe, session_id, session_command,
#                                terminating_strs):
#         env_action = "run_command_in_session"
#         env_options = {
#             "session_command": session_command,
#             "terminating_strs": terminating_strs,
#         }

#         session_data = self.current_state.sessions[session_id].get_dict()
#         session_user = session_data["user"]

#         raw_observation = self._load_raw_observation(action_name, env_action, env_options, session_user)

#         return raw_observation

#     def run_shell_command_in_session(self, action_name, action_type, delay_to_observe, session_id, session_command,
#                                      terminating_strs, timeout=20):
#         env_action = "run_shell_command_in_session"
#         env_options = {
#             "session_command": session_command,
#             "terminating_strs": terminating_strs,
#         }

#         session_data = self.current_state.sessions[session_id].get_dict()
#         session_user = session_data["user"]

#         raw_observation = self._load_raw_observation(action_name, env_action, env_options, session_user)

#         return raw_observation

#     def execute_meterpreter_command(self, action_name, action_type, delay_to_observe, command, options):
#         env_action = "execute_meterpreter_command"
#         env_options = {
#             "command": command,
#             "options": options,
#         }

#         raw_observation = self._load_raw_observation(action_name, env_action, env_options)

#         return raw_observation

#     def execute_meterpreter_oneliner_command(self, action_name, action_type, delay_to_observe, command, options):
#         ## this should cater for one liners that are faked as having options like db_nnamp
#         return self.execute_meterpreter_command(action_name, action_type, delay_to_observe, command,
#                                                 {})  # We don't pass the options to avoid metasploit running them

#     def run_local_command(self, action_name, command_array):
#         env_action = "run_local_command"
#         env_options = {
#             "command_array": command_array,
#         }

#         raw_observation = self._load_raw_observation(action_name, env_action, env_options)

#         return raw_observation

#     def execute_meterpreter_command_that_downloads_file(self, action_name, action_type, delay_to_observe, command,
#                                                         options):
#         env_action = "execute_meterpreter_command_that_downloads_file"
#         env_options = {
#             "command": command,
#             "options": options,
#         }

#         raw_observation = self._load_raw_observation(action_name, env_action, env_options)

#         return raw_observation
