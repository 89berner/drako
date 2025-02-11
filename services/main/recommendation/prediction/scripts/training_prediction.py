#curl -d @/root/drako/containers/drako/scripts/api/file.json 192.168.2.11:4000/predict

import torch
import json
from re import X
import lib.Recommendation.Prediction        as Prediction
import lib.Common.Exploration.Actions       as Actions
import lib.Recommendation.Prediction.Helper as Helper
import dataclasses
from lib.Exploration.Agent.Utils import load_agent_options
from lib.Common import Utils
import gc
import os
import time
import traceback
import lib.Recommendation.Prediction.Options as Options
import docker

from lib.Common.Utils    import Constants
from lib.Common.Utils.Db import Db
import lib.Common.Utils.Log as Log

from flask            import Flask, request
from werkzeug.serving import run_simple

from lib.Common.Training.Learner import get_current_training_training_game_ids

from queue import Queue, Empty
from threading import Thread, Lock

PID = os.getpid()

# INITIALIZATIONS
Log.initialize_log("2", "%s/training_prediction-%d.log" % (Constants.LOGS_FOLDER_PATH, PID), PID)
Log.add_info_large_ascii("Predict")
Actions.initialize()
Actions.client.load_metasploit_actions()

# This is not thread safe, create a new one per thread or use locks
staging_connection_lock = Lock()
staging_connection = Db(db_host=Constants.DRAGON_STAGING_DB_IP, db_name=Constants.get_dragon_staging_db(), db_password=Constants.DRAGON_DB_PWD)

# set to True to inform that the app needs to be re-created
to_reload = False

TRAINING_ID = int(os.getenv('TRAINING_ID'))
FORCE_CPU   = bool(os.getenv('FORCE_CPU'))

Log.logger.info(f"Using training_id from environment: {TRAINING_ID} and force_cpu: {FORCE_CPU}")

# TODO: IMPLEMENT HERE USING THREADPOOL SINCE IT TAKES AT LEAST 1 SECOND PER CONTAINER TO GET CPU USAGE

# WE SHOULD CREATE THREADS PER CONTAINER VISIBLE AND KILL OTHER THREADS WHEN A CONTAINER IS NOT LONGER LIVINGs

# docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
# containers_map = {}
# def containers_loop():
#     import concurrent.futures

#     Log.logger.debug("more")

#     while True:
#         containers = docker_client.containers.list()

#         # with concurrent.futures.ThreadPoolExecutor(max_workers=max(len(containers), 30)) as executor:
#         #     container_stats = list(
#         #         executor.map(
#         #             lambda container: (container, docker_client.containers.get(container.name).stats(stream=False)),
#         #             containers))
#         # Log.logger.debug(container_stats)
#         time.sleep(5)

#         # for container in containers:
#         #     container_name = container.name
#         #     if container_name.startswith("agent"):
#         #         stats = docker_client.containers.get(container_name).stats(stream=False)
#         #         # Log.logger.debug(stats)
#         #         usage_delta  = stats['cpu_stats']['cpu_usage']['total_usage'] - stats['precpu_stats']['cpu_usage']['total_usage']
#         #         system_delta = stats['cpu_stats']['system_cpu_usage'] - stats['precpu_stats']['system_cpu_usage']
#         #         len_cpu      = stats['cpu_stats']['online_cpus']

#         #         # Log.logger.debug([usage_delta, system_delta, len_cpu])

#         #         percentage = (usage_delta / system_delta) * len_cpu * 100
#         #         percent = round(percentage, 2)

#         #         epoch = int(time.time())
#         #         if container_name not in containers_map:
#         #             containers_map[container_name] = {}
#         #         if epoch not in containers_map[container_name]:
#         #             containers_map[container_name][epoch] = percent

#         #         # Log.logger.debug("(%s) Percentage is %f" % (container_name, percent))

#         # Log.logger.debug(containers_map)
# Thread(target=containers_loop, daemon=True).start()

# DATABASE QUEUE_check_if_no_goals_where_reached
db_operations = Queue()
def database_loop(number):
    connection = Db(db_host=Constants.DRAGON_STAGING_DB_IP, db_name=Constants.get_dragon_staging_db(), db_password=Constants.DRAGON_DB_PWD)
    # local_staging_connection = Db(db_host=Constants.DRAGON_STAGING_DB_IP, db_name=Constants.DRAGON_STAGING_DB_NAME, db_password=Constants.DRAGON_DB_PWD)
    while True:
        try:
            item = db_operations.get()
            stmt = item['stmt']
            data = item['data']

            Log.logger.debug("(%d) Executing %s..." % (number, stmt[:30]))
            try:
                connection.execute(stmt, data)
                Log.logger.debug("(%d) Finished executing %s..." % (number, stmt[:30]))
            except:
                Log.logger.error("(%d) ERROR IN EXECUTE, will sleep for 5 seconds => %s" % (number, traceback.format_exc()))
                time.sleep(5)
                connection.renew_connection_and_cursor()
        except:
            Log.logger.error("(%d) ERROR IN QUEUE, will sleep for 5 seconds => %s" % (number, traceback.format_exc()))
            time.sleep(5)

    connection.close()

# lets keep a couple threads in case one dies
Thread(target=database_loop, args=(1,), daemon=True).start()
Thread(target=database_loop, args=(2,), daemon=True).start()
Thread(target=database_loop, args=(3,), daemon=True).start()
Thread(target=database_loop, args=(4,), daemon=True).start()

# RELOAD_WAITING_PERIOD = 60*10
# def reload_loop():
#     while True:
#         time.sleep(RELOAD_WAITING_PERIOD)
#         # Log.logger.info("Thread will request a reload since %d seconds passed" % RELOAD_WAITING_PERIOD)
#         global to_reload
#         to_reload = True
# Thread(target=reload_loop, daemon=True).start()

agent_options_map = None
UPDATE_AGENT_OPTIONS_PERIOD = 30
def agent_options_loop():
    # local_staging_connection = Db(db_host=Constants.DRAGON_STAGING_DB_IP, db_name=Constants.DRAGON_STAGING_DB_NAME, db_password=Constants.DRAGON_DB_PWD)
    while True:
        # Log.logger.info("Thread will request new agent options since %d seconds passed" % UPDATE_AGENT_OPTIONS_PERIOD)
        Log.logger.debug("Acquiring lock for agent_options_loop")
        staging_connection_lock.acquire()
        global agent_options_map
        try:
            agent_options_map = load_agent_options(staging_connection)
        except:
            Log.logger.error("ERROR => %s" % traceback.format_exc())    
        staging_connection_lock.release()
        Log.logger.debug("Released lock for agent_options_loop")
        # Log.logger.debug("Will now wait..")
        time.sleep(UPDATE_AGENT_OPTIONS_PERIOD)
Thread(target=agent_options_loop, daemon=True).start()

training_network_information = None

def get_training_network_information():
    gc.collect()    
    torch.cuda.empty_cache()
    # Log.logger.debug("Emptied cuda cache")

    connection = Db(db_host=Constants.DRAGON_STAGING_DB_IP, db_name=Constants.get_dragon_staging_db(), db_password=Constants.DRAGON_DB_PWD)

    counter = 0
    while counter < 100:
        try:
            if agent_options_map == None:
                Log.logger.debug("Sleeping 5 seconds to wait for agent_options_map to be loaded")
                time.sleep(5)

            Log.logger.debug("Loading training_network_information")
            current_training_ids         = get_current_training_training_game_ids(connection, TRAINING_ID)
            training_network_information = Helper.load_network_information(connection, current_training_ids, FORCE_CPU, agent_options_map)
            Log.logger.debug("Got training_network_information!")
            
            return training_network_information
        except:
            Log.logger.error("ERROR => %s" % traceback.format_exc())
            counter += 1
            time.sleep(5)

    connection.close()

def reload_app_loop():
    while True:
        time.sleep(10*60)
        global training_network_information

        training_network_information = get_training_network_information()
        Log.logger.debug("We just reloaded training_network_information, I will now sleep 10 minutes")

Thread(target=reload_app_loop, daemon=True).start()

def get_app():
    Log.logger.info("Creating the app!")
    app = Flask(__name__)

    training_network_information = get_training_network_information()

    @app.route("/predict", methods=['POST'])
    def predict():
        """
            This should receive:
             target,
             JSON of the state,
             game_Type
             action_history

        :return: prediction
        """
        if training_network_information is None:
            return "App is not ready yet since training_network_information is None!"
        else:
            # LOAD REQUEST DATA
            prediction_req_data = Prediction.load_prediction_request_data(request.form)
            request_data_dict = request.form.to_dict(flat=False)
            request_data      = json.dumps(request_data_dict, sort_keys=True, indent=4)
            # Log.logger.info(f"Processing request:\n{request_data}")

            prediction_result = Prediction.predict(prediction_req_data, training_network_information)

            Log.logger.info(f"Returning for state {prediction_result.state_hash} result action:{prediction_result.action_name} source:{prediction_result.action_source} decision:{prediction_result.action_reason} while network predicted action was:{prediction_result.network_predicted_action}")
            return dataclasses.asdict(prediction_result)

    @app.route("/predict_options", methods=['POST'])
    def predict_options():
        """
            This should receive:
             target,
             JSON of the state,
             game_Type
             action_history

        :return: prediction
        """
        if training_network_information is None:
            return "App is not ready yet since training_network_information is None!"
        else:
            # LOAD REQUEST DATA
            prediction_req_data = Prediction.load_prediction_request_data(request.form)
            # Log.logger.debug("1")
            action_name         = request.form['action_name']
            # Log.logger.debug("2")

            action_options, action_options_source, option_errors = Options.generate_options(prediction_req_data, action_name)
            # Log.logger.debug("3")

            Log.logger.debug([action_options, action_options_source, option_errors])
            return {
                "action_options":        action_options,
                "action_options_source": action_options_source,
                "option_errors":         option_errors,
            }

    @app.route("/set_agent_id", methods=['POST'])
    def set_agent_id():
        """
            This should receive:
             training_id
             container_id
             container_name

        :return: agent_id
        """

        training_id    = request.form['training_id']
        container_id   = request.form['container_id']
        container_name = request.form['container_name']

        agent_id = ""
        try:
            stmt     = "SELECT container_id FROM agent WHERE container_id=%s AND training_id=%s"
            staging_connection_lock.acquire()
            res      = staging_connection.query(stmt, (container_id, training_id))

            if len(res) == 0:
                Log.logger.warning("I did not find this container, will write it to the table!")
                stmt = "INSERT INTO agent(container_id, name, training_id) VALUES(%s,%s,%s)"
                agent_id = staging_connection.execute(stmt, (container_id, container_name, training_id))
                Log.logger.info("Inserted the agent %s and got agent_id %s" % (container_id, agent_id))
            else:
                Log.logger.info("Found container %s" % container_id)

            staging_connection_lock.release()
        except:
            Log.logger.error("ERROR => %s" % traceback.format_exc())
            staging_connection_lock.release()


        return_data = {
            "agent_id": agent_id
        }

        return return_data

    @app.route("/create_episode", methods=['POST'])
    def create_episode():
        """
            This should receive:
                target,
                episode_runner,
                episode_agent_name,
                environment_type,
                episode_configuration_json,
                training_id,

        :return: episode_id
        """

        # TODO: WE SHOULD NOT BE GETTING A NULL TARGET BUT WE DO AT THE START
        target = None
        if target in request.form:
            target = request.form['target']
        # Log.logger.debug(target)

        stmt = "INSERT INTO episode(target, runner, agent_name, environment, configuration, training_id) VALUES (%s,%s,%s,%s,%s,%s)"
        # Log.logger.debug(request.form)
        data = (target, request.form['episode_runner'], request.form['episode_agent_name'], request.form['environment_type'], request.form['episode_configuration_json'], request.form['training_id'])
        # Log.logger.debug(data)

        staging_connection_lock.acquire()
        episode_id = 0
        try:
            episode_id = staging_connection.execute(stmt, data)
        except:
            Log.logger.error("ERROR => %s" % traceback.format_exc())
        staging_connection_lock.release()

        return_data = {
            "episode_id": episode_id
        }

        return return_data

    @app.route("/create_game", methods=['POST'])
    def create_game():
        """
            This should receive:
                episode_id
                training_id
                game_type

        :return: episode_id
        """

        stmt = "INSERT INTO game(episode_id, training_id, name) VALUES (%s,%s,%s)"
        # Log.logger.debug(request.form)
        data = (request.form['episode_id'], request.form['training_id'], request.form['game_type'])
        # Log.logger.debug(data)

        staging_connection_lock.acquire()
        game_id = 0
        try:
            game_id = staging_connection.execute(stmt, data)
        except:
            Log.logger.error("ERROR => %s" % traceback.format_exc())
        staging_connection_lock.release()

        return_data = {
            "game_id": game_id
        }

        return return_data

    @app.route("/agent_options", methods=['POST'])
    def agent_options():
        """
            This should receive:
             attributes

        :return: agent options
        """

        data = agent_options_map

        return data

    @app.route("/db_operation", methods=['POST'])
    def db_operation():
        """
            This should receive:
             stmt
             data

        :return: bool if successful
        """
        # Log.logger.debug(request.form)
        operation_data = {
            "stmt": request.form['stmt'],
            "data": Utils.json_loads(request.form['data'])
        }
        # Log.logger.debug(operation_data)
        db_operations.put_nowait(operation_data)

        queue_size = db_operations.qsize()
        # if queue_size > 100:
        Log.logger.debug(f"db_operations queue size is now: {queue_size}!")

        return {"success": True}

    @app.route('/reload', methods=['POST', 'GET'])
    def reload():
        Log.logger.info("Reload requested!")
        global to_reload
        to_reload = True

        return "reloaded"

    @app.route("/")
    def index():
        reduced_network_information = Helper.show_network_information(training_network_information)

        return reduced_network_information

    return app

# RELOADER APP

class AppReloader(object):
    def __init__(self, create_app):
        self.create_app = create_app
        self.app = create_app()
        Log.logger.debug("Finishing AppReloader")

    def get_application(self):
        global to_reload
        if to_reload:
            self.app  = self.create_app()
            to_reload = False

        # Log.logger.debug("Returning app")
        return self.app

    def __call__(self, environ, start_response):
        app = self.get_application()
        return app(environ, start_response)


# This application object can be used in any WSGI server
# for example in gunicorn, you can run "gunicorn app"
application = AppReloader(get_app)

# if __name__ == '__main__':
#     run_simple('0.0.0.0', int(Constants.PREDICTION_TRAINING_API_PORT), application, use_reloader=False, use_debugger=True, use_evalex=True)

# staging_connection.close()