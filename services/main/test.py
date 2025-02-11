# Since each app requires its own environment,
# in special the agent which needs to run metasploit,
# we need each docker container to run its own tests,
# so the test scripts starts and builds each docker container,
# then runs tests on its own module and on the common module
# an exception is orchestrator that does not use containers

import argparse
import re
import os
os.system("clear")

from lib.Training.Trainer.Common import execute_command

import lib.Common.Utils.Log as Log
import lib.Common.Utils.Constants as Constants

argparser = argparse.ArgumentParser(description='Use the Agent from command line')
argparser.add_argument('--service', dest='service', help='Name of the service to test')
args = argparser.parse_args()

test_results = {}

def can_test_service(service):
    if args.service is None or service == args.service:
        return True
    else:
        return False

def test_orchestrator_module(module):
    if can_test_service("Orchestrator"):
        Log.logger.info(f"Will test module {module} of orchestrator")
        response = execute_command("python3 -m unittest discover -v lib.Training.Trainer", ignore_errors=True)

        test_results["Training"] = {
            "orchestrator": f"{module}:\n{response}"
        }
    else:
        Log.logger.info("Skipping testing Orchestrator}")

def test_module(pillar, image_name, dockerfile_path, module):
    if can_test_service(image_name):
        Log.logger.info(f"Will test module {module} of image {image_name}")
        Log.logger.debug(f"Building {image_name} container..")
        container_name = f"{image_name}_tester"
        execute_command(f"docker build -t {image_name} -f {dockerfile_path}/Dockerfile.{image_name} {Constants.MAIN_SERVICE_PATH}")
        execute_command(f"docker rm -f $(docker container ls -a -q --filter name={container_name}) 2>/dev/null", ignore_errors=True)

        Log.logger.debug(f"Running tests for {image_name}")

        if image_name == "agent":
            test_command = f"/app/init.sh -r test -m {module}"
        else:
            test_command = f"python3 -m unittest discover {module}"

        if image_name == "web": # web needs to talk to the prediction api
            response = execute_command(f"docker run --network host --name {container_name} -v /share:/share -t {image_name} {test_command}", ignore_errors=True)
        else:
            response = execute_command(f"docker run --name {container_name} -v /share:/share -t {image_name} {test_command}", ignore_errors=True)

        if pillar not in test_results:
            test_results[pillar] = {}
        if image_name not in test_results[pillar]:
            test_results[pillar][image_name] = ""

        test_results[pillar][image_name] += f"{module}:\n{response}\n"
    else:
        Log.logger.info("Skipping testing {image_name}")

def build_base_agent():
    if can_test_service("agent"):
        Log.logger.debug(f"Building base_agent container..")
        execute_command(f"docker build -f {Constants.AGENT_BASE_PATH}/Dockerfile.agent.base -t agent-base {Constants.AGENT_BASE_PATH}")
    else:
        Log.logger.info("Skipping building base agent")

Log.initialize_log("2", filename=f"{Constants.LOGS_FOLDER_PATH}/tests.log")

Log.add_debug_large_ascii("Training")
# ORCHESTRATOR IS SPECIAL, IT RUNS ON PARROT SO NO CONTAINER TO TEST
Log.add_debug_medium_ascii("Orchestrator")
test_orchestrator_module("lib.Training.Trainer")

Log.add_debug_medium_ascii("Learner")
test_module(pillar="Training", image_name="learner", dockerfile_path=Constants.LEARNER_FOLDER_PATH, module="lib.Training.Learner")
test_module(pillar="Training", image_name="learner", dockerfile_path=Constants.LEARNER_FOLDER_PATH, module="lib.Common.Training")

Log.add_debug_large_ascii("Recommendation")
Log.add_debug_medium_ascii("Prediction")
test_module(pillar="Recommendation", image_name="training_prediction", dockerfile_path=Constants.PREDICTION_FOLDER_PATH, module="lib.Recommendation.Prediction")
test_module(pillar="Recommendation", image_name="training_prediction", dockerfile_path=Constants.PREDICTION_FOLDER_PATH, module="lib.Common.Recommendation")

Log.add_debug_large_ascii("Presentation")
Log.add_debug_medium_ascii("Graph")
test_module(pillar="Presentation", image_name="visualizer", dockerfile_path=Constants.VISUALIZER_FOLDER_PATH, module="lib.Presentation.Visualizer")
test_module(pillar="Presentation", image_name="visualizer", dockerfile_path=Constants.VISUALIZER_FOLDER_PATH, module="lib.Common.Presentation")

Log.add_debug_medium_ascii("Web")
test_module(pillar="Presentation", image_name="web", dockerfile_path=Constants.WEB_FOLDER_PATH, module="lib.Presentation.Web")

Log.add_debug_large_ascii("Exploration")
Log.add_debug_medium_ascii("Agent")
build_base_agent()
test_module(pillar="Exploration", image_name="agent", dockerfile_path=Constants.AGENT_FOLDER_PATH, module="lib.Exploration.Agent")
test_module(pillar="Exploration", image_name="agent", dockerfile_path=Constants.AGENT_FOLDER_PATH, module="lib.Common.Exploration")

## NOW WE CAN REVIEW TESTS RESULTS

Log.add_info_separator()
Log.add_info_large_ascii("Results")
Log.add_info_separator()

warnings = []
total, errors = 0, 0
for pillar in test_results:
    for image_name in test_results[pillar]:
        image_result = test_results[pillar][image_name]
        Log.add_info_medium_ascii(image_name)
        Log.logger.info(image_result)

        groups = re.findall(r'Ran (\d+) tests', image_result)
        for amount in groups:
            total        += int(amount)

        if "FAILED (" in image_result:
            errors += 1

        if len(groups) == 0:
            warnings.append(f"No tests were run for {image_name} please review!")

Log.add_info_medium_ascii("Summary")
Log.logger.info(f"Total errors found: {errors} out of {total}")

if len(warnings) > 0:
    Log.add_info_medium_ascii("WARNINGS")
    for warning in warnings:
        Log.logger.warning(warning)