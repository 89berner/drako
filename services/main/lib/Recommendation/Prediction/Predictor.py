import torch
from lib.Recommendation import Graph as Graph

import random
import traceback
from dataclasses import dataclass, field
import lib.Common.Utils as Utils
import lib.Common.Utils.Constants as Constants

from lib.Common.Utils import Log as Log
from lib.Common.Training import Learner as Learner
from lib.Recommendation.Prediction import OptionsRecommender
from lib.Common.Exploration.Environment.State import State

from abc import ABC, abstractmethod

import lib.Common.Training.DQN as DQN

PRIORITIZED_AUXILIARY_ACTIONS = [
    "auxiliary/scanner/smb/smb_enumusers",
    "auxiliary/scanner/http/iis_internal_ip",
    "auxiliary/scanner/http/canon_wireless",
    "auxiliary/scanner/dcerpc/tcp_dcerpc_auditor",
    "auxiliary/scanner/http/dir_scanner",
    "auxiliary/scanner/http/allegro_rompager_misfortune_cookie",
    "auxiliary/scanner/dcerpc/endpoint_mapper",
    "auxiliary/scanner/http/jboss_vulnscan",
    "auxiliary/gather/vbulletin_getindexablecontent_sqli",
    "auxiliary/scanner/netbios/nbname",
    "auxiliary/scanner/discovery/udp_sweep",
    "auxiliary/admin/http/allegro_rompager_auth_bypass",
    "auxiliary/scanner/discovery/udp_probe",
    "auxiliary/scanner/ftp/anonymous",
    "auxiliary/scanner/http/nginx_source_disclosure",
    "auxiliary/admin/http/typo3_news_module_sqli",
    "auxiliary/scanner/http/ntlm_info_enumeration",
    "auxiliary/scanner/ftp/ftp_version",
    "auxiliary/scanner/ssh/ssh_version",
    "auxiliary/scanner/finger/finger_users",
    "auxiliary/scanner/smb/pipe_dcerpc_auditor",
    "auxiliary/gather/xerox_pwd_extract",
    "auxiliary/scanner/smb/smb_enumshares",
    "auxiliary/scanner/http/crawler",
    "auxiliary/scanner/http/http_version",
    "auxiliary/scanner/smb/pipe_auditor",
    "auxiliary/scanner/misc/poisonivy_control_scanner",
    "auxiliary/scanner/portscan/syn",
    "auxiliary/scanner/portscan/tcp",
    "auxiliary/scanner/portscan/ack",
    "auxiliary/gather/windows_secrets_dump",
    "auxiliary/scanner/smb/smb_version",
    "db_nmap",
]

BLACKLISTED_ACTIONS = [
    "fileserver_and_metasploitlistener",
    "metasploitlistener",
    "delete_sessions",
    "auxiliary/spoof/nbns/nbns_response",
]

# WE WILL HAVE ONE OF THESE PER GAME_TYPE
class PredictorLoader:
    def __init__(self, connection, training_id, training_game_id, game_type, force_cpu, agent_options):
        self.DEBUG_MODE = False

        self.connection       = connection
        self.training_id      = training_id      #TODO: We should avoid needing this
        self.training_game_id = training_game_id
        self.game_type        = game_type

        self.states_counter_map      = self._load_states_counters_map()
        self.states_to_actions_map   = self._load_states_to_actions_map()
        self.interesting_actions_map = self._load_interesting_actions_map()
        self.no_goals_reached_yet    = self._check_if_no_goals_where_reached() # Checks if any reward reason matches a goal

        Log.logger.debug(f"Finished loading network maps for {self.game_type}")

        if torch.cuda.is_available() and not force_cpu:
            self.device_name = "cuda"
        else:
            self.device_name = "cpu"
        self.torch_device = torch.device(self.device_name)

        self.agent_options = agent_options

        self.training_network = self._load_latest_nn()
        Log.logger.debug(f"Finished loading NN for {self.game_type} using device_name: {self.device_name}")

        try:
            if self.game_type == Constants.GAME_TYPE_NETWORK:
                self.key_states_to_action_per_target = self._filter_states_for_those_that_lead_to_key_state('START', 'SESSION')
            elif self.game_type == Constants.GAME_TYPE_PRIVESC:
                self.key_states_to_action_per_target = self._filter_states_for_those_that_lead_to_key_state('SESSION', Constants.GRAPH_KEY_STATE_SUPER_SESSION)
            else:
                Log.logger.debug(f"No idea how to deal with game_type {self.game_type}")
                self.key_states_to_action_per_target = {}
        except:
            Log.logger.error(f"ERROR LOADING KEY STATES => {traceback.format_exc()}")
            self.key_states_to_action_per_target = {}

        Log.logger.debug(["key_states_to_action_per_target", self.key_states_to_action_per_target])

        self.actions_to_use      = Learner.load_actions_to_use(self.connection, self.training_game_id)
        self.options_recommender = OptionsRecommender(self.connection, self.training_game_id, self.game_type)

        self.prioritized_actions_map = self._load_prioritized_actions()
        # Log.logger.debug(self.prioritized_actions_map)

        Log.logger.debug(f"Finished init of PredictorLoader for game {self.game_type}")

    def _load_prioritized_actions(self):
        self.learner_options = Learner.load_learner_options(self.connection, Constants.DQN_FAMILY_NAME, Constants.COMMON_FAMILY_NAME, self.game_type, attributes=["PRIORITIZED_ACTIONS", "PRIORITIZED_ACTIONS_WEIGHT", ""])
        prioritized_actions        = self.learner_options["PRIORITIZED_ACTIONS"].split(",")
        prioritized_actions_weight = self.learner_options["PRIORITIZED_ACTIONS_WEIGHT"]
        Log.logger.debug([prioritized_actions, prioritized_actions_weight])

        prioritized_actions_map = {}
        for prioritized_action in prioritized_actions:
            if prioritized_action != "":
                prioritized_actions_map[prioritized_action] = prioritized_actions_weight

        return prioritized_actions_map

    def _get_training_data(self):
        # HERE WE SHOULD LOAD THE NN FROM THE DATABASE
        Log.logger.info(f"Getting the training data for training_game_id:{self.training_game_id}")

        query = "SELECT neural_network_path FROM training_game WHERE training_game_id=%s"
        # Log.logger.debug(query)
        results = self.connection.query(query, (self.training_game_id,))
        # Log.logger.debug(results)

        return results

    def _load_latest_nn(self):
        device = torch.device(self.device_name)

        results = self._get_training_data()

        if len(results) > 0:
            result              = results[0]
            neural_network_path = result['neural_network_path']

            Log.logger.debug("Loading training network %s..." % neural_network_path)
            Log.logger.debug("Finished loading training network...")

            network_loaded = torch.load(neural_network_path, map_location=torch.device(device))

            return network_loaded
        else:
            raise ValueError(f"I did not find any training_data for the training_game_id {self.training_game_id}")

    def _load_states_counters_map(self):
        counter_stmt = """
            SELECT target, prev_state_hash, count(*) as amount
            FROM step 
            FORCE INDEX (training_id_3)
            WHERE training_id=%s AND prev_game_type=%s
            GROUP BY target, prev_state_hash
            ORDER BY amount
        """
        data = (self.training_id, self.game_type)
        Log.logger.debug([counter_stmt, data])
        results = self.connection.query(counter_stmt, data)

        states_counter_map = {}
        for result in results:
            target      = result['target']
            state_hash  = result['prev_state_hash']
            amount      = result['amount']
            if target not in states_counter_map:
                states_counter_map[target] = {}

            if state_hash not in states_counter_map[target]:
                states_counter_map[target][state_hash] = {}

            states_counter_map[target][state_hash] = amount

        return states_counter_map

    def _load_states_to_actions_map(self):
        counter_stmt = """
            SELECT target, prev_state_hash, action_name, count(*) as amount
            FROM step 
            FORCE INDEX (training_id_3)
            WHERE training_id=%s AND prev_game_type=%s
            GROUP BY target, prev_state_hash, action_name
            ORDER BY amount
        """
        Log.logger.debug([counter_stmt, (self.training_id, self.game_type)])

        results = self.connection.query(counter_stmt, (self.training_id, self.game_type))
        # Log.logger.debug(results)
        states_to_actions_map = {}
        # states_to_actions_map => This should create a map where we have:
        # For each target
        #   For each state
        #       For each amount of times we could execute an action a list of actions already executed
        # For example {
        # "10.10.10.3": {
        #                   "AAAAA": {
        #                               1: ["action_1", "action_2"....]
        # Then we can check which is the lowest bucket of actions that does not have the same amount as the total of actions to use
        # and we can use that one to pick a random action
        for res in results:
            target      = res['target']
            state_hash  = res['prev_state_hash']
            action_name = res['action_name']
            amount      = res['amount']
            if target not in states_to_actions_map:
                states_to_actions_map[target] = {}

            if state_hash not in states_to_actions_map[target]:
                states_to_actions_map[target][state_hash] = {}

            # Now lets create a bucket from 1 to the amount, so if we get a 3 we add the action in 1, 2 and 3
            for counter in range(1, amount + 1):
                if counter not in states_to_actions_map[target][state_hash]:
                    states_to_actions_map[target][state_hash][counter] = []
                states_to_actions_map[target][state_hash][counter].append(action_name)

        return states_to_actions_map

    def _load_interesting_actions_map(self):
        interesting_actions_stmt = """
            SELECT target, prev_state_hash, next_state_hash, action_name, count(*) as amount
            FROM step 
            FORCE INDEX (comb)
            WHERE training_id=%s AND prev_game_type=%s
            GROUP BY target, prev_state_hash, action_name, next_state_hash, prev_game_type, next_game_type
            HAVING prev_state_hash != next_state_hash
            AND NOT (prev_game_type = "PRIVESC" AND next_game_type="NETWORK") 
        """ # IMPORTANT TO ALSO AVOID PRIVESC -> NETWORK ACTIONS
        # ORDER BY target, prev_state_hash, amount
        Log.logger.debug([interesting_actions_stmt, (self.training_id, self.game_type)])

        # This will just create an array per state of actions that lead to new states, but we could also
        # be smarter by providing a probability distribution so actions that lead to more states are prioritised
        results = self.connection.query(interesting_actions_stmt, (self.training_id, self.game_type))
        # Log.logger.debug(results)
        interesting_actions_map = {}

        for res in results:
            state_hash      = res['prev_state_hash']
            action_name     = res['action_name']
            target          = res['target']
            if target not in interesting_actions_map:
                interesting_actions_map[target] = {}
            if state_hash not in interesting_actions_map[target]:
                interesting_actions_map[target][state_hash] = {}
            interesting_actions_map[target][state_hash][action_name] = 1

        for target in interesting_actions_map:
            Log.logger.debug(f"Loaded {len(interesting_actions_map)} states with interesting actions for target {target}")

        return interesting_actions_map

    def _check_if_no_goals_where_reached(self):
        query =  f"SELECT count(*) as amount FROM step WHERE (reward_reasons LIKE '%{Constants.REWARD_FOR_REGULAR_USER_SESSION_KEY}%' OR reward_reasons LIKE '%{Constants.REWARD_FOR_SUPER_USER_SESSION_KEY}%') "
        query += " AND prev_game_type = %s"
        results = self.connection.query(query, (self.game_type, ))
        # Log.logger.debug([query, self.game_type])
        amount = int(results[0]['amount'])
        # Log.logger.debug([results, amount])

        if amount == 0:
            return True
        else:
            return False

    def _get_available_targets(self):
        stmt    = "SELECT distinct(target) as target FROM training_states WHERE training_id=%s"
        results = self.connection.query(stmt, (self.training_id,))
        return [res['target'] for res in results]

    def _filter_states_for_those_that_lead_to_key_state(self, initial_state, key_state):
        """
        :return:
            This needs to return a map that links target -> state hash -> next state -> actions to get there, where there are
            only next states if they lead to a session
        """
        Log.add_debug_medium_ascii(f"filter {self.game_type}")

        options = {
            'amount_of_orphan_nodes_to_skip': 1,
            'debug':                          self.DEBUG_MODE,
            'hide_recommendation':            True,
            'graph_type':                     'directed',
            'skip_checks':                    True,
        }

        key_states_to_action_per_target = {}
        for target in self._get_available_targets():
            # Log.logger.debug(f"Processing target: {target}")
            # Skip global since we don't queries for that
            if target == Constants.GLOBAL_TARGET:
                continue

            # 1.1) First we iterate for every target we have, querying for the max transition_id available from training_states
            max_transition_id = Learner.get_training_state_max_transition_id(self.connection, self.training_game_id, target)
            Log.logger.debug(f"max_transition_id for training_game_id {self.training_game_id} of target {target} is {max_transition_id}")

            if max_transition_id is not None:
                # 1.2) Once we get the max transition id, we create a Graph for it
                Log.logger.debug("Querying for transition id %d" % max_transition_id)

                training_milestone = Graph.TrainingMilestone([], None, None)
                Graph.get_results(self.connection, self.training_id, max_transition_id, self.game_type, target, training_milestone)

                state_hash_to_node, state_json_to_hash = Graph.create_node_hashes_map(self.game_type, training_milestone, target, options, True)
                self.DEBUG_MODE and Log.logger.debug("Finished create_node_hashes_map")
                # Log.logger.debug(state_hash_to_node)
                try:
                    G, pos, final_edge_labels = Graph.create_graph_and_pos(state_hash_to_node, options)
                    self.DEBUG_MODE and Log.logger.debug("Finished create_graph_and_pos")
                except:
                    Log.logger.error("Error trying to create graph => %s" % traceback.format_exc())
                    Log.logger.warning("Will try to run again with checks")
                    options['skip_checks'] = False
                    G, pos, final_edge_labels = Graph.create_graph_and_pos(state_hash_to_node, options)

                if G is not None:
                    # 1.3) If there is a graph, we now get all the simple paths to a key state
                    self.DEBUG_MODE and Log.logger.debug(f"starting get_all_simple_paths_from_initial_state_to_key_state from {initial_state} to {key_state}")
                    paths = Graph.get_all_simple_paths_from_initial_state_to_key_state(G, initial_state, key_state)
                    self.DEBUG_MODE and Log.logger.debug("Finished get_all_simple_paths_from_initial_state_to_key_state")
                    # Log.logger.debug([initial_state, key_state, paths])

                    states_that_lead_to_session = {}
                    for path in paths:
                        path_list = Graph.json_path_to_hash_path(path)
                        # Log.logger.debug(path_list)
                        for state in path_list:
                            states_that_lead_to_session[state] = 1

                    # 1.4) Now for each state we got, we will calculate the shortest path it has to a session
                    for state_hash in states_that_lead_to_session:
                        # Get the shortest path from this state to a session
                        state_json      = state_hash_to_node[state_hash]['state_json']
                        shortest_path   = Graph.get_shortest_path_to_key_state(G, state_json, key_state)
                        self.DEBUG_MODE and Log.logger.debug("Finished get_shortest_path_to_key_state for state %s" % state_json)

                        next_state_json = shortest_path[1] #only the next state
                        action_name     = final_edge_labels[state_json, next_state_json].split(" ")[0] #action that got me to that state

                        if target not in key_states_to_action_per_target:
                            key_states_to_action_per_target[target] = {}

                        shortest_path_as_hashes = []
                        for state_in_json in shortest_path:
                            path_state_hash = state_json_to_hash[state_in_json]
                            shortest_path_as_hashes.append(path_state_hash)

                        # 1.5) Add now for each target, each state its action and their path to session
                        key_states_to_action_per_target[target][state_hash] = {
                            "action_name":     action_name,
                            "next_state_hash": state_json_to_hash[next_state_json],
                            "path_to_session": ",".join(shortest_path_as_hashes)
                        }
                    
                    Log.logger.debug("Finished setting up Graph")
                else:
                    Log.logger.debug("G is None!")
                    return {}
            else:
                return {}

        return key_states_to_action_per_target

@dataclass
class PredictionResult:
    action_name:              str
    action_source:            str
    action_reason:            str
    action_options:           dict = field(default_factory=dict)
    action_options_source:    dict = field(default_factory=dict)
    option_errors:            dict = field(default_factory=dict)
    action_type:              str  = ""
    network_predicted_action: str  = ""
    action_extra:             dict = field(default_factory=dict)
    state_hash:               str  = ""
    action_data:              dict = field(default_factory=dict)

class BasePredictor(ABC):
    def __init__(self, game_type: str, predictor_loader: PredictorLoader):
        # COMMON
        self.actions_to_use = predictor_loader.actions_to_use
        self.game_type      = game_type

        # STATE DATA
        self.states_to_actions_map           = predictor_loader.states_to_actions_map
        self.states_counter_map              = predictor_loader.states_counter_map
        self.interesting_actions_map         = predictor_loader.interesting_actions_map
        self.key_states_to_action_per_target = predictor_loader.key_states_to_action_per_target
        self.no_goals_reached_yet            = predictor_loader.no_goals_reached_yet # Checks if any reward reason matches a goal

        # NN
        self.training_network = predictor_loader.training_network
        self.torch_device     = predictor_loader.torch_device

        # OPTIONS
        self.options_recommender = predictor_loader.options_recommender
        self.prioritized_actions = predictor_loader.prioritized_actions_map
        self.agent_options       = predictor_loader.agent_options

        # Filtered actions for counter method
        self.actions_to_use_weights, self.actions_to_use_without_exploits_weights = self._filter_actions_to_use()

        # actions_to_use_without_exploits_weights => used when no goal was reached yet and there are no ports available for the state

    def _filter_actions_to_use(self):
        actions_to_use_weights, actions_to_use_without_exploits_weights = [], []
        for action in self.actions_to_use:
            if action in self.prioritized_actions:
                weight = self.prioritized_actions[action]
                actions_to_use_without_exploits_weights.append(weight)
                actions_to_use_weights.append(weight)
            elif action in BLACKLISTED_ACTIONS:
                actions_to_use_without_exploits_weights.append(0)
                actions_to_use_weights.append(0)
            elif action.startswith("exploit/"):
                actions_to_use_without_exploits_weights.append(0)
                actions_to_use_weights.append(10)
            elif action in PRIORITIZED_AUXILIARY_ACTIONS:
                    actions_to_use_without_exploits_weights.append(10)
                    actions_to_use_weights.append(10)
            else: # non prioritized auxiliary actions
                actions_to_use_without_exploits_weights.append(1)
                actions_to_use_weights.append(1)

        # Log.logger.debug(self.actions_to_use)
        # Log.logger.debug(actions_to_use_weights)
        # Log.logger.debug(actions_to_use_without_exploits_weights)

        return actions_to_use_weights, actions_to_use_without_exploits_weights

    def get_states_to_actions_map(self):
        return self.states_to_actions_map

    def get_interesting_actions_map(self):
        return self.interesting_actions_map

    def get_options_recommender(self):
        return self.options_recommender

    @abstractmethod
    def predict(self, target: str, state_received: State, action_history: list) -> PredictionResult:
        raise NotImplementedError("You need to implement this method!")

class CounterPredictor(BasePredictor):
    def __init__(self, *args):
        super().__init__(*args)

        # CONSTANTS
        if self.game_type == Constants.GAME_TYPE_NETWORK:
            self.PCT_TO_PICK_STATE_THAT_LEADS_TO_GOAL = 0.5
        else:
            self.PCT_TO_PICK_STATE_THAT_LEADS_TO_GOAL = 0.2

        self.PCT_TO_PICK_GREEDY_ACTION = 0.3

    def get_random_action_prediction(self, state):
        game_type = state.deduce_game_type()

        if game_type == Constants.GAME_TYPE_NETWORK:
            # Log.logger.debug(["self.no_goals_reached_yet", self.no_goals_reached_yet])
            if len(state.get_open_ports()) == 0 and self.no_goals_reached_yet:
                # THIS IS NOT GOOD FOR TRAINING BUT GOOD FOR EXPLORATION
                random_action = random.choices(self.actions_to_use, weights=self.actions_to_use_without_exploits_weights)[0]
            else:
                random_action = random.choices(self.actions_to_use, weights=self.actions_to_use_weights)[0]
        else:
            random_action = random.choices(self.actions_to_use, self.actions_to_use_weights)[0]

        random_action_prediction = PredictionResult(action_name=random_action, action_source="RANDOM", action_reason="Plain random action")

        return random_action_prediction

    def create_greedy_prediction_result(self, state):
        observation = state.get_transform_state_to_observation(self.game_type)

        action_source, action_name, action_extra = DQN.pick_action_name_from_nn_sequencial(
            self.actions_to_use,
            observation,
            self.training_network,
            self.torch_device,
            action_history=[])

        prediction_result = PredictionResult(
            action_name=action_name, action_source="GREEDY", action_extra=action_extra,
            network_predicted_action=action_name, action_reason="Chosen by Network"
        )

        return prediction_result

    def create_prediction_result_of_action_that_leads_to_session(self, target, state_hash):
        picked_action_name_that_leads_to_session = self.key_states_to_action_per_target[target][state_hash]['action_name']
        picked_next_state_hash                   = self.key_states_to_action_per_target[target][state_hash]['next_state_hash']
        path_to_session                          = self.key_states_to_action_per_target[target][state_hash]['path_to_session']

        prediction_result = PredictionResult(action_name=picked_action_name_that_leads_to_session,
                            action_source='LEADS_TO_GOAL', action_reason="Leads to state %s which is the path to a goal: %s" % (picked_next_state_hash, path_to_session))

        return prediction_result

    def get_amount_of_actions_performed_in_state(self, target, state_hash):
        target_and_state_present_in_states_counter_map = target in self.states_counter_map and state_hash in self.states_counter_map[target]

        if target_and_state_present_in_states_counter_map:
            amount_of_actions_performed_in_state = self.states_counter_map[target][state_hash]
            # Log.logger.info("For target %s and state_hash %s got amount_of_actions_performed_in_state:%d" % (target, state_hash, amount_of_actions_performed_in_state))
        else:
            amount_of_actions_performed_in_state = 0

        return amount_of_actions_performed_in_state

    def get_random_interesting_action_for_state(self, target, state_hash):
        important_actions_for_this_state = self.interesting_actions_map[target][state_hash]
        # Log.logger.debug("Interesting actions available: %s" % ",".join(important_actions_for_this_state))

        return PredictionResult(action_name=random.choice(list(important_actions_for_this_state.keys())), action_source="INTERESTING", action_reason="Leads to new states")

    def get_if_we_should_pick_an_interesting_action_for_state(self, target, state_hash, randomness_end, randomness_step): # 0.2 to do 5 times each action on average
        target_and_state_in_interesting_actions_map = target in self.interesting_actions_map and state_hash in self.interesting_actions_map[target]

        if not target_and_state_in_interesting_actions_map:
            return False

        # 2) Check how many actions where already performed in this state
        amount_of_actions_performed_in_state = self.get_amount_of_actions_performed_in_state(target, state_hash)

        # amount_of_actions_performed_in_state = 3000
        # amount_of_actions_to_use             = 300

        # This means that when we use on average 7 times each action, we will then only pick a random action 30% of the time
        amount_of_actions_to_use = len(self.actions_to_use)
        ratio          = amount_of_actions_performed_in_state / amount_of_actions_to_use
        randomness_pos = 1 - max(randomness_end, 1 - (randomness_step * ratio) )

        Log.logger.info(f"{self.game_type} For state {state_hash} with {amount_of_actions_performed_in_state}/{amount_of_actions_to_use} actions done and ratio of {ratio} will request interesting actions with P({randomness_pos})")

        # Do we have important actions?
        return random.random() < randomness_pos

    def pick_interesting_or_random_action_based_on_the_amount_of_actions_executed_for_that_state(self, target, state, state_hash):
        if self.get_if_we_should_pick_an_interesting_action_for_state(target, state_hash, randomness_end=0.3, randomness_step=0.1): #at worst 30% of the time we pick a random action, 
            return self.get_random_interesting_action_for_state(target, state_hash)
        else:
            Log.logger.warning("No interesting actions for the state, will return a random one")

            random_action = self.get_random_action_prediction(state)
            return random_action

    def predict(self, target: str, state: State, action_history: list) -> PredictionResult:
        """
            First we check if there are any actions that lead to a new state:
            1) If there are actions that lead to a new state AND we flip the coin on PCT_TO_PICK_STATE_THAT_LEADS_TO_GOAL PERCENTAGE: (e.g 50% of the time)
                1.1) If we flip a coin and hit the PCT_TO_PICK_GREEDY_ACTION PERCENTAGE AND we are not in the explore mode: (e.g 30% of the time)
                    1.1.1) We return the recommendation from the Neural Network
                1.2) If we flip a coin and dont hit the  PCT_TO_PICK_GREEDY_ACTION PERCENTAGE: (e.g 70% of the time)
                    1.2.1) We return the action loaded by self.key_states_to_action_per_target
            2) If there were no actions that lead to a new state or we did not hit the PCT_TO_PICK_STATE_THAT_LEADS_TO_GOAL PERCENTAGE:
                2.1) We either choose an "interesting action" which led to new states on a %
                2.2) Or we just return a random action


            Here we need to decide an action by getting a random value and then depending on the value either:
                1) If there are any actions that in this state led to new states, choose randomly between them if not GOTO 2
                2) For all the actions available in the current state, pick a random one

            We do this by getting:
                a) The amount of actions attempted for the current state
                b) What actions actually led to new states
        :param
            network_information: This should have the state_to_state_filtered_actions_map map, which links each state to the next states that have a path to a session
        :return:
        """

        state_hash = state.get_state_hash(self.game_type)

        target_and_state_already_known                     = target in self.key_states_to_action_per_target and state_hash in self.key_states_to_action_per_target[target]
        should_pick_a_state_to_lead_a_goal                 = random.random() < self.PCT_TO_PICK_STATE_THAT_LEADS_TO_GOAL
        should_pick_a_greedy_action                        = random.random() < self.PCT_TO_PICK_GREEDY_ACTION
        should_pick_a_greedy_action_and_profile_is_explore = should_pick_a_greedy_action and self.agent_options['PROFILE'] != Constants.PROFILE_EXPLORE

        if target_and_state_already_known:
            if should_pick_a_state_to_lead_a_goal: # 50% of the time for network or 20% for privesc
                if should_pick_a_greedy_action_and_profile_is_explore: # 30% of the time when we are not exploring (17% for net, 7% for priv)
                    return self.create_greedy_prediction_result(state)
                else:
                    return self.create_prediction_result_of_action_that_leads_to_session(target, state_hash)
            else:
                return self.pick_interesting_or_random_action_based_on_the_amount_of_actions_executed_for_that_state(target, state, state_hash)
        else:
            return self.pick_interesting_or_random_action_based_on_the_amount_of_actions_executed_for_that_state(target, state, state_hash)

class GreedyPredictor(BasePredictor):
    def __init__(self, *args):
        super().__init__(*args)

    def predict(self, target: str, state: State, action_history: list) -> PredictionResult:
        observation = state.get_transform_state_to_observation(self.game_type)

        action_source, action_name, action_extra = DQN.pick_action_name_from_nn_sequencial(self.actions_to_use, observation, self.training_network, self.torch_device, action_history)

        return PredictionResult(
            action_name=action_name, action_source=action_source, action_extra=action_extra,
            network_predicted_action=action_name, action_reason="Chosen by Network"
        )

class EpsilonGreedyPredictor(BasePredictor):
    def __init__(self, *args):
        super().__init__(*args)

        # TODO: CALCULATE EPSILON BY ITSELF

    def predict(self, target: str, state: State, action_history: list) -> PredictionResult:
        raise NotImplementedError("First you need to calculate epsilon here!")

        # self.DEFAULT_EPSILON = 1
        # epsilon = DEFAULT_EPSILON  # default
        #
        # if target not in self.epsilon_data:
        #     Log.logger.warn("Unable to find target %s in epsilon_data %s" % (target, self.epsilon_data))
        # elif state_hash in self.epsilon_data[target]:
        #     epsilon = self.epsilon_data[target][state_hash]
        # else:
        #     Log.logger.warn("state %s was not found, will apply the default epsilon of %d" % (state_hash, DEFAULT_EPSILON))
        #
        # Log.logger.debug("Using epsilon: %s with epsilon_data %s and state_hash %s" % (epsilon, self.epsilon_data, state_hash))
        #
        # prediction_result = PredictionResult(
        #     action_name=action_name, action_source=action_source, action_extra=action_extra,
        #     network_predicted_action=action_name, action_reason="Chosen by Network"
        # )
        #
        # # ===> THEN WE DECIDE
        # if random.random() < epsilon:
        #     random_action_name = numpy.random.choice(self.actions_to_use)
        #     # random_action_name_idx = {k: v for v, k in enumerate(actions_to_use)}[random_action_name]
        #     prediction_result.action_name=random_action_name
        # else:
        #     return None

    # GETTERS

    # def get_epsilon_data(self):
    #     return self.epsilon_data
