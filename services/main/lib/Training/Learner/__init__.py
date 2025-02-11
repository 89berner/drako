import os
import time
import requests
import traceback

import torch.optim      as optim
from torch import device as torch_device
from torch.cuda import is_available as torch_cuda_is_available
from torch import save as torch_save
from torch import load as torch_load

import lib.Training.Learner.ExperienceBuffer as ExperienceBuffer
import lib.Common.Training.Learner
import lib.Common.Utils.Constants as Constants
import lib.Common.Utils.Log as Log

from lib.Common.Exploration.Environment.State import State

from lib.Common.Exploration.Environment.Environment import Reward
import lib.Common.Utils as Utils
from lib.Common.Utils.Db import Db

from lib.Training.Learner.Logging import LoggerHelper
import lib.Common.Training.DQN as CommonDQN

from lib.Common.Training.Learner import get_main_training_ids

import time

# Childs will have to implement learner_name and learner_family
class BaseLearner:
    def __init__(self, game_type, training_id, load_main_training, profile, continue_from_latest_point, params_to_override, benchmark_id, force_cpu, staging_connection):

        self.game_type                  = game_type
        self.benchmark_id               = benchmark_id
        self.training_id                = training_id
        self.load_main_training         = load_main_training
        self.continue_from_latest_point = continue_from_latest_point
        self.profile                    = profile

        self.train_on_transitions = self.profile not in ["EXPLORE"]

        Log.logger.debug(params_to_override)
        Log.logger.debug(benchmark_id)
        Log.logger.debug(force_cpu)

        Log.logger.debug(f"Creating learner of game_type:{game_type} learner_family:{self.learner_family} learner_name:{self.learner_name}")

        # Start setting options from the config table, they are stored in self.learner_options
        self.params_to_override = params_to_override

        if staging_connection is None:
            self.staging_connection = Db(db_host=Constants.DRAGON_STAGING_DB_IP, db_name=Constants.get_dragon_staging_db(), db_password=Constants.DRAGON_DB_PWD)
        else:
            self.staging_connection = staging_connection

        self.prod_connection = Db(db_host=Constants.DRAGON_PROD_DNS,      db_name=Constants.DRAGON_PROD_DB_NAME,    db_password=Constants.DRAGON_DB_PWD)

        # ATTRIBUTES
        self.folder_path  = f"{Constants.NETWORKS_FOLDER_PATH}/{self.training_id}"
        self.nn_filename  = f"{self.folder_path}/{self.learner_name}_{self.game_type}.pt"

        # DEFAULTS
        self.SEED                 = "12345"
        self.target               = ""
        self.ADDITIONAL_LOGGING   = False
        self.device               = None
        self.training_network     = None
        self.target_network       = None
        self.optimizer            = None
        self.experience_buffer    = None
        self.training_game_id     = None
        self.latest_transition_id = 0
        self.step_counter         = 0  # This is incremented every time we add something to the buffer
        self.train_counter        = 0
        self.stored_nn_versions   = []  # helper to delete previous nn versions
        self.last_transition_id_used_for_state_upload = 0
        self.observation_shape_size = len(State().get_transform_state_to_observation(self.game_type))
        self.AMOUNT_OF_STEPS_PER_EXTRA_LOGGING = 100

        # OPTIONS TO BE SET MANUALLY
        self.stop_training_after                = None
        self.skip_until_reaching                = None
        self.training_starts_at_rewarding_games = False
        self.train_only_on_target               = None
        self.pause_benchmark_at                 = None

        # BENCHMARK DEFAULTS
        self.benchmark_counter         = 0
        self.benchmark_ongoing         = False
        self.benchmark_last_transition = None
        self.benchmark_target          = None
        self.training_limit            = None
        self.benchmark_transitions_from_good_episodes = []
        self.map_of_target_to_episode_id              = {}
        self.target_to_state_actions_tuple            = {}
        self.map_target_to_non_reward_steps           = {}

        # INIT COMPONENTS
        self.init_learner_options(params_to_override)

        self.load_actions_to_use()

        # we can't avoid loading this for exploration since we need qvals in many places
        # todo: remove this dependency so we can avoid loading it for explore
        self.init_pytorch(force_cpu)
        self.init_load_main_training()
        self.setup_optimizer()

        self.init_experience_buffer()

        self.initial_state_hashes = {} # This is populated every time we get data from the steps table
        self.LoggerHelper = LoggerHelper(self.training_id, self.experience_buffer, self.game_type, self.actions_to_use, self.training_network, self.device, self.staging_connection, self.prod_connection, self.initial_state_hashes, self.CREATE_PER_TARGET_STATES, self.profile)

        empty_observation = State().get_transform_state_to_observation(self.game_type)
        empty_state_hash  = State().get_state_hash(self.game_type)
        self.LoggerHelper.print_network_top_20(empty_state_hash, empty_observation)

    #########################################
    ################ <INITS> ################
    #########################################

    def init_learner_options(self, configuration_override = None):
        """
            Sets into the object the options loaded from the training_config table.
            Description for each parameter is stored in the table
        :return:
        """
        self.learner_options      = lib.Common.Training.Learner.load_learner_options(self.prod_connection, self.learner_family, self.learner_name, game_type=self.game_type)
        self.benchmark_config_map = lib.Common.Training.Learner.load_benchmark_config_options(self.prod_connection, self.game_type, self.learner_family, self.learner_name)

        Log.logger.debug(self.learner_options)

        if configuration_override is not None:
            # Log.logger.debug(self.learner_options)
            # Log.logger.debug(self.configuration_override)
            self.learner_options = {**self.learner_options, **configuration_override}

        # HYPERPARAMETERS
        self.BATCH_SIZE                     = self.learner_options["BATCH_SIZE"]
        self.SYNC_TARGET_STEPS              = self.learner_options["SYNC_TARGET_STEPS"]
        self.REPLAY_START_SIZE              = self.learner_options["REPLAY_START_SIZE"]
        self.LEARNING_RATE                  = self.learner_options["LEARNING_RATE"]
        self.BUFFER_SIZE                    = self.learner_options["BUFFER_SIZE"]
        self.STEPS_PER_PRIORITIES_PRINT     = self.learner_options["STEPS_PER_PRIORITIES_PRINT"]
        self.STEPS_PER_NN_SAVE              = self.learner_options["STEPS_PER_NN_SAVE"]
        self.USE_TRAINING_NETWORK_AS_TARGET = self.learner_options["USE_TRAINING_NETWORK_AS_TARGET"]
        self.DQN_GAMMA                      = self.learner_options["DQN_GAMMA"]
        self.BOOST_REWARDS                  = self.learner_options["BOOST_REWARDS"]
        self.FREEZE_REWARDS                 = self.learner_options["FREEZE_REWARDS"]

        self.STEPS_FOR_PRE_TRAINING_DATA       = self.learner_options["STEPS_FOR_PRE_TRAINING_DATA"]
        self.STEPS_TO_POPULATE_TRAINING_STATES = self.learner_options["STEPS_TO_POPULATE_TRAINING_STATES"]
        self.MAX_NUMBER_OF_ACTIONS_SPACE       = self.learner_options["MAX_NUMBER_OF_ACTIONS_SPACE"]
        self.CREATE_PER_TARGET_STATES          = self.learner_options["CREATE_PER_TARGET_STATES"]
        self.SKIP_NON_REWARDING_STEPS          = self.learner_options["SKIP_NON_REWARDING_STEPS"]
        self.NORMALIZE_REWARDS                 = self.learner_options["NORMALIZE_REWARDS"]

        self.EPSILON_START       = self.learner_options["EPSILON_START"]
        self.EPSILON_FINAL       = self.learner_options["EPSILON_FINAL"]
        self.EPSILON_TOTAL_STEPS = self.learner_options["EPSILON_TOTAL_STEPS"]
        self.EPSILON_DECREASE_BY = 1 / (self.EPSILON_TOTAL_STEPS + self.EPSILON_TOTAL_STEPS / 10)

        # DQN OPTIONS
        self.AMOUNT_OF_SIMULATED_TRAINING_STEPS = self.learner_options["AMOUNT_OF_SIMULATED_TRAINING_STEPS"]

        # REWARD OPTIONS
        self.CALCULATE_REWARD                   = self.learner_options["CALCULATE_REWARD"]
        self.ADD_REWARD_PENALTY_FOR_ERRORS      = self.learner_options["ADD_REWARD_PENALTY_FOR_ERRORS"]
        self.ADD_REWARD_PENALTY_FOR_TIME_TAKEN  = self.learner_options["ADD_REWARD_PENALTY_FOR_TIME_TAKEN"]
        self.ADD_REWARD_PENALTY_FOR_STEPS_TAKEN = self.learner_options["ADD_REWARD_PENALTY_FOR_STEPS_TAKEN"]
        self.ADD_REWARD_FOR_NETWORK_INFORMATION = self.learner_options["ADD_REWARD_FOR_NETWORK_INFORMATION"]
        self.ONLY_REWARD_ENDING                 = self.learner_options["ONLY_REWARD_ENDING"]

        Log.logger.debug("LOADED THE CONFIGURATION => %s" % Utils.dump_json(self.learner_options))

    def init_pytorch(self, force_cpu):
        device_name = "cpu"
        if torch_cuda_is_available() and not force_cpu:
            device_name = "cuda"
        else:
            Log.logger.warning("CUDA not available so going with CPU!!!")

        self.device = torch_device(device_name)
        Log.logger.debug("Setting device to %s!!!" % device_name)

    def init_experience_buffer(self):
        raise NotImplementedError("You need to implement init_experience_buffer!")

    def load_actions_to_use(self):
        if self.load_main_training:
            training_game_id_to_load_actions, _ = self.load_main_training_id_and_nn_path()
            # LOAD ACTIONS TO USE
            Log.logger.debug(f"Got main training_game_id {training_game_id_to_load_actions}")
            self.actions_to_use = lib.Common.Training.Learner.load_actions_to_use(self.prod_connection, training_game_id_to_load_actions)
            Log.logger.debug("Loaded %d actions from DB" % len(self.actions_to_use))
        else:
            # self.training_game_id = self.create_training_game()
            actions_to_use = lib.Common.Training.Learner.load_actions_to_use(self.staging_connection,
                                                                             self.training_game_id)
            # Log.logger.debug(['actions_to_use_loaded', actions_to_use])
            if actions_to_use is not None:
                self.actions_to_use = actions_to_use
                Log.logger.debug("Loaded %d actions from DB" % len(self.actions_to_use))
            else:
                self.actions_to_use = CommonDQN.get_random_actions(self.game_type, self.SEED,
                                                                         self.MAX_NUMBER_OF_ACTIONS_SPACE)
                # Log.logger.debug(['actions_to_use_generated', self.actions_to_use])
                Log.logger.debug("Created %d actions and uploaded it to DB" % len(self.actions_to_use))

    def init_load_main_training(self):
        if self.load_main_training:
            self.load_main_training_nn()
        else:
            self.setup_network()

        Log.logger.debug("Training network is:")
        Log.logger.debug(self.training_network)

    def setup_optimizer(self):
        self.optimizer = optim.Adam(self.training_network.parameters(), lr=self.LEARNING_RATE)

    def setup_network(self):
        raise NotImplementedError("This needs to be implemented by child classes!")
        # self.training_network = DQN.DQN(self.observation_shape_size, number_of_actions_space).to(self.device)
        # self.target_network = DQN.DQN(self.observation_shape_size, number_of_actions_space).to(self.device)

    #########################################
    ################ </INITS> ###############
    #########################################

    #########################################
    ######### <GETTER AND SETTERS> ##########
    #########################################

    def get_training_game_id(self):
        return self.training_game_id

    def get_benchmark_counter(self):
        return self.benchmark_counter

    def get_benchmark_last_transition_id(self):
        return self.benchmark_last_transition['transition_id']

    def set_skip_until_reaching(self, skip_until_reaching):
        self.skip_until_reaching = skip_until_reaching

    def set_stop_training_after(self, stop_training_after):
        self.stop_training_after = stop_training_after

    def set_training_starts_at_rewarding_games(self):
        self.training_starts_at_rewarding_games = True

    def set_training_target(self, target):
        self.train_only_on_target = target

    def set_pause_benchmark_at(self, pause_benchmark_at):
        self.pause_benchmark_at = pause_benchmark_at

    def set_training_limit(self, training_limit):
        self.training_limit = training_limit

    def set_steps_to_populate_training_states(self, steps):
        self.STEPS_TO_POPULATE_TRAINING_STATES = steps

    def set_steps_per_nn_save(self, steps):
        self.STEPS_PER_NN_SAVE = steps

    #########################################
    ######### </GETTER AND SETTERS> #########
    #########################################

    #########################################
    ########### <DATABASE CALLS> ############
    #########################################

    def mark_current_game_as_ready(self):
        stmt = "UPDATE training_game SET ready=1 WHERE training_game_id=%s"
        data = (self.training_game_id,)
        self.staging_connection.execute(stmt, data)

    def load_main_training_id_and_nn_path(self):
        main_training_ids = get_main_training_ids(self.prod_connection)

        main_training_game_id = main_training_ids[self.game_type]['training_game_id']

        query = """
            SELECT neural_network_path FROM training t 
            JOIN training_game tg ON t.training_id=tg.training_id 
            WHERE tg.main_training=1 AND tg.training_game_id=%s
        """

        results = self.prod_connection.query(query, (main_training_game_id,))
        if len(results) > 0:
            main_training_nn_path = results[0]['neural_network_path']
        else:
            raise ValueError("I did not find any main training to load!!")

        return main_training_game_id, main_training_nn_path

    def load_main_training_nn(self):
        _, main_training_nn_path = self.load_main_training_id_and_nn_path()

        self.load_nns(main_training_nn_path, local_target=False) # load target as copy of training network

        return True

    def get_current_game_training(self):
        """
            This does not check for ready=1 since we want them to continue no matter what
        :return:
        """
        stmt = "SELECT training_game_id, neural_network_path, latest_transition_id FROM training_game WHERE training_id = \"%s\" AND game_type = \"%s\" AND latest_transition_id is not NULL" % (
            self.training_id, self.game_type)
        results = self.staging_connection.query(stmt)

        if len(results) > 0:
            Log.logger.debug([results[0]['training_game_id'], results[0]['neural_network_path'], results[0]['latest_transition_id']])
            return results[0]
        else:
            return None

    def create_training_game(self):
        stmt = "INSERT INTO training_game(training_id, benchmark_id, game_type, actions_to_use, learner_options, learner_options_benchmarked, network) VALUES (%s,%s,%s,%s,%s,%s,%s)"
        data = (self.training_id, self.benchmark_id, self.game_type, Utils.dump_json(self.actions_to_use), Utils.dump_json(self.benchmark_config_map), Utils.dump_json(self.params_to_override), str(self.training_network))
        training_game_id = self.staging_connection.execute(stmt, data)

        return training_game_id

    def get_list_of_episodes(self): # This relies on > REWARD_FOR_REGULAR_USER_AMOUNT for accum reward to speed up the query
        query = f"SELECT target, MIN(episode_id) as episode_id FROM step WHERE accumulated_reward > {Constants.REWARD_FOR_REGULAR_USER_AMOUNT} AND (reward_reasons LIKE '%{Constants.REWARD_FOR_SUPER_USER_SESSION_KEY}%' OR reward_reasons LIKE '%{Constants.REWARD_FOR_REGULAR_USER_SESSION_KEY}%') GROUP BY target"

        results     = self.prod_connection.query(query)
        Log.logger.debug(results)
        episode_to_reward_map = {}
        for result in results:
            episode_to_reward_map[result['target']] = int(result['episode_id'])

        return episode_to_reward_map

    def create_initial_select_of_step_columns(self):
        query = " SELECT step.transition_id, step.game_step, step.transactions_since_step_started, step.time_spent, step.error,  step.action_name, step.accumulated_reward, step.prev_state"
        query += " ,step.prev_game_type, step.next_game_type, step.prev_state_hash, step.next_state, step.next_state_hash, step.episode_finished"
        query += ", step.reward_reasons, step.episode_id as episode_id, game.name as game_type, episode.target FROM step"
        query += " JOIN game on step.game_id=game.game_id"
        query += " JOIN episode on step.episode_id=episode.episode_id"
        query += " WHERE episode.trainable=1"

        return query

    # TODO: Review why we need to do this every time we get a batch?
    def get_initial_state_hashes_up_to_now(self, good_game, target=None, training_id = None):
        initial_state_hashes = {}
        if self.game_type == "NETWORK":
            pass #This is not needed, only first state is initial and its added on logging step
        elif self.game_type == "PRIVESC":
            query = """
                SELECT distinct prev_state_hash FROM step
                JOIN episode on step.episode_id=episode.episode_id
                WHERE episode.trainable=1 AND prev_game_type = "NETWORK" and next_game_type = "PRIVESC"
            """
            if training_id is not None:
                query += " AND step.training_id=%d" % training_id

            if target is not None:
                query += " AND step.target=\"%s\"" % target

            if good_game:
                connection = self.prod_connection
            else:
                connection = self.staging_connection

            results = connection.query(query)
            for result in results:
                initial_state_hashes[result['prev_state_hash']] = 1
        else:
            raise ValueError(f"I don't know how to get initial state hashes for game_type {self.game_type}")

        return initial_state_hashes

    def get_batch_of_good_episodes_for_game_training_data(self, target = None):
        query = self.create_initial_select_of_step_columns()
        query += " AND game.name = \"%s\"" % self.game_type

        # Set target if provided
        if target is not None:
            query += " AND step.target = \"%s\"" % target

        query += " ORDER BY transition_id ASC"

        if self.training_limit is not None:
            query += f" LIMIT {self.training_limit}"

        Log.logger.debug(query)
        # raise ValueError("x")

        results     = self.prod_connection.query(query)
        transitions = self.get_transitions_from_results(results)
        Log.logger.info("Got %d transitions from good episodes!" % len(transitions))

        initial_state_hashes = self.get_initial_state_hashes_up_to_now(good_game=True, target=target)

        return transitions, initial_state_hashes

    def get_batch_of_current_training_for_game_training_data(self, query_type="higher"):
        # Log.logger.debug("Will request %d elements with query_type %s" % (amount, query_type))
        query = self.create_initial_select_of_step_columns()
        query += " AND episode.training_id = %d" % self.training_id
        query += " AND game.name = \"%s\"" % self.game_type

        if query_type == "higher":
            query += " AND transition_id > %d ORDER BY transition_id ASC" % self.latest_transition_id
        elif query_type == "lower":
            query += " AND transition_id < %d ORDER BY transition_id ASC" % self.latest_transition_id
        else:
            raise ValueError("Only higher or lower query types allowed")

        Log.logger.debug(query)
        results     = self.staging_connection.query(query)
        transitions = self.get_transitions_from_results(results)
        Log.logger.debug("Got %d transitions" % len(results))

        initial_state_hashes = self.get_initial_state_hashes_up_to_now(good_game=False, training_id=self.training_id)

        return transitions, initial_state_hashes

    #########################################
    ########### <DATABASE CALLS> ############
    #########################################

    #########################################
    ########### <DATA PREPARATION> ##########
    #########################################

    def get_transitions_from_results(self, results):
        transitions = []
        actions_to_use_name_to_idx = {k: v for v, k in enumerate(self.actions_to_use)}
        for res in results:
            try:
                data = {
                    "transition_id": res['transition_id'],
                    "reward":         res['accumulated_reward'],
                    "target":         res['target'],
                    'state_hash':     res['prev_state_hash'],
                    'new_state_hash': res['next_state_hash'],
                    'episode_id':     int(res['episode_id']),
                }

                # Parse reward reasons, this should be modified so its stored as a list of hashes instead of parsing the string
                reward_reasons_list = Utils.json_loads(res['reward_reasons'])
                reward_reasons = []
                for reason in reward_reasons_list:
                    reward_reasons.append(reason.split(":")[0])
                data['reward_reasons'] = reward_reasons

                try:
                    prev_state_dict = Utils.json_loads(res['prev_state'])
                except:
                    Log.logger.error(f"Error trying to load json for next_state => {res['prev_state_dict']} with error => {traceback.format_exc()}")
                data['state'] = State(prev_state_dict)

                try:
                    next_state_dict = Utils.json_loads(res['next_state'])
                except:
                    Log.logger.error(f"Error trying to load json for next_state => {res['next_state']} with error => {traceback.format_exc()}")
                data['new_state']                       = State(next_state_dict)

                data['action_name']                     = res['action_name']
                data['action_idx']                      = actions_to_use_name_to_idx[res['action_name']]
                data['game_step']                       = res['game_step']
                data['transactions_since_step_started'] = Utils.json_loads(res['transactions_since_step_started'])
                data['time_spent']      = res['time_spent']
                data['error']           = res['error']
                data['prev_state_json'] = res['prev_state']
                data['new_state_json']  = res['next_state']

                data['prev_game_type']  = res['prev_game_type']
                data['next_game_type']  = res['next_game_type']

                transitions.append(data)
            except:
                Log.logger.error("Error trying to append result to transitions => %s" % traceback.format_exc())

        return transitions

    def create_and_add_experience_to_buffer(self, transition):
        reward_for_experience = transition['reward']
        reward_reasons        = transition['reward_reasons']

        if self.CALCULATE_REWARD:
            # Log.logger.debug("Starting to calculate reward..")

            game_step = transition['game_step']
            transactions_since_step_started = transition['transactions_since_step_started']
            time_taken_for_observation = transition['time_spent']

            prev_state = transition['state']
            new_state  = transition['new_state']
            observed_error = transition['error']
            prev_game_type = transition['prev_game_type']
            next_game_type = transition['next_game_type']

            reward = Reward(game_step, transactions_since_step_started, time_taken_for_observation, prev_state, new_state, prev_game_type, next_game_type, observed_error)

            reward.rewarding_only_ending(self.ONLY_REWARD_ENDING)
            reward.normalize_rewards(self.NORMALIZE_REWARDS)
            reward.penalty_for_errors(self.ADD_REWARD_PENALTY_FOR_ERRORS)
            reward.penalty_for_time_taken(self.ADD_REWARD_PENALTY_FOR_TIME_TAKEN)
            reward.penalty_for_steps_taken(self.ADD_REWARD_PENALTY_FOR_STEPS_TAKEN)
            reward.reward_for_network_information(self.ADD_REWARD_FOR_NETWORK_INFORMATION)

            reward.calculate_reward()

            calculated_reward     = reward.get_accumulated_reward()
            reward_for_experience = calculated_reward

            # Log.logger.debug("Finished calculating reward")

            # if calculated_reward != transition['reward']:
            #     Log.logger.warn("For transition %d db_reward => %s calculated_reward => %s, reward_reasons_calculated => %s" % (transition['transition_id'], transition['reward'], calculated_reward, reward.get_reward_reasons_with_values()))

        goal_reached = False
        if Constants.REWARD_FOR_SUPER_USER_SESSION_KEY in reward_reasons or Constants.REWARD_FOR_REGULAR_USER_SESSION_KEY in reward_reasons:
            goal_reached = True

        new_experience = ExperienceBuffer.Experience(transition['prev_game_type'], transition['state'], transition['state_hash'], transition['action_idx'], transition['action_name'],
                                                     reward_for_experience,
                                                     transition['next_game_type'], transition['new_state'], transition['new_state_hash'], transition['target'], transition['prev_state_json'], transition['new_state_json'], goal_reached)
        self.experience_buffer.append(new_experience)
        # Log.logger.debug("Amount of elements in buffer now: %d" % len(self.experience_buffer))

        self.LoggerHelper.add_seen_state_hash(new_experience)
        # Log.logger.debug("Added experience to state hash")

        self.step_counter += 1

        self.target = new_experience.target # Lets set it based on the experience

        return new_experience

    #########################################
    ########### </DATA PREPARATION> #########
    #########################################

    #########################################
    ########### <NEURAL NETWORK> ############
    #########################################

    def upload_initial_nn(self):
        nn_filename_with_version = self.save_nn()
        self.sync_target_nn()

        stmt = "UPDATE training_game SET neural_network_path=%s, latest_transition_id=%s WHERE training_game_id=%s"
        data = (nn_filename_with_version, self.latest_transition_id, self.training_game_id)
        self.staging_connection.execute(stmt, data)

    def save_nn(self):
        Log.logger.debug("Saving training network..")
        nn_filename_with_version = self.nn_filename + ".%d" % self.latest_transition_id
        torch_save(self.training_network, nn_filename_with_version)
        Log.logger.debug("Saved the training network to %s" % nn_filename_with_version)
        self.stored_nn_versions.append(nn_filename_with_version)

        # TEC-444: Review, we only keep 1 version to avoid reading a file which is being written by simulateneus reloads
        # TEC-444: Remove this when reloads are triggered per game type
        amount_of_versions = 3
        if len(self.stored_nn_versions) >= amount_of_versions:
            filename_to_delete = self.stored_nn_versions[-amount_of_versions]
            Log.logger.debug("Attempting to remove file %s" % filename_to_delete)
            if os.path.exists(filename_to_delete):
                os.remove(filename_to_delete)
            Log.logger.debug("Removed file %s" % filename_to_delete)

        return nn_filename_with_version

    def build_target_filename(self):
        return "%s/%s_%s.pt.target" % (self.folder_path, self.learner_name, self.game_type)

    def load_nns(self, nn_filename, local_target=True):
        Log.logger.debug("Loading training network %s..." % nn_filename)
        self.training_network = torch_load(nn_filename)
        Log.logger.debug("Finished loading training network...")

        if local_target:
            nn_filename_target = self.build_target_filename()
            Log.logger.debug("Loading target network %s..." % nn_filename_target)
            self.target_network = torch_load(nn_filename_target)
        else:
            Log.logger.debug("Using the same training network as our initial target network")
            self.target_network = torch_load(nn_filename)
        Log.logger.debug("Finished loading target network...")

    def sync_target_nn(self):
        if self.latest_transition_id % self.SYNC_TARGET_STEPS == 0:
            Log.logger.debug("Saving target network..")
            nn_filename_target = self.build_target_filename()
            torch_save(self.training_network, nn_filename_target)
            Log.logger.debug("Saved the target network to %s" % nn_filename_target)

    def update_game_training(self):
        # FIRST WE SAVE THE NEW VERSION OF THE NETWORK
        nn_filename_with_version = self.save_nn()
        self.sync_target_nn()

        # NOW WE STORE IT IN THE DATABASE
        Log.logger.debug(f"Updating NN for training_game_id {self.training_game_id}")

        stmt = "UPDATE training_game SET neural_network_path=%s, latest_transition_id=%s WHERE training_game_id=%s"
        data = (nn_filename_with_version, self.latest_transition_id, self.training_game_id)
        self.staging_connection.execute(stmt, data)
        Log.logger.debug([stmt, data])

    #########################################
    ########### </NEURAL NETWORK> ###########
    #########################################

    #########################################
    ############### <UTILS> #################
    #########################################

    #########################################
    ################ </UTILS> ###############
    #########################################

    #########################################
    ############## <TRAINING> ###############
    #########################################

    def pre_training_hook(self):
        pass

    def train_on_transition(self, transition, train_transition = True):
        """

        :param transition:
        """

        start_time = time.time()

        self.latest_transition_id = transition['transition_id']
        new_experience = self.create_and_add_experience_to_buffer(transition)

        if self.latest_transition_id > self.last_transition_id_used_for_state_upload + self.STEPS_TO_POPULATE_TRAINING_STATES:
            self.LoggerHelper.log_training_states(transition['transition_id'])
            self.last_transition_id_used_for_state_upload = self.latest_transition_id

        if train_transition:
            self.pre_training_hook()

            Log.logger.info(f"Tid:{self.latest_transition_id} Step:{self.step_counter} BufferSize:{len(self.experience_buffer)} {new_experience}")

            target  = transition['target']
            trained = self.train_network(new_experience)

            if trained and self.step_counter % self.STEPS_PER_NN_SAVE == 0:
                self.update_game_training()

            self.pos_training_hook()

            Log.logger.debug(f"Finished processing transition_id {self.latest_transition_id} for {target} after {time.time() - start_time} seconds")
            Log.logger.debug("=" * 60)
        else:
            if self.latest_transition_id % 100 == 0:
                Log.logger.debug(f"(1/100) Finished processing transition {self.latest_transition_id}")

    def pos_training_hook(self):
        pass

    def train_network(self, new_experience):
        """
            Important this must implement a step.train_counter += 1 on every training iteration
        """
        raise NotImplementedError("You need to implement train_network!")

    #########################################
    ############## </TRAINING> ##############
    #########################################

    # 1) Check if we have any existing training to continue for the training id provided
    # 2) If there is a ongoing training
    #   2.1) Get ongoing training
    #   2.2) Load the neural network
    #   2.3) Now get all the previous transitions up to which it was trained and add them to the buffer
    # 3) If there is no ongoing training
    #   3.1) If we have the "good games" flag, then train on them and load all of them to the buffer
    #   3.2) Create a new training entry with a new NN
    #
    # 4) Will now set the game as ready!
    # 5) Enter loop of getting any transition after the last one we processed and training the network updating the latest transition_id used

    def learn(self):
        Log.add_info_medium_ascii("Preparation")

        Log.logger.debug("Now getting training for current game if available by the supplied training_id..")

        Log.logger.debug("1) Check if we have any existing training to continue for the training id provided")
        existing_game_training_ongoing = self.get_current_game_training()

        if existing_game_training_ongoing:  # 2) If there is a ongoing training
            Log.logger.debug("2.1) Get ongoing training")
            Log.logger.debug("Found an existing training for the game %s" % self.game_type)

            # SETTING VARS
            self.training_game_id              = existing_game_training_ongoing['training_game_id']
            self.LoggerHelper.training_game_id = self.training_game_id

            if self.continue_from_latest_point:
                self.latest_transition_id = existing_game_training_ongoing['latest_transition_id']
            else:
                Log.logger.warning("Not using latest transition id since we dont have the continue_from_latest_point flag on")

            if self.train_on_transitions:
                Log.logger.debug("2.2) Load the neural network")
                Log.logger.debug(
                    "Existing game training going on, will continue from training_game_id %s" % self.training_game_id)
                self.load_nns(existing_game_training_ongoing['neural_network_path'])
                self.optimizer = optim.Adam(self.training_network.parameters(), lr=self.LEARNING_RATE)
            else:
                nn_filename_with_version = self.save_nn()
                self.sync_target_nn()

            Log.logger.debug(
                "2.3) Now get all the previous transitions up to which it was trained and add them to the buffer")
            transitions_for_buffer, self.initial_state_hashes = self.get_batch_of_current_training_for_game_training_data("lower")

            for transition in transitions_for_buffer:
                self.create_and_add_experience_to_buffer(transition)
        else:
            Log.logger.debug("3) Since there is NO ongoing training")

            Log.logger.info("We need to create the game training!")
            self.training_game_id              = self.create_training_game()
            self.LoggerHelper.training_game_id = self.training_game_id

            Log.logger.debug("3.2) Create a new training entry with a new NN")
            Log.logger.info("Will start uploading the initial training network for game %s.." % self.game_type)
            self.upload_initial_nn()

        Log.logger.info("Finished setting up training for id %d" % self.training_game_id)

        Log.logger.debug("4) Will now set the game as ready!")
        self.mark_current_game_as_ready()
        
        Log.logger.debug("Amount of elements in buffer now: %d" % len(self.experience_buffer))

        Log.logger.info("=" * 60)
        Log.logger.info(f"Starting learner with training_game_id {self.training_game_id} and after transition {self.latest_transition_id}")

        Log.add_info_medium_ascii("Looping")

        if self.train_on_transitions:
            Log.logger.debug(
                "5) Enter loop of getting any transition after the last one we processed and updating training states with the latest transition_id used")
        else:
            Log.logger.debug(
                "5) Enter loop of getting any transition after the last one we processed and training the network updating the latest transition_id used")

        while True:
            # change_happened = False
            # Log.logger.debug("Getting new training entries since latest_transition_id id:%d processed" % latest_transition_id)
            transitions, self.initial_state_hashes = self.get_batch_of_current_training_for_game_training_data()
            for transition in transitions:
                self.train_on_transition(transition, self.train_on_transitions)

            if self.profile == "TRAIN":
                Log.logger.info("Finishing training after getting batch of existing training")
                break
            else:
                time.sleep(5)
                # Will continue loop

        return True

    #########################################
    ############## <BENCHMARK> ##############
    #########################################

    def benchmark(self):
        Log.add_info_medium_ascii("Preparation")

        if not self.benchmark_ongoing:
            Log.logger.info("0) We need to create the game training!")
            self.training_game_id              = self.create_training_game()
            self.LoggerHelper.training_game_id = self.training_game_id

            Log.logger.info(f"1) With training_game_id {self.training_game_id} loading transitions from good games to train with limit of {self.training_limit}")

            if self.train_only_on_target is not None:
                self.benchmark_transitions_from_good_episodes, self.initial_state_hashes = self.get_batch_of_good_episodes_for_game_training_data(self.train_only_on_target)
            else:
                self.benchmark_transitions_from_good_episodes, self.initial_state_hashes = self.get_batch_of_good_episodes_for_game_training_data()

            # Getting a list of episodes so we can skip training initial explorations
            if self.training_starts_at_rewarding_games:
                Log.logger.info("1.1) There is a flag to start from rewarding episodes, will fetch them")
                self.map_of_target_to_episode_id = self.get_list_of_episodes()

            self.upload_initial_nn()

        self.benchmark_ongoing         = True
        finished                       = True # If we don't mark it as False it means we did not pause

        Log.logger.info(f"2) Will train {len(self.benchmark_transitions_from_good_episodes)} transitions from good games starting at:{self.benchmark_counter}")
        for i in range(self.benchmark_counter, len(self.benchmark_transitions_from_good_episodes)):
            self.benchmark_counter += 1

            if self.pause_benchmark_at is not None and self.benchmark_counter % self.pause_benchmark_at == 0:
                Log.logger.info(f"Pausing benchmark at iteration {self.benchmark_counter} with pause setting of {self.pause_benchmark_at}")
                finished = False
                break

            transition = self.benchmark_transitions_from_good_episodes[i]
            self.benchmark_last_transition = transition

            if self.skip_until_reaching is not None and self.benchmark_counter < self.skip_until_reaching:
                continue

            if self.we_should_skip_this_non_rewarding_episode(transition):
                continue

            if self.we_should_skip_this_non_important_step(transition):
                continue

            ######################### ACTUAL TRAINING ########################
            self.train_on_transition(transition)
            ######################### ACTUAL TRAINING ########################

            if self.stop_training_after is not None and self.benchmark_counter > self.stop_training_after:
                Log.logger.warning(f"Stopped training after reaching {self.stop_training_after} transitions!")
                break

        Log.logger.info("3) Finished training NN, will now upload training states!")
        self.LoggerHelper.log_training_states(self.benchmark_last_transition['transition_id'])
        return finished, self.benchmark_last_transition['target']

    def we_should_skip_this_non_important_step(self, transition):
        if self.SKIP_NON_REWARDING_STEPS > 0:
            reward = int(transition['reward'])
            if reward == 0:
                prev_state_hash = transition['state_hash']
                action_name     = transition['action_name']
                target          = transition['target']
                tuple = (target, prev_state_hash, action_name)
                if tuple not in self.map_target_to_non_reward_steps:
                    self.map_target_to_non_reward_steps[tuple] = 1
                else:
                    self.map_target_to_non_reward_steps[tuple] += 1
                    if self.map_target_to_non_reward_steps[tuple] % self.SKIP_NON_REWARDING_STEPS + 1 != 0:
                        Log.logger.warning(
                            f"Skipping non-rewarding {tuple} since counter is {self.map_target_to_non_reward_steps[tuple]}/{self.SKIP_NON_REWARDING_STEPS}")
                        return True
                    # Now this means we already covered such a non rewarding action

        return False

    def we_should_skip_this_non_rewarding_episode(self, transition):
        target = transition['target']
        if self.training_starts_at_rewarding_games and target in self.map_of_target_to_episode_id:
            if transition['episode_id'] - 10 < self.map_of_target_to_episode_id[target]:  # Lets allow the first 10 episodes to be empty
                # Log.logger.debug(f"Skipping transition_id:{transition['transition_id']} episode_id:{transition['episode_id']}")
                return True  # We will skip this episode since there is no rewarding data to be used

        return False

    #########################################
    ############## </BENCHMARK> #############
    #########################################