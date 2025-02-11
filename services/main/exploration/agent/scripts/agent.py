# python drako.py --log-level=0 --playbook=hackerone/lame.script

import argparse
import time
import traceback
import os

from lib.Common.Exploration.Metasploit import Metasploit
from lib.Common.Exploration.Metasploit.MetasploitStorage import MetasploitStorage

import lib.Exploration.Agent.Console.Console    as Console
import lib.Common.Utils.Constants               as Constants
import lib.Common.Utils.Log as Log
import lib.Common.Exploration.Actions as Actions
import lib.Common.Utils as Utils

from lib.Exploration.Agent.Agents                   import GoExploreAgent, NNRecommendationTesterAgent
from lib.Exploration.Agent.Dummy                    import DummyAgent
from lib.Common.Exploration.Environment.Environment import NetworkEnvironment, DreamatoriumEnvironment
from lib.Exploration.Agent.Console.Parser import Parser
from lib.Common.Exploration.Environment.Observation import ProcessedObservation

import logging

from lib.Common.Recommendation.PredictionRequest import request_agent_options

logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

argparser = argparse.ArgumentParser(description='Use the Agent from command line')
argparser.add_argument('--runner',    dest='runner', default="cli", help='specify the runner for the Agent', choices=("cli", "playbook", "agent", "replay"))
argparser.add_argument('--log-level', dest='log_level', default=0, help='specify the log level', choices=("0", "1", "2", "3"))

# AGENT ARGS
argparser.add_argument('--agent',              dest='agent',                                     help='agent to use')
argparser.add_argument('--environment',        dest='environment',                               help='specify the environment network or dreamatorium')
argparser.add_argument('--steps',              dest='steps', default=100, type=int,              help='how many steps the episode lasts')
argparser.add_argument('--playbook',           dest='playbook',           type=str,              help='specify the playbook path')
argparser.add_argument('--target',             dest='target',             type=str,              help='target for agent')
argparser.add_argument('--mode',               dest='mode',               type=str,              help='mode for agent')
argparser.add_argument('--regenerate_actions', dest='regenerate_actions', type=Utils.str2bool,   help='mode for agent', default=False)
argparser.add_argument('--training_id',        dest='training_id',        type=int,              help='optional training id to use')
argparser.add_argument('--episode_id',         dest='episode_id',         type=int,              help='episode_id to replay')

def get_container_id():
    container_id = os.getenv('CONTAINER_ID')
    if container_id is None:
        return None
    return container_id

def decide_action(agent, parser, game_type):
    # select action
    if args.runner == "cli":
        action_recommendation = parser.get_next_action_from_cli()
    elif args.runner == "playbook":
        action_recommendation = parser.get_next_action_from_playbook()
    elif args.runner == "agent":
        action_recommendation = agent.get_next_action_from_agent()
        Console.print_to_console(
            "[+] [%s ]Agent wants to execute action %s with options:\n%s" % (game_type, action_recommendation.action_name, action_recommendation.action_options),
            "normal")
    else:
        raise Exception("Unknown runner")

    return action_recommendation

def execute_action(action_recommendation, environment):
    action_name    = action_recommendation.action_name
    action_options = action_recommendation.action_options
    action_type    = action_recommendation.action_type
    action_data    = action_recommendation.action_data

    # perform action and get reward
    Log.logger.debug("Looking for action %s with options %s" % (action_name, action_options))

    if action_data is None:
        action_func = Actions.client.get_action(environment.get_current_game_type(), action_name)  # agent.get_action(action_name)
    else:
        # Log.logger.debug("Creating a metasploit action with: %s" % [action_name, action_type, action_data])
        # Log.logger.debug("Creating a metasploit action with: %s" % [action_name, action_type])
        action_func = Actions.Metasploit.create_metasploit_action(environment, action_name, action_type, action_data)

    time_start = time.time()
    if action_func is not None:
        try:
            processed_observation = action_func.execute(action_options)
        except:
            error_message = "Error executing action %s: %s" % (action_name, traceback.format_exc())
            # Log.logger.error(error_message)
            time_taken = time.time() - time_start
            processed_observation = ProcessedObservation("", "", time_taken, None, error_message)
    else:
        time_taken = time.time() - time_start
        processed_observation = ProcessedObservation("", "", time_taken, None, "No action found: %s" % action_name)

    # Log.logger.debug("processed_observation.description: %s" % processed_observation.description)

    return processed_observation

def print_observation(processed_observation):
    action_output = processed_observation.description
    message_type  = "normal"

    if processed_observation.observed_error is not None:
        message_type = "error"
        Console.print_to_console("[-] Error observed: %s" % processed_observation.observed_error, message_type)
    elif processed_observation.conditions_is_debug is True:
        Console.print_to_console(action_output, message_type)
    elif action_output == "" and processed_observation.observed_error is None:
        Console.print_to_console("[-] No response available", message_type)
    else:
        Console.print_to_console("[+] Response is:\n%s" % action_output, message_type)

def run_step(agent, environment, parser):
    step_id    = environment.step_id
    time_start = time.time()

    # 0)
    # We stop any jobs that might be running ensuring the environment is clean
    environment.metasploit_client.terminate_running_jobs_for_workspace()

    # 1) 
    # Agent should check and decide what game we it is playing
    # This is the case since they might decide differently when to continue on a game or not

    game_type = environment.get_current_game_type()
    Log.logger.debug("Starting step: %d for game %s" % (step_id, game_type))


    # 2)
    # Decide based on the agent and the environment what should it do
    action_recommendation = decide_action(agent, parser, game_type)

    # 2.5)
    # Update the target IP
    _, training_target_ip = agent.get_target()
    # TODO REMOVE NEXT LINE
    # Log.logger.debug(f'Got target ip {training_target_ip} to update in the environment')
    environment.set_target_ip(training_target_ip)

    # 3)
    # Execute the action
    environment.set_container_waiting()
    if len(action_recommendation.action_options_errors.keys()) > 0:
        time_taken            = time.time() - time_start
        error_message         = "Error setting the following information: %s" % action_recommendation.action_options_errors
        processed_observation = ProcessedObservation(action_recommendation.action_name, error_message, time_taken, None)
    else:
        processed_observation = execute_action(action_recommendation, environment)
    print_observation(processed_observation)

    # 4) 
    # Review the observation and get the reward of the environment
    reward, reward_reasons = environment.decide_reward(action_recommendation, processed_observation)

    # # 5) 
    # # Add the reward 
    # agent.add_reward(action_name, action_options, processed_observation, reward)

    summary_str = "[#] Finished step: %d. Action performed: %s. Reward received: %d. Reward reason:%s. Total accumulated reward: %d."
    summary_str += "\nEnvironment state is: %s"
    Log.logger.info(summary_str % (
        step_id, action_recommendation.action_name, reward, reward_reasons, environment.agent_episode_points, environment.get_state_pretty()))
    environment.set_container_not_waiting()

    # NOW CHECK IF THERE WAS AN ERROR

    if processed_observation.observed_error is not None:
        agent.handle_error(processed_observation)

def check_if_agents_enabled_for_init():
    # agent_options      = load_agent_options(connection, attributes=["STOP_AGENTS_INIT"])
    agent_options    = request_agent_options()
    stop_agents_init = agent_options['STOP_AGENTS_INIT']

    if stop_agents_init:
        return False
    else:

        return True

def run_agent( args):
    agent_options = {}
    if args.target is not None:
        agent_options["target"] = args.target

    if args.runner == "agent":
        agents_enabled = False
        while not agents_enabled:
            agents_enabled = check_if_agents_enabled_for_init() # We don't have an agent yet so we need to do it manually here
            if agents_enabled:
                break
            else:
                Log.logger.warning("Agents are not enabled for init, will wait for 30 seconds and check again")
                time.sleep(30)

    # INITIALIZE EPISODE
    if args.environment is None or args.environment == "network":
        environment = NetworkEnvironment(args.steps, args.runner, args.agent, args.target, args.training_id)
    elif args.environment == "dreamatorium":
        raise NotImplementedError("This has been disabled!")
        # environment = DreamatoriumEnvironment(args.steps, args.runner, args.agent, args.target, args.training_id)
    else:
        raise ValueError("Unknown environment %s" % args.environment)

    # SET ENVIRONMENT INFORMATIONS
    metasploit_client = Metasploit(environment)
    environment.set_metasploit_client(metasploit_client)

    # AGENTS DEPEND ON ACTIONS BEING INITIALIZED
    # INITIALIZE AGENT
    if args.runner == "agent":
        # For agents we avoid loading metasploit actions to save up RAM
        Actions.initialize(environment)

        if args.training_id is None:
            raise ValueError("You need to set a training_id to use an agent")

        if args.agent == "GoExplore":
            agent = GoExploreAgent(environment)
        elif args.agent == "NNRecommendationTester":
            agent = NNRecommendationTesterAgent(environment)
        else:
            raise ValueError("Unknown agent type: %s" % args.agent)
    else:
        Actions.initialize(environment)
        Actions.client.load_metasploit_actions(metasploit_client)
        agent = DummyAgent(environment, agent_options)

    # SET THE AGENT ON THE ENVIRONMENT TO DETERMINE GAME_TYPE
    environment.set_agent(agent)

    error_message = ""
    parser = Parser(agent, environment, agent_options, args.playbook, args.episode_id)
    try:
        if environment.inside_a_container():
            Log.logger.debug("We are inside a container with id %s" % environment.get_container_id())

        is_finished, reason = environment.is_finished()
        while not is_finished:
            Log.logger.debug("=" * 100)

            # update agent options before startin step
            agent.update_agent_options()
            run_step(agent, environment, parser)

            if parser.closed():
                Log.logger.info("Ending episode since parser is closed")
                break

            is_finished, reason = environment.is_finished()
            if is_finished:
                Log.logger.info("Ending episode due to %s", reason)
                break

            # Here we check if we should pause after we finished the step
            while True:
                should_we_run_step = agent.should_we_run_step()
                if not should_we_run_step:
                    Log.logger.debug("Agent is paused, we will wait for 30 seconds..")
                    time.sleep(30)
                else:
                    Log.logger.debug("We can continue running the agent!")
                    break

            # Check if we should finish the episode
            finish_episode, finish_reason = agent.should_we_finish_episode()
            Log.logger.debug("Result of finish episode is: %s" % finish_episode)
            if finish_episode:
                environment.finish_episode(finish_reason)
                break
            else:
                environment.finish_step()

            Log.logger.debug("=" * 100)

            Log.logger.debug("Finished step")

        Log.logger.debug("Environment finished with reason %s, exiting this agent iteration!", reason)
    except:
        error_message = "[-] ERROR: %s. Will end iteration." % traceback.format_exc()
        # Log.logger.error(error_message)
        Console.print_to_console(error_message, "error")

    # CLOSE EPISODE
    Log.logger.debug("Will now close the episode")
    environment.close(error_message)

    # CLOSE ACTIONS AND METASPLOIT
    metasploit_client.clean_active_sessions()

    Console.print_to_console("[+] Finishing running agent")

def main(args):
    # INITIALIZE
    log_filename = None
    container_id = get_container_id()
    if container_id and args.training_id:
        log_filename = f"{Constants.LOGS_FOLDER_PATH}/{args.training_id}/{container_id[:10]}.log"

    Log.initialize_log(args.log_level, log_filename)
    Log.add_info_large_ascii("Agent")
    Log.logger.info("Starting with log level: %s" % args.log_level)

    # connection = Db(db_host=Constants.DRAGON_STAGING_DB_IP, db_name=Constants.DRAGON_STAGING_DB_NAME, db_password=Constants.DRAGON_DB_PWD)

    # When action regeneration is required we regenerate the actions and exit
    if args.regenerate_actions:
        environment = NetworkEnvironment(args.steps, args.runner, args.agent, args.target, args.training_id)

        metasploit_client  = Metasploit(environment)
        metasploit_storage = MetasploitStorage(environment, metasploit_client=metasploit_client.client)
        metasploit_storage.regenerate_actions()
        environment.close("regenerate_actions")
    else:
        run_agent(args)

if __name__ == '__main__':
    # SETTING UP LOGGER
    args = argparser.parse_args()
    main(args)
