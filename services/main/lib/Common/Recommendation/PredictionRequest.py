import lib.Common.Utils.Constants as Constants

from lib.Common.Exploration.Actions.Data import ActionRecommendation

import time
import requests
import traceback
import lib.Common.Utils.Log as Log
import lib.Common.Utils as Utils
import os

MAX_RETRIES = 5

def get_prediction_api_ip():
    prediction_api_ip = os.getenv('PREDICTION_API_IP')
    if prediction_api_ip is None:
        raise ValueError("Variable PREDICTION_API_IP is missing")
    return prediction_api_ip

def send_action_request(data_to_send, prediction_api_ip):
    try:
        response = requests.post(f"http://{prediction_api_ip}:{Constants.PREDICTION_TRAINING_API_PORT}/predict", data=data_to_send)
        if response.status_code != 200:
            prediction_error = response.text
            Log.logger.warn("Error with prediction! => %s" % prediction_error)
            time.sleep(5)
            return None, prediction_error
        else:
            # Log.logger.debug("API RESPONSE => %s" % response.text[:500])
            response_data = Utils.json_loads(response.text)

            action_recommendation = ActionRecommendation(response_data['action_source'], response_data['action_reason'],
                                                         response_data['action_name'], response_data['action_type'],
                                                         response_data['action_options'],
                                                         response_data['option_errors'], response_data['action_data'],
                                                         response_data['action_extra'])

            return action_recommendation, None
    except:
        Log.logger.warn(
            "Error with prediction! Will wait for 5 seconds before trying again => %s" % traceback.format_exc())
        time.sleep(5)
        return None

def request_action(environment, target, state, action_history, prediction_name, extra_data = {}):
    game_type = environment.get_current_game_type()
    Log.logger.debug("A new action has been requested from agent for game %s" % game_type)

    data_to_send = {
        'target':              target,
        'state':               state.get_json(),
        'game_type':           game_type,
        'action_history':      Utils.dump_json(action_history),
        'environment_options': Utils.dump_json(environment.get_environment_options()),
        'exploration_method':  prediction_name,
    }
    data_to_send.update(extra_data)

    if prediction_name == "COUNTER":
        data_to_send['action_history'] = Utils.dump_json([]) # Not needed
    # Log.logger.debug(data_to_send)

    prediction_api_ip = get_prediction_api_ip()
    # Log.logger.debug(f"prediction_api_ip: {prediction_api_ip}")

    counter = 0
    while counter < MAX_RETRIES:
        Log.logger.debug(f"({counter}/{MAX_RETRIES}) Attempting to get action prediction..")
        counter += 1

        action_recommendation, prediction_error = send_action_request(data_to_send, prediction_api_ip)
        if action_recommendation is not None:
            return action_recommendation
        else:
            Log.logger.debug("ERROR_PREDICTOR: Sleeping 5 seconds due to predictor error %s" % prediction_error)
            time.sleep(5)

    raise ValueError("Error with prediction! Failed after %d retries => %s" % (MAX_RETRIES, prediction_error))

def send_request(data_to_send, endpoint):
    prediction_api_ip = get_prediction_api_ip()

    url = f"http://{prediction_api_ip}:{Constants.PREDICTION_TRAINING_API_PORT}/{endpoint}"
    Log.logger.debug(f"Will send a request to {url}")
    response = requests.post(url, data=data_to_send)
    if response.status_code != 200:
        prediction_error = response.text
        Log.logger.warn("Error with prediction request for url %s with data %s! => %s" % (url, data_to_send, prediction_error))
        time.sleep(1)
        return None, prediction_error
    else:
        Log.logger.debug(f"API RESPONSE => {response.text}")
        response_data = Utils.json_loads(response.text)

        return response_data

def request_options(environment, target, state, action_name):
    game_type = environment.get_current_game_type()
    Log.logger.debug("Options has been requested from agent for game %s" % game_type)

    data_to_send = {
        'target':              target,
        'state':               state.get_json(),
        'game_type':           game_type,
        'environment_options': Utils.dump_json(environment.get_environment_options()),
        'action_name':         action_name,
    }

    counter = 0
    Log.logger.debug(f"({counter}/{MAX_RETRIES}) Attempting to get options prediction..")
    counter += 1

    return send_request(data_to_send, "predict_options")
#
# {
#     "action_options":        action_options,
#     "action_options_source": action_options_source,
#     "option_errors":         option_errors,
# }

def request_agent_options():
    res = send_request({}, "agent_options")
    # Log.logger.debug(res)

    return res


def request_agent_id(training_id, container_id, container_name):
    data = {
        "training_id":    training_id,
        "container_id":   container_id,
        "container_name": container_name,
    }
    res  = send_request(data, "set_agent_id")

    return res['agent_id']

def send_db_operation(stmt, data):
    data = {
        "stmt":      stmt,
        "data":      Utils.dump_json(data)
    }
    # Log.logger.debug(stmt)
    # Log.logger.debug(data)

    send_request(data, "db_operation")

    return True

def create_episode(target, episode_runner, episode_agent_name, environment_type, episode_configuration_json, training_id):
    data = {
        "target":                     target,
        "episode_runner":             episode_runner,
        "episode_agent_name":         episode_agent_name,
        "environment_type":           environment_type,
        "episode_configuration_json": episode_configuration_json,
        "training_id":                training_id,
    }
    # Log.logger.debug(data)

    res  = send_request(data, "create_episode")

    return res['episode_id']

def create_game(episode_id, training_id, game_type):
    data = {
        "episode_id":  episode_id,
        "training_id": training_id,
        "game_type":   game_type,
    }
    # Log.logger.debug(data)
    res  = send_request(data, "create_game")

    return res['game_id']
