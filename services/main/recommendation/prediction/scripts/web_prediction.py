#curl -d @/root/drako/containers/drako/scripts/api/file.json 192.168.2.10:4000/predict

import lib.Recommendation.Prediction        as Prediction
import lib.Common.Exploration.Actions       as Actions
import lib.Recommendation.Prediction.Helper as Helper

import traceback
import dataclasses

from lib.Common.Utils    import Constants
from lib.Common.Utils.Db import Db
import lib.Common.Utils.Log as Log

from lib.Common.Training.Learner import get_main_training_ids

from flask            import Flask, request

# INITIALIZATIONS
Log.initialize_log("2", "%s/web_prediction.log" % Constants.LOGS_FOLDER_PATH)
Log.add_info_large_ascii("Predict")
Actions.initialize()
Actions.client.load_metasploit_actions()

app = Flask(__name__)
prod_connection          = None
main_network_information = None

def load_information():
    global main_network_information
    global prod_connection
    prod_connection          = Db(db_host=Constants.DRAGON_PROD_DNS, db_name=Constants.DRAGON_PROD_DB_NAME, db_password=Constants.DRAGON_DB_PWD)
    main_training_ids        = get_main_training_ids(prod_connection)
    main_network_information = Helper.load_network_information(prod_connection, main_training_ids)

@app.route("/predict_web", methods=['POST'])
def predict_web():
    """
        This is aimed at the web interface
    """

    prediction_result = Prediction.predict_web(request.form, main_network_information)

    Log.logger.debug(f"Returning for state {prediction_result.state_hash} result action:{prediction_result.action_name} source:{prediction_result.action_source} decision:{prediction_result.action_reason} while network predicted action was:{prediction_result.network_predicted_action}")
    return dataclasses.asdict(prediction_result)


@app.route("/")
def index():
    reduced_network_information = Helper.show_network_information(main_network_information)

    return reduced_network_information

if __name__ == '__main__':
    load_information()
    app.run('0.0.0.0', int(Constants.PREDICTION_WEB_API_PORT), use_reloader=False, use_debugger=True, use_evalex=True)
