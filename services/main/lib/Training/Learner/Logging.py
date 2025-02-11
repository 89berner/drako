import operator

from collections import OrderedDict
import lib.Common.Utils as Utils
import lib.Common.Utils.Log as Log

import lib.Common.Training.DQN               as DQN
from   lib.Common.Utils import Constants

class LoggerHelper:
    def __init__(self, training_id, experience_buffer, game_type, actions_to_use, training_network, device, staging_connection, prod_connection, initial_state_hashes, CREATE_PER_TARGET_STATES, profile):
        self.training_id          = training_id
        self.experience_buffer    = experience_buffer
        self.game_type            = game_type
        self.actions_to_use       = actions_to_use
        self.training_network     = training_network
        self.device               = device
        self.staging_connection   = staging_connection
        self.prod_connection      = prod_connection
        self.initial_state_hashes = initial_state_hashes
        self.profile              = profile

        self.seen_states = {
            "global": {},
            "targets": {},
        }

        # Getting a list of exploitation paths so we can measure our progress
        self.map_of_actions_to_tuples_to_log = self.load_actions_to_log()

        self.CREATE_PER_TARGET_STATES = CREATE_PER_TARGET_STATES

        # CACHES
        self.training_state_hash_to_obs_cache = {}

        self.training_game_id = None

    def print_network_top_20(self, state_hash, observation):
        _, top_limited_qvalues_sorted = self.get_top_limited_qvalues_sorted(observation)

        Log.logger.debug(f"Top qvalues for state {state_hash} => {top_limited_qvalues_sorted}")

    def get_top_limited_qvalues_sorted(self, observation):
        new_q_vals_values      = DQN.get_q_vals_values_from_network(observation, self.training_network, self.device)
        new_q_vals_values_dict = DQN.create_q_vals_values_dict(new_q_vals_values, self.actions_to_use)

        top_limited_qvalues        = OrderedDict(sorted(new_q_vals_values_dict.items(), key=operator.itemgetter(1), reverse=True)[:20])
        top_limited_qvalues_sorted = Utils.dump_json_sorted_by_values(top_limited_qvalues)

        return new_q_vals_values_dict, top_limited_qvalues_sorted

    def log_train_network_results(self, batch, state_action_values, ADDITIONAL_LOGGING, target, new_experience=None):
        # Caching state_hash => obs_array to improve speed
        if new_experience is not None: #TODO: This might be better suited somewhere else
            prev_state_hash = new_experience.prev_state_hash
            if prev_state_hash not in self.training_state_hash_to_obs_cache:
                observation    = new_experience.prev_state.get_transform_state_to_observation(self.game_type)
                self.training_state_hash_to_obs_cache[prev_state_hash] = observation
                Log.logger.debug(f"I had to store in cache the observation for state_hash: {prev_state_hash}")

        states, prev_state_hashes, new_state_hashes, actions, rewards, _, next_states, _, _ = batch
        #### NOW STORE TRAINING DATA
        # LOG TO DATABASE TRAINING DATA IF WE PERFORMED ANY TRAINING

        # TODO: MOVE MOST OF THIS CHECKS INTO A MODULE
        # ADDITIONAL LOGIC TO CHECK IF ANY OF THE TRAINED ON ACTIONS IS CONSIDERED IMPORTANT
        ADDITIONAL_LOGGING = self.check_batch_for_additional_logging(target, batch, ADDITIONAL_LOGGING)

        if ADDITIONAL_LOGGING:
            # TODO: UNIFY WITH DB BELOW IN A METHOD
            for idx, action_idx in enumerate(actions):

                action_name      = self.actions_to_use[action_idx]
                prev_state_hash  = prev_state_hashes[idx]
                new_state_hash   = new_state_hashes[idx]
                prev_action_qval = state_action_values[idx]  # prev_q_vals_values_dict[action_name]

                new_q_vals_values_dict, top_limited_qvalues_sorted = self.get_top_limited_qvalues_sorted(states[idx])
                new_action_qval = new_q_vals_values_dict[action_name]

                Log.logger.debug(f"({prev_state_hash},{action_name}-X) => ({new_state_hash},{rewards[idx]}) went from {prev_action_qval} to {new_action_qval}")
                Log.logger.debug(f"Top qvalues for state {prev_state_hash} => {top_limited_qvalues_sorted}")

    def check_batch_for_additional_logging(self, target, batch, ADDITIONAL_LOGGING):
        _, prev_state_hashes, _, actions, _, _, _, _, _ = batch
        for idx, action_idx in enumerate(actions):
            action_name = self.actions_to_use[action_idx]
            state_hash  = prev_state_hashes[idx]
            tuple = (state_hash, action_name)
            # Log.logger.debug(f"Checking if we should log for tuple {tuple}")
            if target in self.map_of_actions_to_tuples_to_log and tuple in self.map_of_actions_to_tuples_to_log[target]:
                return True

        return ADDITIONAL_LOGGING

    def add_seen_state_hash(self, new_experience):
        self.add_state_information_to_map(self.seen_states["global"], new_experience)

        target = new_experience.target
        if target not in self.seen_states['targets']:
            self.seen_states['targets'][target] = {}
        self.add_state_information_to_map(self.seen_states['targets'][target], new_experience)

    def check_if_it_is_an_initial_state_hash(self, state_hash):
        # Log.logger.debug([state_hash, self.initial_state_hashes])
        if state_hash in self.initial_state_hashes:
            return True
        else:
            return False

    def add_state_information_to_map(self, seen_states_map, new_experience):
        prev_state_hash = new_experience.prev_state_hash
        # prev_game_type  = new_experience.prev_game_type
        next_state_hash = new_experience.new_state_hash
        # next_game_type  = new_experience.new_game_type

        if prev_state_hash != next_state_hash:
            action_name        = new_experience.action_name
            next_state         = new_experience.new_state
            next_state_in_json = next_state.get_json()

            # PROCESS FOR GLOBAL
            if prev_state_hash not in seen_states_map:
                prev_observation = new_experience.prev_state.get_transform_state_to_observation(self.game_type)
                seen_states_map[prev_state_hash] = {
                    "state_json":  new_experience.prev_state.get_json(),
                    "observation": prev_observation,
                    "next_states":     {},
                    "prev_states":     {},
                    "initial_state": True,
                }

            # prev state is present, so we just try to add the next state if its missing
            next_states_map = seen_states_map[prev_state_hash]["next_states"]
            if next_state_hash not in next_states_map:
                next_states_map[next_state_hash] = {
                    action_name: {"amount": 1},
                    "total": 1,
                }

                if next_state_hash not in seen_states_map:
                    # NOW CREATE THE NEXT STATE MAP SINCE THIS IS THE FIRST TIME WE HAVE SEEN THIS NEXT STATE
                    next_observation = new_experience.new_state.get_transform_state_to_observation(self.game_type)
                    seen_states_map[next_state_hash] = {
                        "state_json":    next_state_in_json,
                        "observation":   next_observation,
                        "next_states":   {},
                        "prev_states":   {},
                        "initial_state": self.check_if_it_is_an_initial_state_hash(next_state_hash),
                    }
            else: # WE HAVE ALREADY SEEN THIS NEXT STATE HASH
                if action_name not in next_states_map[next_state_hash]:
                    next_states_map[next_state_hash][action_name] = {"amount": 1}
                else:
                    next_states_map[next_state_hash][action_name]['amount'] += 1
                next_states_map[next_state_hash]["total"] += 1

            if new_experience.goal_reached is True:
                next_states_map[next_state_hash][action_name]['goal_reached'] = 1

            # NOW POPULATE PREV STATES OF NEXT HASH
            prev_states_of_next_state = seen_states_map[next_state_hash]['prev_states']
            if prev_state_hash not in prev_states_of_next_state:
                prev_states_of_next_state[prev_state_hash] = {
                    "total": 0
                }
            prev_states_of_next_state[prev_state_hash]['total'] += 1

            if action_name not in prev_states_of_next_state[prev_state_hash]:
                prev_states_of_next_state[prev_state_hash][action_name] = {
                    "amount": 0
                }
            # Log.logger.debug(prev_states_of_next_state[prev_state_hash][action_name])
            prev_states_of_next_state[prev_state_hash][action_name]["amount"] += 1

            # Log.logger.debug([prev_game_type, next_game_type])
            # if prev_game_type != next_game_type:
            #     prev_states_of_next_state[prev_state_hash]['prev_game_type'] = prev_game_type


    def build_state_q_vals_and_important_pos(self, state_hash, observation, amount_for_qvals):
        prev_q_vals_values                   = DQN.get_q_vals_values_from_network(observation, self.training_network, self.device)
        prev_q_vals_values_dict              = DQN.create_q_vals_values_dict(prev_q_vals_values, self.actions_to_use)
        prev_q_vals_values_dict_sorted       = dict(sorted(prev_q_vals_values_dict.items(), key=operator.itemgetter(1), reverse=True))
        prev_q_vals_values_dict_sorted_tuple = tuple(prev_q_vals_values_dict_sorted.keys())

        top_q_vals, top_limited_qvalues, _ = DQN.log_q_vals_and_get_top_actions(self.actions_to_use, prev_q_vals_values, amount_of_actions=amount_for_qvals)

        new_q_vals = {}
        for action_name in top_limited_qvalues:
            new_q_vals[action_name] = {
                "val":             top_limited_qvalues[action_name],
                "amount_of_times": self.experience_buffer.get_trained_action(state_hash, action_name),
            }

        return new_q_vals

    def log_training_states(self, transition_id, amount_for_qvals=20):
        """
            Logs each known state up to now for the game type and the predictions for the current network
        :return:
        """
        if self.training_game_id is None:
            raise ValueError("You can't log training states since training_game_id is NONE")

        insert_stmt = """
            INSERT INTO training_states(training_id, transition_id, game_type, training_game_id, state_hash, state, top_dqn, prev_states, next_states, target, initial_state) 
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """
        all_data = []

        state_hash_to_new_q_vals_cache = {}
        Log.logger.debug("Start process of logging training states")
        for state_hash in self.seen_states['global']:
            # Log.logger.debug(state_hash)
            state_hash_data = self.seen_states['global'][state_hash]

            state_json    = state_hash_data["state_json"]
            prev_states   = state_hash_data["prev_states"]
            next_states   = state_hash_data["next_states"]
            observation   = state_hash_data["observation"]
            initial_state = state_hash_data["initial_state"]

            if self.profile != "EXPLORE":
                new_q_vals = self.build_state_q_vals_and_important_pos(state_hash, observation, amount_for_qvals=amount_for_qvals)
            else:
                new_q_vals = {}

            state_hash_to_new_q_vals_cache[state_hash] = (new_q_vals, state_json)

            data = (self.training_id, transition_id, self.game_type, self.training_game_id, state_hash, state_json,
                    Utils.dump_json_sorted_by_values(new_q_vals),
                    Utils.dump_json(prev_states), Utils.dump_json(next_states), Constants.GLOBAL_TARGET, initial_state)
            all_data.append(data)
            # self.staging_connection.execute(stmt, data)
            # Log.logger.debug("Prepared training data for state hash %s" % state_hash)

        self.staging_connection.execute_many(insert_stmt, all_data)
        Log.logger.debug(f"Inserted {len(all_data)} training states")

        # We need per target state for graphs and converging calculations
        if self.CREATE_PER_TARGET_STATES:
            for target in self.seen_states['targets']:
                all_data = []
                for state_hash in self.seen_states['targets'][target]:
                    state_hash_data = self.seen_states['targets'][target][state_hash]

                    state_json    = state_hash_data["state_json"]
                    next_states   = state_hash_data["next_states"]
                    prev_states   = state_hash_data["prev_states"]
                    initial_state = state_hash_data["initial_state"]

                    data = (self.training_id, transition_id, self.game_type, self.training_game_id, state_hash, state_json,
                            Utils.dump_json_sorted_by_values(new_q_vals),
                            Utils.dump_json(prev_states), Utils.dump_json(next_states), target, initial_state)
                    # self.staging_connection.execute(stmt, data)
                    # Log.logger.debug("Prepared training data for target %s state hash %s" % (target, state_hash))
                    all_data.append(data)

                self.staging_connection.execute_many(insert_stmt, all_data)
                Log.logger.debug(f"Inserted {len(all_data)} training states")

    def load_actions_to_log(self):
        query = "SELECT target, state_hash, action_name FROM target_logging WHERE game_type = %s"

        data = (self.game_type,)
        Log.logger.debug(query)
        Log.logger.debug(data)
        results = self.prod_connection.query(query, data)
        # Log.logger.debug(results)
        map_of_actions_to_tuples_to_log = {}
        for result in results:
            target = result['target']
            if target not in map_of_actions_to_tuples_to_log:
                map_of_actions_to_tuples_to_log[target] = {}

            step_tuple = (result['state_hash'], result['action_name'])
            map_of_actions_to_tuples_to_log[target][step_tuple] = 1

        Log.logger.debug(map_of_actions_to_tuples_to_log)

        return map_of_actions_to_tuples_to_log