from datetime import datetime

from lib.Common import Utils as Utils
from lib.Common.Training import Learner as Learner
from lib.Common.Utils import Log as Log

from lib.Recommendation.Prediction.Predictor import GreedyPredictor, CounterPredictor, EpsilonGreedyPredictor, PredictorLoader

import torch

def show_network_information(network_information):
    reduced_network_information = {}
    for className in ["COUNTER", "GREEDY", "EPSILONGREEDY"]:
        reduced_network_information[className] = {
            "PRIVESC": {
                "states_to_actions_map":   network_information['PRIVESC'][className].get_states_to_actions_map(),
                "interesting_actions_map": network_information['PRIVESC'][className].get_interesting_actions_map(),

            },
            "NETWORK": {
                "states_to_actions_map":   network_information['NETWORK'][className].get_states_to_actions_map(),
                "interesting_actions_map": network_information['NETWORK'][className].get_interesting_actions_map(),
            },
            "time": network_information['time']
        }

    return reduced_network_information

def load_network_information(connection, training_ids, force_cpu=False, agent_options = None):
    network_information = {
        "PRIVESC": load_network_information_per_game(connection, training_ids, "PRIVESC", force_cpu, agent_options),
        "NETWORK": load_network_information_per_game(connection, training_ids, "NETWORK", force_cpu, agent_options),
        "time":    datetime.now(),
    }

    Log.logger.debug("Returning network_information")
    return network_information

def load_network_information_per_game(connection, training_ids, game_type, force_cpu, agent_options):
    game_training_data = training_ids[game_type]
    predictor_loader = PredictorLoader(connection, game_training_data['training_id'], game_training_data['training_game_id'], game_type, force_cpu, agent_options)

    return {
        "COUNTER":       CounterPredictor(game_type, predictor_loader),
        "GREEDY":        GreedyPredictor(game_type, predictor_loader),
        "EPSILONGREEDY": EpsilonGreedyPredictor(game_type, predictor_loader),
    }
