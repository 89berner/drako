import datetime
import time
import traceback
import re
import sys

from lib.Training.Trainer.Common import review_target_health, stop_agents_and_reset_current_vm, stop_agent_init, set_target_ip
import lib.Common.Utils.Log as Log
import lib.Common.Training.Learner
import lib.Common.Utils as Utils
import lib.Common.Training.ExploitationPath as ExploitationPath

import lib.Common.Utils.Constants as Constants

AMOUNT_OF_SESSIONS_TO_TRIGGER_RESET     = 60
MAX_TIME_PER_TARGET_BEFORE_RESET        = 2  # TODO: REVIEW TO INCREASE
MAX_AMOUNT_OF_NETWORK_CONVERGING_CHECKS = 30 #30
MAX_AMOUNT_OF_PRIVESC_CONVERGING_CHECKS = 10 #30
MAX_SESSIONS                            = 2000
MAX_SUPER_SESSIONS                      = 500

ENABLE_NO_RESULTS_LIMIT = False

class ConvergingTracker:
    def __init__(self, game_type, staging_connection, training_id, target_key):
        self.game_type          = game_type
        self.staging_connection = staging_connection
        self.training_id        = training_id
        self.target_key         = target_key

        self.converging_steps        = 0
        self.non_converging_steps    = 0
        self.converging_ratio        = 0
        self.converging_row          = 0
        self.longest_converging_row  = 0
        self.converging_path         = ""
        self.last_exploitation_paths = {}
        self.last_goal_paths         = {}
        self.last_best_goal_paths    = {}
        self.goal_path_counters      = {}
        self.last_goal_paths_clean   = {}

    def gather_converging_data(self):
        # CONVERGING INFORMATION
        state_map = ExploitationPath.load_state_maps(self.staging_connection, [str(self.training_id)], self.target_key)
        if self.training_id in state_map:
            state_map          = state_map[self.training_id]
            self.last_exploitation_paths, self.last_goal_paths, self.last_best_goal_paths = ExploitationPath.create_training_path(self.game_type, state_map, print_debug=False)

            if len(self.last_best_goal_paths) > 0:
                self.converging_path += "-"
                self.converging_steps += 1
                self.converging_row += 1
                if self.converging_row > self.longest_converging_row:
                    self.longest_converging_row = self.converging_row
            else:
                self.converging_path += "_"
                self.non_converging_steps += 1
                self.converging_row = 0

            # HERE WE CREATE A MAP OF THE VERSION WITHOUT BRACKETS OF GOAL PATHS
            # TO A LIST OF ALL GOAL PATHS WITH BRACKETS
            self.last_goal_paths_clean = {}
            for goal_path in self.last_goal_paths:
                clean_goal_path = re.sub(r'\(.*?\)', '', goal_path)
                if clean_goal_path not in self.last_goal_paths_clean:
                    self.last_goal_paths_clean[clean_goal_path] = []
                self.last_goal_paths_clean[clean_goal_path].append(goal_path)

            for clean_goal_path in self.last_goal_paths_clean:
                if clean_goal_path not in self.goal_path_counters:
                    self.goal_path_counters[clean_goal_path] = 0
                self.goal_path_counters[clean_goal_path] += 1

            self.converging_ratio = self.converging_steps / (self.converging_steps + self.non_converging_steps)
            # Log.logger.debug([self.last_goal_paths, self.converging_steps, self.non_converging_steps, self.converging_ratio])
        else:
            Log.logger.warning(f"I did not find the training_id {self.training_id} in the state_map!")

    def get_converging_string(self):
        return f"{self.converging_steps}/{self.non_converging_steps}={self.converging_ratio}, longest_converging_row:{self.longest_converging_row} => [{self.converging_path}]"

    def get_extra_data(self):
        return {
            # "exploitation_paths": self.last_exploitation_paths,
            "goal_paths":         self.last_goal_paths,
            "best_goal_paths":    self.last_best_goal_paths,
        }

class Monitor:
    def __init__(self, staging_connection, target, configuration):
        self.staging_connection = staging_connection
        self.training_id        = configuration.training_id
        self.target             = target
        self.target_id          = target['id']
        self.target_key         = target['ip']
        self.target_source      = target['source']
        self.target_name        = target['name']

        if 'wait_for_super' in target:
            self.wait_for_super = target['wait_for_super']
        else:
            self.wait_for_super = False

        self.learner_family     = configuration.learner_family
        self.learner_name       = configuration.learner_name
        self.configuration      = configuration

        self.amount_of_agents  = configuration.amount_of_agents
        # self.latest_episode_id = None

        self.total_actions_used = 0

        self.started_at            = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.start_time            = time.time()
        self.last_reset_start_time = time.time()

        self.converging_trackers = {
            "PRIVESC": ConvergingTracker("PRIVESC", staging_connection, self.training_id, self.target_key),
            "NETWORK": ConvergingTracker("NETWORK", staging_connection, self.training_id, self.target_key)
        }

        # RESETS
        self.time_to_reset = None

        self.minutes_per_target = configuration.minutes_per_target
        self.seconds_per_target = self.minutes_per_target * 60
        self.total_regular_sessions            = 0
        self.total_super_sessions              = 0
        self.total_resets                      = 0
        self.total_steps                       = 0
        self.total_positive_steps              = 0
        self.total_episodes                    = 0
        self.finished                          = 0

        self.last_amount_of_regular_sessions_for_reset = 0
        self.last_amount_of_super_sessions_for_reset   = 0

        self.finish_reason = "NOT_FINISHED"

    def gather_target_data(self):
        for game_type in self.converging_trackers:
            self.converging_trackers[game_type].gather_converging_data()

        # OTHERS
        self.total_actions_used      = self.get_amount_of_actions_used_for_target()
        self.total_positive_steps    = self.get_amount_of_positive_steps_for_target()

        regular_sessions = self.get_amount_of_regular_sessions_for_target()
        self.last_amount_of_regular_sessions_for_reset += regular_sessions - self.total_regular_sessions
        self.total_regular_sessions = regular_sessions

        super_sessions, episode_id = self.get_amount_of_super_sessions_for_target()
        if super_sessions > 0 and self.total_super_sessions == 0: # On the first time lets upload it as an example
            # TODO: Do it for all checking we haven't uploaded them yet
            try:
                self.add_new_super_episode(episode_id)
            except Exception:
                Log.logger.error("ERROR ADDING PROOF EPISODE => %s" % traceback.format_exc())
        self.last_amount_of_super_sessions_for_reset += super_sessions - self.total_super_sessions
        self.total_super_sessions = super_sessions

    def monitor_target(self):
        # LOOP UNTIL WE SURPASS THE TIME ALLOWED OR WE REACH A MAX AMOUNT OF X
        reached_max_time_allowed, reached_max_time_allowed_and_no_results, reached_max_converges, reached_max_sessions = False, False, False, False
        while not reached_max_time_allowed and not reached_max_converges and not reached_max_time_allowed_and_no_results and not reached_max_sessions:
            try:
                # SLEEP 60 seconds before another check
                time.sleep(60)
                # Log.logger.debug("time.time(): %d self.start_time:%d self.seconds_per_target:%d reached_max_time_allowed:%s" % (time.time(), self.start_time, self.seconds_per_target, reached_max_time_allowed ))

                ##############################################################
                ####### AT THE START WE CHECK IF THE TARGET IS HEALTHY #######
                ##############################################################
                only_target = self.configuration.target_id
                is_healthy = review_target_health(self.staging_connection, self.target, only_target)
                if not is_healthy:
                    Log.logger.warning("Current target is not healthy, will skip it")
                    self.finish_reason = "UNHEALTHY_TARGET"
                    break

                ##############################################
                ### THEN WE GATHER THE LATEST INFORMATION ###
                ##############################################

                self.gather_target_data()

                ##############################################################
                ### NOW WE CHECK IF THE SYSTEM NEEDS A RESET OF THE SYSTEM ###
                ##############################################################

                its_time_for_vm_reset = time.time() > self.last_reset_start_time + 60 * 60 * MAX_TIME_PER_TARGET_BEFORE_RESET

                # THIS IS DISABLED SINCE WHEN WE GET TOO MANY SESSIONS WE DONT WANT TO STOP IT FROM GOING TO MORE SUPER SESSIONS
                # WHY WOULD IT BE A BAD THING TO GET TOO MANY SESSIONS? AT WORST THE TARGET SHOULD BE UNHEALTHY AND STOP GIVING US SESSIONS
                # TODO: ADD CHECK THAT AFTER N SESSIONS WE DID NOT GET ANY FOR A LONG TIME
                amount_of_sessions_begets_reset = False #self.last_amount_of_regular_sessions_for_reset > AMOUNT_OF_SESSIONS_TO_TRIGGER_RESET # to avoid bad responses of the box and never getting super session due to restarting too fast

                should_reset = False
                if its_time_for_vm_reset or amount_of_sessions_begets_reset:  # two hours passed
                    if its_time_for_vm_reset:
                        Log.logger.warning(f"{MAX_TIME_PER_TARGET_BEFORE_RESET} hours have passed, we will reset the target and continue")
                        should_reset = True
                    elif amount_of_sessions_begets_reset: # DISABLED, CHECK COMMENT ABOVE
                        if self.time_to_reset is None:
                            Log.logger.debug("Now to avoid killing sessions too early, we will stop new agents from starting and allow any ongoing ones to continue")
                            stop_agent_init(self.staging_connection)

                            self.time_to_reset = time.time() + 60*60 # Lets give it one hour
                        elif time.time() < self.time_to_reset: # We should actually reset
                            Log.logger.debug(f"Current time is {datetime.datetime.fromtimestamp(int(time.time()))} has not reached {datetime.datetime.fromtimestamp(int(self.time_to_reset))} so we will not reset")
                        else:
                            Log.logger.warning(f"There were more than {AMOUNT_OF_SESSIONS_TO_TRIGGER_RESET} sessions found, we should reset the box")
                            self.last_amount_of_regular_sessions_for_reset = 0
                            should_reset = True

                    if should_reset:
                        stop_agents_and_reset_current_vm(self.staging_connection, self.target)
                        set_target_ip(self.staging_connection, self.target['ip'])

                        self.last_reset_start_time = time.time()
                        self.total_resets += 1
                        self.time_to_reset = None

                #################################################################
                ### HERE CHECK IF WE REACHED THE END OF PROCESSING THE TARGET ###
                #################################################################
                no_sessions_found                       = self.last_amount_of_regular_sessions_for_reset == 0
                reached_max_time_allowed                = time.time() > (self.start_time + self.seconds_per_target)
                reached_max_time_allowed_and_no_results = time.time() > (self.start_time + self.seconds_per_target / 2) and no_sessions_found

                reached_max_converges_for_network      = self.converging_trackers["NETWORK"].converging_row > MAX_AMOUNT_OF_NETWORK_CONVERGING_CHECKS
                reached_max_converges_for_privesc      = self.converging_trackers["PRIVESC"].converging_row > MAX_AMOUNT_OF_PRIVESC_CONVERGING_CHECKS
                reached_max_sessions                   = self.total_super_sessions > MAX_SUPER_SESSIONS and self.total_regular_sessions > MAX_SESSIONS
                probably_no_regular_sessions_available = self.converging_trackers["NETWORK"].converging_row == 0 and reached_max_converges_for_privesc

                if reached_max_time_allowed:
                    Log.logger.info("=" * 50)
                    Log.logger.info("We finished processing target since we reached the time limit")
                    Log.logger.info("=" * 50)
                    self.finish_reason = "TIME_LIMIT: %d MINUTES" % self.minutes_per_target
                elif ENABLE_NO_RESULTS_LIMIT and reached_max_time_allowed_and_no_results:
                    Log.logger.info("=" * 50)
                    Log.logger.info("We finished processing target since we reached the time limit without any results")
                    Log.logger.info("=" * 50)
                    self.finish_reason = "NO_RESULT_TIME_LIMIT: %d MINUTES" % ( self.minutes_per_target / 2 )
                elif reached_max_sessions:
                    Log.logger.info("=" * 50)
                    Log.logger.info("We finished processing target since we reached the max amount of sessions found")
                    Log.logger.info("=" * 50)
                    self.finish_reason = "MAX_SESSIONS_FOUND"
                elif (reached_max_converges_for_network and reached_max_converges_for_privesc) or probably_no_regular_sessions_available:
                    Log.logger.info("=" * 50)
                    self.finish_reason = "MAX_CONVERGING: Reached max amount of converging steps for "
                    for game_type in self.converging_trackers:
                        tracker = self.converging_trackers[game_type]
                        self.finish_reason += f"{game_type}: {tracker.converging_row} "
                    Log.logger.info("=" * 50)
                    reached_max_converges = True

                #############################################
                ######## FINALLY WE UPDATE STATISTICS #######
                #############################################
                self.print_target_statistics()
                self.update_target_statistics()
            except SystemExit:
                sys.exit(0)
            except Exception:
                Log.logger.error(f"Sleeping 1 minute due to error going through monitor loop: {traceback.format_exc()}")
                time.sleep(60)

        self.finished = 1
        self.gather_target_data()
        self.update_target_statistics()

    def update_target_statistics(self):
        # GET TOTAL EPISODES AND TOTAL STEPS
        count_stmt = "SELECT (SELECT count(*) FROM step WHERE training_id=%s) as total_steps, (SELECT count(*) FROM episode WHERE training_id=%s) as total_episodes FROM dual"
        results    = self.staging_connection.query(count_stmt, (self.training_id, self.training_id))
        if len(results) > 0:
            result = results[0]
            self.total_steps    = result['total_steps']
            self.total_episodes = result['total_episodes']

        select_stmt = "SELECT id FROM training_target WHERE training_id=%s AND target_ip=%s AND target_id=%s"
        results     = self.staging_connection.query(select_stmt, (self.training_id, self.target_key, self.target_id))

        avg_steps_per_min = 0
        if self.total_steps:
            avg_steps_per_min = self.total_steps / ((time.time() - self.last_reset_start_time) / 60)

        extra = {
            "NETWORK": self.converging_trackers["NETWORK"].get_extra_data(),
            "PRIVESC": self.converging_trackers["PRIVESC"].get_extra_data(),
            "TARGET":  self.target
        }

        network_conv_str = self.converging_trackers["NETWORK"].get_converging_string()
        network_conv_row = self.converging_trackers["NETWORK"].converging_row
        privesc_conv_str = self.converging_trackers["PRIVESC"].get_converging_string()
        privesc_conv_row = self.converging_trackers["PRIVESC"].converging_row

        Log.logger.debug(["NETWORK", network_conv_str, network_conv_row, "PRIVESC", privesc_conv_str, privesc_conv_row])
        if len(results) == 0:
            insert_stmt = """
            INSERT INTO 
            training_target(target_id, target_ip, training_id, minutes_per_target, total_steps, total_episodes, total_resets, total_regular_sessions, total_super_sessions, total_actions_used, finished, finish_reason, started_at, amount_of_agents, total_positive_steps, network_conv_str, network_conv_row, privesc_conv_str, privesc_conv_row, extra, target_name)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """
            self.staging_connection.execute(insert_stmt, (self.target_id, self.target_key, self.training_id, self.minutes_per_target, self.total_steps, self.total_episodes, self.total_resets, self.total_regular_sessions, self.total_super_sessions, self.total_actions_used, self.finished, self.finish_reason, self.started_at, self.amount_of_agents, self.total_positive_steps, network_conv_str, network_conv_row, privesc_conv_str, privesc_conv_row, Utils.dump_json(extra), self.target_name))
        else:
            update_stmt = """
                UPDATE training_target SET total_steps=%s, total_episodes=%s, total_resets=%s, total_regular_sessions=%s, total_super_sessions=%s, total_actions_used=%s, finished=%s, finish_reason=%s, ended_at=%s, avg_steps_per_min=%s, total_positive_steps=%s, network_conv_str=%s, network_conv_row=%s, privesc_conv_str=%s, privesc_conv_row=%s, extra=%s
                WHERE training_id=%s AND target_id=%s AND target_ip=%s
            """
            self.staging_connection.execute(update_stmt, (self.total_steps, self.total_episodes, self.total_resets, self.total_regular_sessions, self.total_super_sessions, self.total_actions_used, self.finished, self.finish_reason, datetime.datetime.today().strftime('%Y-%m-%d %H:%M:%S'), avg_steps_per_min, self.total_positive_steps, network_conv_str, network_conv_row, privesc_conv_str, privesc_conv_row, Utils.dump_json(extra), self.training_id, self.target_id, self.target_key))

        self.update_target_paths()

    def update_target_paths(self):
        for game_type in self.converging_trackers:
            tracker = self.converging_trackers[game_type]
            for clean_goal_path in tracker.last_goal_paths_clean:
                query = "SELECT target_path_id FROM training_target_path WHERE path=%s AND target=%s AND training_id=%s AND game_type=%s"
                results = self.staging_connection.query(query, (clean_goal_path, self.target_key, self.training_id, game_type))
                if len(results) == 0:
                    # INSERT
                    stmt = "INSERT INTO training_target_path(path, target, training_id, game_type) VALUES(%s,%s,%s,%s)"

                    target_path_id = self.staging_connection.execute(stmt, (clean_goal_path, self.target_key, self.training_id, game_type))
                else:
                    target_path_id = results[0]["target_path_id"]

                # NOW UPDATE
                stmt = "UPDATE training_target_path SET amount=%s WHERE target_path_id=%s"
                self.staging_connection.execute(stmt, (tracker.goal_path_counters[clean_goal_path], target_path_id))

                # MARK BEST GOAL
                best_goal_path = False
                raw_goal_paths = tracker.last_goal_paths_clean[clean_goal_path]
                for raw_goal_path in raw_goal_paths:
                    if raw_goal_path in tracker.last_best_goal_paths:
                        best_goal_path = True

                if best_goal_path:
                    Log.logger.info(f"Marking path {clean_goal_path} as best_goal_path!")
                    stmt = "UPDATE training_target_path SET best_goal_path=1 WHERE target_path_id=%s"
                    self.staging_connection.execute(stmt, (target_path_id, ))

    def print_target_statistics(self):
        total_steps, total_steps_in_minute, total_steps_with_reward, total_steps_for_network, total_steps_for_privesc, \
        total_steps_breaking_session, total_agents_with_session, total_unique_net_actions, total_unique_privesc_actions, \
        longest_privesc_streak, longest_agent, privesc_streak_avg, total_agents_running = self.get_steps_per_minute()

        message = f"({self.target['ip']}[{self.target_key}]) STEPS_PER_MINUTE={total_steps_in_minute}\n"
        message += f"TOTAL_AGENTS_RUNNING:{total_agents_running} TOTAL_STEPS={total_steps} TOTAL_NET_STEPS={total_steps_for_network} TOTAL_PRIVESC_STEPS={total_steps_for_privesc} TOTAL_STEPS_BREAKING_SESSION={total_steps_breaking_session}\n"
        message += f"AMOUNT_OF_REGULAR_SESSIONS={self.total_regular_sessions} AMOUNT_OF_SUPER_SESSIONS={self.total_super_sessions} TOTAL_AGENTS_WITH_SESSION={total_agents_with_session}\n"
        message += f"TOTAL_UNIQUE_NET_ACTIONS={total_unique_net_actions} TOTAL_UNIQUE_PRIVESC_ACTIONS={total_unique_privesc_actions}\n"
        message += f"LONGEST_PRIVESC_STREAK={longest_privesc_streak}({longest_agent}) PRIVESC_STREAK_AVG={privesc_streak_avg}"
        Log.logger.debug(message)

        #AND WITH REWARD TOTAL SO FAR:{total_steps_with_reward}

        # print_tester_results = False
        # if print_tester_results:
        #     res = self.get_latest_test_result()
        #     if res is not None:
        #         episode_id         = int(res["episode_id"])
        #         has_error          = res["has_error"]
        #         accumulated_reward = res["accumulated_reward"]
        #         total_steps        = res["total_steps"]
        #         positive_steps     = res["positive_steps"]
        #         created_at         = res["created_at"]
        #         updated_at         = res["updated_at"]

        #         elapsed = updated_at - created_at

        #         if episode_id != self.latest_episode_id:
        #             # if self.latest_episode_id is not None:
        #             #     Log.logger.debug("episode_id: %d is different than latest_episode_id: %d" % (episode_id, self.latest_episode_id))
        #             # else:
        #             #     Log.logger.debug("latest_episode_id is none and episode_id is %d" % episode_id)
        #             message = "EPISODE:%d ACCUMULATED_REWARD:%d POSITIVE_STEPS:%d/%d ACTIONS_USED:%d ELAPSED:%s" % (episode_id, accumulated_reward, positive_steps, total_steps, self.total_actions_used, elapsed)

        #             if has_error == 1:
        #                 message += " AND THERE ARE ERRORS!"

        #             Log.logger.debug(message)

        #             self.latest_episode_id = episode_id

    def get_amount_of_actions_used_for_target(self):
        query_stmt = """
            SELECT count(distinct step.action_name) as amount
            FROM step
            JOIN episode ON step.episode_id=episode.episode_id
            WHERE episode.target=%s AND episode.training_id=%s
        """
        results = self.staging_connection.query(query_stmt, (self.target_key, self.training_id))

        return results[0]['amount']

    def get_amount_of_super_sessions_for_target(self):
        """
            This needs to also the return episode_id of the first super session found
        """
        query_stmt = f"""
            SELECT MIN(step.episode_id) as episode_id, count(*) as amount
            FROM step
            JOIN episode ON step.episode_id=episode.episode_id
            WHERE step.reward_reasons LIKE '%{Constants.REWARD_FOR_SUPER_USER_SESSION_KEY}%' 
            AND step.target=%s AND step.training_id=%s AND episode.trainable=1
        """
        results = self.staging_connection.query(query_stmt, (self.target_key, self.training_id))

        return results[0]['amount'], results[0]['episode_id']

    def get_amount_of_regular_sessions_for_target(self):
        query_stmt = f"""
            select count(*) as amount
            FROM step
            JOIN episode ON step.episode_id=episode.episode_id
            WHERE step.reward_reasons LIKE '%{Constants.REWARD_FOR_REGULAR_USER_SESSION_KEY}%' 
            AND step.target=%s AND step.training_id=%s AND episode.trainable=1
        """
        results = self.staging_connection.query(query_stmt, (self.target_key, self.training_id))

        return results[0]['amount']

    def get_amount_of_positive_steps_for_target(self):
        query_stmt = """
            select count(*) as amount
            FROM step
            WHERE accumulated_reward > 0 
            AND step.target=%s AND step.training_id=%s
        """
        results = self.staging_connection.query(query_stmt, (self.target_key, self.training_id))

        return results[0]['amount']

    def add_new_super_episode(self, episode_id):
        stmt = "SELECT count(*) as amount_of_transitions FROM step WHERE training_id=%s"
        results = self.staging_connection.query(stmt, (self.training_id,))
        amount_of_transitions = results[0]['amount_of_transitions']

        stmt = """
            SELECT action_name, action_source, accumulated_reward 
            FROM step 
            WHERE target=%s AND episode_id=%s AND training_id=%s 
            ORDER BY transition_id
        """
        results = self.staging_connection.query(stmt, (self.target_key, episode_id, self.training_id))

        actions_entry = []
        for res in results:
            entry = "%s(%s)=%d" % (res['action_name'], res['action_source'], res['accumulated_reward'])
            actions_entry.append(entry)

        configuration_dict = lib.Common.Training.Learner.load_learner_options(self.staging_connection, self.learner_family, self.learner_name, game_type="ALL")

        insert_stmt = """
            INSERT INTO super_episode(training_id, episode_id, amount_of_transitions, target, actions, db_config, trainer_config, started_at)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
        """
        new_super_episode_id = self.staging_connection.execute(insert_stmt, (self.training_id, episode_id, amount_of_transitions, self.target_key, "\n".join(actions_entry), Utils.dump_json(configuration_dict), self.configuration.to_json(), self.started_at))

        return new_super_episode_id

    # def get_latest_test_result(self):
    #     stmt = """
    #             SELECT episode.episode_id, episode.has_error, episode.accumulated_reward, episode.finished, episode.positive_steps, episode.total_steps, episode.created_at, episode.updated_at 
    #             FROM  episode
    #             JOIN  test_episode ON episode.episode_id=test_episode.episode_id
    #             WHERE episode.test_episode=1 AND test_episode.test_failed=0 AND episode.training_id=%d AND episode.finished=1
    #             ORDER BY episode_id DESC LIMIT 1
    #             """ % self.training_id
    #     results = self.staging_connection.query(stmt)

    #     if len(results) > 0:
    #         return results[0]
    #     else:
    #         return None

    def get_steps_per_minute(self):
        stmt = """
            SELECT count(*) total_steps 
            FROM step 
            WHERE step.training_id=%s AND target=%s
        """
        results = self.staging_connection.query(stmt, (self.training_id, self.target_key))
        total_steps = int(results[0]['total_steps'])

        stmt = """
            SELECT count(*) total_steps_with_reward 
            FROM step 
            WHERE step.training_id=%s AND accumulated_reward > 0 AND target=%s
        """
        results = self.staging_connection.query(stmt, (self.training_id, self.target_key))
        total_steps_with_reward = int(results[0]['total_steps_with_reward'])

        stmt = """
            SELECT count(*) as total_steps_in_minute
            FROM step
            WHERE step.training_id=%s AND step.created_at >= NOW() - INTERVAL 1 minute AND target=%s
        """
        results = self.staging_connection.query(stmt, (self.training_id, self.target_key))
        total_steps_in_minute = int(results[0]["total_steps_in_minute"])

        stmt = """
            SELECT count(*) as total_steps_for_privesc 
            FROM step 
            WHERE training_id=%s AND prev_game_type = %s AND target=%s
        """
        results = self.staging_connection.query(stmt, (self.training_id, "PRIVESC", self.target_key))
        total_steps_for_privesc = int(results[0]['total_steps_for_privesc'])

        stmt = """
            SELECT count(*) as total_steps_for_network 
            FROM step 
            WHERE training_id=%s AND prev_game_type = %s AND target=%s
        """
        results = self.staging_connection.query(stmt, (self.training_id, "NETWORK", self.target_key))
        total_steps_for_network = int(results[0]['total_steps_for_network'])

        stmt = """
            SELECT count(*) as total_steps_breaking_session 
            FROM step 
            WHERE training_id=%s AND prev_game_type = %s AND next_game_type=%s AND target=%s
        """
        results = self.staging_connection.query(stmt, (self.training_id, "PRIVESC", "NETWORK", self.target_key))
        total_steps_breaking_session = int(results[0]['total_steps_breaking_session'])

        stmt = """
            SELECT count(*) as total_agents_with_session 
            FROM agent
            WHERE training_id=%s AND has_session=%s 
        """
        results = self.staging_connection.query(stmt, (self.training_id, 1))
        total_agents_with_session = int(results[0]['total_agents_with_session'])

        stmt = """
            SELECT count(*) as total_agents_running
            FROM agent
            WHERE training_id=%s AND running=1
        """
        results = self.staging_connection.query(stmt, (self.training_id,))
        total_agents_running = int(results[0]['total_agents_running'])

        stmt = """
            SELECT count(distinct(action_name)) as total_unique_net_actions 
            FROM step
            WHERE training_id=%s AND prev_game_type=%s 
        """
        results = self.staging_connection.query(stmt, (self.training_id, "NETWORK"))
        total_unique_net_actions = int(results[0]['total_unique_net_actions'])

        stmt = """
            SELECT count(distinct(action_name)) as total_unique_privesc_actions 
            FROM step
            WHERE training_id=%s AND prev_game_type =%s 
        """
        results = self.staging_connection.query(stmt, (self.training_id, "PRIVESC"))
        total_unique_privesc_actions = int(results[0]['total_unique_privesc_actions'])

        # CHECK HOW MANY STRAIGHT STEPS WE HAD AS A MAX IN PRIVESC
        stmt = """
            SELECT agent_id, game_id, step_id, action_name
            FROM step 
            WHERE prev_game_type='PRIVESC' AND next_game_type='PRIVESC' AND training_id =%s
            ORDER BY agent_id,game_id,step_id ASC;
        """
        results = self.staging_connection.query(stmt, (self.training_id,))

        agents_steps_map       = {}
        old_agent_key          = ""
        step_key               = ""
        total_steps_count      = 0
        longest_privesc_streak = 0
        longest_agent          = 0
        for res in results:
            agent_key = f"{res['agent_id']-res['game_id']}"
            if old_agent_key != agent_key:
                step_key = res['step_id']
                
            agent_map_key = f"{agent_key}-{step_key}"
            if agent_map_key not in agents_steps_map:
                agents_steps_map[agent_map_key] = 0

            agents_steps_map[agent_map_key] += 1 # TODO: THIS WOULD COUNT DUPLICATED ACTIONS
            if agents_steps_map[agent_map_key] > longest_privesc_streak:
                longest_privesc_streak = agents_steps_map[agent_map_key]
                longest_agent          = res['agent_id']
            
            total_steps_count += 1

        total_agents_count = len(agents_steps_map)
        # Log.logger.debug(results)
        # Log.logger.debug(agents_steps_map)
        # Log.logger.debug([total_steps_count, total_agents_count])

        privesc_streak_avg = 0
        if total_agents_count > 0:
            privesc_streak_avg = total_steps_count / total_agents_count

        return total_steps, total_steps_in_minute, total_steps_with_reward, total_steps_for_network, total_steps_for_privesc, \
                total_steps_breaking_session, total_agents_with_session, total_unique_net_actions, total_unique_privesc_actions, \
                     longest_privesc_streak, longest_agent, privesc_streak_avg, total_agents_running

