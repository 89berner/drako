from lib.Training.Learner.Builder import build_learner
import lib.Common.Utils.Log as Log
import lib.Common.Utils as Utils
import lib.Common.Exploration.Actions as Actions
import lib.Common.Utils.Constants as Constants
from lib.Common.Utils.Db import Db

from sklearn.model_selection import ParameterGrid

import lib.Common.Training.ExploitationPath as ExploitationPath
import json
import time
import os

import lib.Common.Utils as Utils

import pandas as pd

from lib.Common.Training.Learner import load_benchmark_config_options

class Benchmark:
    def __init__(self, game_type, benchmark_id = None):
        self.game_type = game_type

        self.staging_connection  = Db(db_host=Constants.DRAGON_STAGING_TRAINING_DB_IP, db_name=Constants.get_dragon_staging_db(), db_password=Constants.DRAGON_DB_PWD)

        self.benchmark_results     = {}
        self.converged_steps_map   = {}
        self.learners_to_benchmark = {}

        self.log_level                          = "1"
        self.stop_training_at                   = None
        self.skip_until_reaching                = None
        self.training_starts_at_rewarding_games = False
        self.training_target                    = None
        self.pause_benchmark_at                 = None
        self.training_limit                     = None
        self.load_main_training                 = False
        self.amount_of_runs                     = 1

        # LEARNER DEPEND ON ACTIONS BEING INITIALIZED
        Actions.initialize()
        Actions.client.load_metasploit_actions()

        self.benchmark_id = benchmark_id

    def set_amount_of_runs(self, amount_of_runs):
        self.amount_of_runs = amount_of_runs

    def set_log_level(self, log_level):
        self.log_level = log_level

    def set_stop_training(self, stop_training_at):
        self.stop_training_at = stop_training_at

    def set_skip_until_reaching(self, skip_until_reaching):
        self.skip_until_reaching = skip_until_reaching

    def set_training_starts_at_rewarding_games(self):
        self.training_starts_at_rewarding_games = True

    def set_training_target(self, target):
        self.training_target = target

    def set_pause_benchmark_at(self, pause_benchmark_at):
        self.pause_benchmark_at = pause_benchmark_at

    def set_training_limit(self, training_limit):
        self.training_limit = training_limit

    def set_load_main_training(self):
        self.load_main_training = True

    def get_benchmark_options(self):
        return {
            "stop_training_at":                   self.stop_training_at,
            "skip_until_reaching":                self.skip_until_reaching,
            "training_starts_at_rewarding_games": self.training_starts_at_rewarding_games,
            "training_target":                    self.training_target,
            "pause_benchmark_at":                 self.pause_benchmark_at,
            "training_limit":                     self.training_limit,
            "load_main_training":                 self.load_main_training,
        }

    def get_default_learner_configs(self):
        return load_benchmark_config_options(self.staging_connection, self.game_type)

    def add_learner(self, learner_name, configuration_overrides):
        self.learners_to_benchmark[learner_name] = configuration_overrides

    def create_benchmark_id(self):
        # Check for benchmark training above the start
        stmt = "INSERT INTO benchmark(game_type, benchmark_config, benchmark_config_defaults, converged_steps_map, benchmark_options) VALUES (%s,%s,%s,%s,%s)"
        config_overrides_str    = Utils.dump_json(self.learners_to_benchmark)
        config_defaults_str     = Utils.dump_json(self.get_default_learner_configs())
        options_str             = Utils.dump_json(self.get_benchmark_options())
        converged_steps_map_str = Utils.dump_json(self.converged_steps_map)
        new_benchmark_id     = self.staging_connection.execute(stmt, (self.game_type, config_overrides_str, config_defaults_str, converged_steps_map_str, options_str))
        print(f"Got new benchmark id {new_benchmark_id}")

        return new_benchmark_id

    def create_benchmarked_training(self):
        print(f"Starting to create new training")

        stmt = "INSERT INTO training(benchmark_id) VALUES (%s)"
        new_training_id = self.staging_connection.execute(stmt, (self.benchmark_id, ))
        print(f"Got new training id {new_training_id}")

        # NOW CREATE FOLDER
        os.mkdir(f"/share/networks/{new_training_id}/")
        os.mkdir(f"/share/logs/{new_training_id}/")

        return new_training_id

    def set_learner_information_for_training(self, learner_family, learner_name, params_to_override, new_training_id):
        stmt = "UPDATE training SET learner_family=%s, learner_name=%s, trainer_config=%s WHERE training_id=%s"
        Log.logger.debug(f"Updated the trainer setting learner_family:{learner_family} learner_name:{learner_name} trainer_config:{params_to_override}")
        self.staging_connection.execute(stmt, (learner_family, learner_name, Utils.dump_json(params_to_override), new_training_id))

    def create_learner_to_benchmark(self, learner_name, new_training_id, params_to_override):
        # INITIALIZE LEARNER
        learner = build_learner(self.game_type, learner_name, new_training_id, load_main_training=self.load_main_training, profile=None,
                                            continue_from_latest_point=None, params_to_override=params_to_override, benchmark_id=self.benchmark_id, staging_connection=self.staging_connection)

        if self.skip_until_reaching is not None:
            learner.set_skip_until_reaching(self.skip_until_reaching)

        if self.stop_training_at is not None:
            learner.set_stop_training_after(self.stop_training_at)

        if self.training_starts_at_rewarding_games:
            learner.set_training_starts_at_rewarding_games()

        if self.training_target is not None:
            learner.set_training_target(self.training_target)

        if self.pause_benchmark_at is not None:
            learner.set_pause_benchmark_at(self.pause_benchmark_at)

        if self.training_limit is not None:
            learner.set_training_limit(self.training_limit)

        # DEFAULTS
        learner.set_steps_to_populate_training_states(999999999999)  # JUST DONT
        learner.set_steps_per_nn_save(999999999999)

        return learner

    def update_benchmark_table(self):
        converged_steps_map_str = Utils.dump_json(self.converged_steps_map)
        training_rows           = self.calculate_exploitation_paths()
        training_rows_str       = Utils.dump_json(training_rows)

        stmt = "UPDATE benchmark SET converged_steps_map=%s, benchmark_result=%s WHERE benchmark_id=%s"
        stmt_data = (converged_steps_map_str, training_rows_str, self.benchmark_id)
        self.staging_connection.execute(stmt, stmt_data)
        # Log.logger.debug([stmt, stmt_data])

    def perform_bechmark(self):
        if self.benchmark_id is None:
            self.benchmark_id = self.create_benchmark_id()
            print(f"Benchmark created with training_id {self.benchmark_id}")
        else:
            raise ValueError("Cannot perform a new benchmark when a benchmark_id is already configured")

        for learner_name in self.learners_to_benchmark:
            configuration_overrides = self.learners_to_benchmark[learner_name]
            Log.logger.debug(f"Will start benchmarking {learner_name}")
            parameter_grid = list(ParameterGrid(configuration_overrides))
            print(f"Will now start trying {len(parameter_grid)} parameter configurations")

            params_counter = 0
            for params_to_override in parameter_grid:
                params_counter += 1
                print(f"({params_counter}/{len(parameter_grid)}) Will use configuration {params_to_override}")

                for run in range(1, self.amount_of_runs + 1):
                    Log.logger.debug(f"Going through run {run}")

                    new_training_id = self.create_benchmarked_training()
                    Log.close_log()
                    Log.initialize_log(self.log_level, f"/share/logs/{new_training_id}/benchmark.log")
                    learner = self.create_learner_to_benchmark(learner_name, new_training_id, params_to_override)
                    self.set_learner_information_for_training(learner.learner_family, learner_name, params_to_override, new_training_id)

                    finished  = False
                    converged = False
                    while not finished:
                        finished, target = learner.benchmark()# Finished might return false if it was paused
                        print(f"Finished:{finished} for target:{target} will wait for 1 second for data to be uploaded to the DB")
                        time.sleep(1)

                        last_transition_id  = learner.get_benchmark_last_transition_id()
                        state_map_result    = self.load_benchmarks(target, last_transition_id)

                        if new_training_id in state_map_result:
                            state_map = state_map_result[new_training_id]

                            exploitation_paths_arr, goal_paths, best_goal_paths = ExploitationPath.create_training_path(self.game_type, state_map)
                            if len(best_goal_paths) > 0:
                                for goal_path in best_goal_paths:
                                    Log.logger.info(f"We reached a goal! {goal_path}")
                                converged = True
                        else:
                            best_goal_paths = []
                            exploitation_paths_arr, goal_paths = {}, {}

                        self.add_to_converged_steps_map(learner_name, params_counter, run, converged, learner.training_id, exploitation_paths_arr, goal_paths, best_goal_paths, params_to_override)

                        stmt = "INSERT INTO benchmark_step(benchmark_id, benchmark_counter, training_id, exploitation_paths, goal_paths, best_goal_paths, converged) VALUES(%s,%s,%s,%s,%s,%s,%s)"
                        self.staging_connection.execute(stmt, (self.benchmark_id, learner.get_benchmark_counter(), learner.training_id, Utils.dump_json(exploitation_paths_arr), Utils.dump_json(goal_paths), Utils.dump_json(best_goal_paths), converged))

                        # UPLOAD RESULTS TO DB
                        self.update_benchmark_table()

                    print("Now we will persist the NN")
                    learner.update_game_training()

        Log.logger.debug(self.converged_steps_map)

        Log.close_log()

    def add_to_converged_steps_map(self, learner_name, params_counter, run, converged, training_id, exploitation_paths_arr, goal_paths, best_goal_paths, params_to_override):
        if learner_name not in self.converged_steps_map:
            self.converged_steps_map[learner_name] = {}
        if params_counter not in self.converged_steps_map[learner_name]:
            self.converged_steps_map[learner_name][params_counter] = {}
        if run not in self.converged_steps_map[learner_name][params_counter]:
            self.converged_steps_map[learner_name][params_counter][run] = {
                "tostr":                  "",
                "amount":                 0,
                "benchmark_steps":        1,
                "training_id":            training_id,
                "exploitation_paths_arr": exploitation_paths_arr,
                "goal_paths":             goal_paths,
                "best_goal_paths":        best_goal_paths,
                "params_to_override":     params_to_override,
            }
        else:
            self.converged_steps_map[learner_name][params_counter][run]["exploitation_paths_arr"] = exploitation_paths_arr
            self.converged_steps_map[learner_name][params_counter][run]["goal_paths"]       = goal_paths
            self.converged_steps_map[learner_name][params_counter][run]["best_goal_paths"]  = best_goal_paths
            self.converged_steps_map[learner_name][params_counter][run]["benchmark_steps"] += 1

        if converged is True:
            self.converged_steps_map[learner_name][params_counter][run]["amount"] += 1
            self.converged_steps_map[learner_name][params_counter][run]["tostr"] += "-"
        elif converged is False:
            self.converged_steps_map[learner_name][params_counter][run]["tostr"] += "_"
        else:
            self.converged_steps_map[learner_name][params_counter][run]["tostr"] += "?"

        Log.logger.debug(self.converged_steps_map)

    def get_benchmark_training_ids(self):
        query = "SELECT training_id FROM training WHERE benchmark_id=%s"
        results = self.staging_connection.query(query, (self.benchmark_id, ))

        training_ids = []
        for res in results:
            training_ids.append(str(res['training_id']))
        return training_ids

    def load_benchmarks(self, target, transition_id=None):
        print(f"Now we will retrieve all training games for benchmark_id {self.benchmark_id} and transition_id: {transition_id}")

        # 3) RETURN THEN A MAP OF RESULTS[TRAINING_ID] = STATE_MAP

        # 1) IF THERE IS A PROVIDED TRAINING_ID THEN ONLY USE THAT ONE IF NOT LOAD ALL TRAINING_IDS FOR BENCHMARK
        training_ids = self.get_benchmark_training_ids()

        # 2) LOAD STATE MAP FOR EACH TRAINING_ID IN LIST
        self.benchmark_results = ExploitationPath.load_state_maps(self.staging_connection, training_ids, target, transition_id)
        # print(self.benchmark_results)
        # print(self.benchmark_results.keys())
        stmt = """
            SELECT tg.training_id,tg.learner_options_benchmarked, t.learner_name
            FROM training_game tg
            JOIN training t on tg.training_id=t.training_id
            WHERE tg.benchmark_id=%s
        """
        results = self.staging_connection.query(stmt, (self.benchmark_id,))
        # print(results)
        for result in results:
            training_id       = result['training_id']
            benchmark_options = Utils.json_loads(result['learner_options_benchmarked'])
            learner_name      = result['learner_name']
            if training_id in self.benchmark_results:
                # print(self.benchmark_results[training_id])
                for state_hash in self.benchmark_results[training_id][self.game_type]:
                    self.benchmark_results[training_id][self.game_type][state_hash]["benchmark_options"] = benchmark_options
                    self.benchmark_results[training_id][self.game_type][state_hash]["learner_name"]      = learner_name

        # THIS IS A HACK, ONLY SO THAT THIS DOES NOT REPLACE AN ACTIVE TRAINING
        # AND IS USEFUL WHEN LOADING AN EXISTING ONE
        # Log.logger.debug(self.converged_steps_map)
        # Log.logger.debug(len(self.converged_steps_map))
        if len(self.converged_steps_map) == 0:
            self.load_converged_steps_map()
        # Log.logger.debug(self.converged_steps_map)

        return self.benchmark_results

    def load_converged_steps_map(self):
        Log.logger.debug("Loading converged steps map...")
        query = "SELECT converged_steps_map FROM benchmark WHERE benchmark_id=%s"
        results = self.staging_connection.query(query, (self.benchmark_id,))
        if len(results) > 0:
            self.converged_steps_map = Utils.json_loads(results[0]['converged_steps_map'])
        else:
            raise ValueError(f"I did not find any benchmark with id {self.benchmark_id}")

    def get_training_id_converging_data(self, training_id):
        for learner_name in self.converged_steps_map:
            for param_run in self.converged_steps_map[learner_name]:
                for run in self.converged_steps_map[learner_name][param_run]:
                    if self.converged_steps_map[learner_name][param_run][run]['training_id'] == training_id:
                        return self.converged_steps_map[learner_name][param_run][run]

        raise ValueError(f"We did not find the training_id {training_id} this should never happen!")

    def calculate_exploitation_paths(self, debug=False):
        ############# Calculate training paths per training_id

        rows = []
        for training_id in self.benchmark_results:
            state_map = self.benchmark_results[training_id]
            # print(state_map)

            # Log.logger.info(state_map)
            example_state_hash = list(state_map[self.game_type].keys())[0]
            config       = Utils.dump_json(state_map[self.game_type][example_state_hash]["benchmark_options"])
            learner_name = state_map[self.game_type][example_state_hash]["learner_name"]
            exploitation_paths_arr, goal_paths_str, best_goal_paths_str = ExploitationPath.create_training_path(self.game_type, state_map, print_debug=debug)

            training_id_converging_data = self.get_training_id_converging_data(training_id)

            goal_paths_str_arr = []
            for path_str in goal_paths_str:
                goal_paths_str_arr.append(path_str)

            best_goal_paths_str_arr = []
            for path_str in best_goal_paths_str:
                best_goal_paths_str_arr.append(path_str)

            data_row = {
                'LEARNER':            learner_name,
                'TRAINING_ID':        training_id,
                'CONFIG':             config,
                'BEST_GOAL_PATHS':    '\n'.join(best_goal_paths_str_arr),
                'GOAL_PATHS':         '\n'.join(goal_paths_str_arr),
                'EXPLOITATION_PATHS': '\n'.join(exploitation_paths_arr),
                "CONVERGE_AMOUNT":    training_id_converging_data["amount"],
                "CONVERGE_STR":       training_id_converging_data["tostr"],
                "BENCHMARK_STEPS":    training_id_converging_data["benchmark_steps"]
            }
            rows.append(data_row)
        return rows

    def build_exploitation_paths_df(self, rows):
        exploitation_paths_df = pd.DataFrame()
        counter = 1
        for data_row in rows:
            row_df = pd.DataFrame(data_row, index=[counter])
            exploitation_paths_df = pd.concat([row_df, exploitation_paths_df])
            counter += 1

        exploitation_paths_df = exploitation_paths_df.reindex(index=exploitation_paths_df.index[::-1])  # To reverse the order of the table having the first entries at the top
        exploitation_paths_df = exploitation_paths_df.style.set_properties(**{
            'text-align': 'center',
            'white-space': 'pre-wrap',
        })

        return exploitation_paths_df

    def build_per_state_benchmark_df(self):
        df = pd.DataFrame()
        counter = 1
        for training_id in self.benchmark_results:
            state_map = self.benchmark_results[training_id][self.game_type]
            for state_hash in state_map:
                benchmark_data = state_map[state_hash]
                top_dqn        = benchmark_data["top_dqn"]
                config         = Utils.dump_json(benchmark_data["benchmark_options"])
                state_json     = benchmark_data["state"]
                # next_states = benchmark_data["next_states"]

                row_df = pd.DataFrame(
                    {'TRAINING_ID': training_id, 'CONFIG': config, 'STATE_HASH': state_hash, 'STATE': state_json,
                     'TOP_DQN': top_dqn}, index=[counter]
                )
                # Log.logger.debug(row_df)
                df = pd.concat([row_df, df])
                counter += 1

        df = df.reindex(index=df.index[::-1])  # To reverse the order of the table having the first entries at the top
        # FILTER
        df = df[df['STATE_HASH'] == 'FCE91']
        # This is to align the text to the center
        df = df.style.set_properties(**{
            'text-align': 'center',
            'white-space': 'pre-wrap',
        })
        # This is to align the header to the center
        left_aligned_df = df.set_table_styles([dict(selector='th', props=[('text-align', 'center')])])

        return left_aligned_df
