import lib.Recommendation.Prediction.Options as Options
from lib.Recommendation.Prediction.Options.OptionsRecommender import OptionsRecommender

import lib.Common.Utils.Log           as Log
import lib.Common.Utils               as Utils
import lib.Common.Exploration.Actions as Actions

from lib.Common.Exploration.Environment.State import State

import dataclasses
from dataclasses import dataclass, field

MAX_GUESSING_TRIES = 50

@dataclass
class PredictionRequestData:
    environment_options: dict
    target:              str
    state:               State
    game_type:           str
    exploration_method:  str
    skip_payload:        str
    action_history:      list = field(default_factory=list)

def load_prediction_request_data(form_data):
    environment_options_str = form_data.get('environment_options')
    environment_options     = Utils.json_loads(environment_options_str)
    target                  = form_data.get('target') #environment_options['target'] => this pointed to the target_ip
    state_dict              = Utils.json_loads(form_data.get('state'))
    state                   = State(state_dict)
    game_type               = form_data.get('game_type')
    exploration_method      = form_data.get('exploration_method')
    skip_payload            = form_data.get('skip_payload')

    action_history = None
    if 'action_history' in form_data:
        action_history = Utils.json_loads(form_data.get('action_history'))

    prediction_request_data = PredictionRequestData(
        environment_options=environment_options, target=target, state=state, action_history=action_history,
        game_type=game_type, exploration_method=exploration_method, skip_payload=skip_payload
    )
    # Log.logger.info(dataclasses.asdict(prediction_request_data))

    return prediction_request_data

def predict(prediction_req_data, network_information):
    # SET SOME VARS
    game_type          = prediction_req_data.game_type
    exploration_method = prediction_req_data.exploration_method

    # GET PREDICTOR OBJECT
    predictor = network_information[game_type][exploration_method]

    # START LOOP OF TRYING TO GET A CORRECT PREDICTION FOR WHICH WE HAVE NO OPTIONS ERRORS
    # TODO: Change so we don't need to loop here
    counter = 0
    while True:
        Log.logger.debug(f"Going through loop {counter} of predicting an action and option")
        counter += 1
        # GET PREDICTION
        prediction_result = predictor.predict(prediction_req_data.target, prediction_req_data.state, prediction_req_data.action_history)

        # SET EXTRA DATA
        prediction_result.state_hash  = prediction_req_data.state.get_state_hash(game_type)
        action_func                   = Actions.client.get_action(game_type, prediction_result.action_name)
        prediction_result.action_type = action_func.action_type

        # GENERATE OPTIONS
        options_recommender = predictor.get_options_recommender()
        action_name         = prediction_result.action_name
        prediction_result.action_options, prediction_result.action_options_source, prediction_result.option_errors \
            = Options.generate_options(prediction_req_data, action_name, options_recommender)

        # CHECK OPTIONS ARE CORRECT
        if counter > MAX_GUESSING_TRIES:
            Log.logger.warning(f"We reached {MAX_GUESSING_TRIES} so we will accept whatever we got")
            break
        elif not prediction_result.option_errors:
            break
        else:
            Log.logger.debug("Will try guessing again since we had an option error")

    # FLAG TO AVOID TOO MUCH DATA GOING THROUGH THE WIRE
    if not prediction_req_data.skip_payload == "1":
        if hasattr(action_func, 'is_metasploit_action'):
            prediction_result.action_data = action_func.action_data
        else:
            prediction_result.action_data = None

    # Log.logger.debug(dataclasses.asdict(prediction_result))

    return prediction_result

def predict_web(form_data, main_network_information):
    # LOAD REQUEST DATA
    prediction_req_data = load_prediction_request_data(form_data)

    exploration_method = "GREEDY"
    predictor          = main_network_information[prediction_req_data.game_type][exploration_method]
    prediction_result  = predictor.predict(prediction_req_data.target, prediction_req_data.state, prediction_req_data.action_history)

    # Log.logger.debug(dataclasses.asdict(prediction_result))

    return prediction_result


