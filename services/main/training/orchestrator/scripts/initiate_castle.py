# python drako.py --log-level=0 --script-name=script.txt
import argparse
import os
import time
import docker
import traceback

import sys
sys.path.append("/root/drako/services/main/")
import lib.Common.Utils.Constants as Constants

from lib.Common.Utils    import str2bool
from lib.Common.Utils.Db import Db
import lib.Common.Utils.Log as Log

from lib.Training.Trainer.Common import execute_command, walk_and_clean_directory, wait_for_game_training_to_be_ready

argparser = argparse.ArgumentParser(description='Use Trainer from command line')
argparser.add_argument('-s', '--amount_of_agents',           dest='amount_of_agents', default=1,                   required=0, type=int,       help='number of agents to spawn')
argparser.add_argument('-i', '--training_id',                dest='training_id',                                   required=1, type=int,       help='force a training id instead of creating one')
argparser.add_argument('-b', '--build_mode',                 dest='build_mode',       default="build_all_and_run", required=0, type=str,       help='force a training id instead of creating one', choices=("build_all_and_run","build_and_run"))
argparser.add_argument('-o', '--only_agents',                dest='only_agents',      default=False,               required=0, type=str2bool,  help='whether to only focus on building agents, used for debugging' )
argparser.add_argument('-p', '--profile',                    dest='profile',                                       required=1, type=str,       help='profile for script',  choices=('EXPLORE', 'TRAIN', 'EXPLORE_AND_TRAIN', "BENCHMARK"))
argparser.add_argument('-a', '--agent_name',                 dest='agent_name',                                    required=1, type=str,       help='name for the agent',  )
argparser.add_argument('-t', '--tester_name',                dest='tester_name',                                   required=1, type=str,       help='name for the tester', )
argparser.add_argument('-q', '--clean_up_containers',        dest='clean_up_containers', default=True,             required=0, type=str2bool,  help='create prediction and learners',)
argparser.add_argument('-y', '--timeout',                    dest='timeout',             default=10800,            required=0, type=int,       help='define how long the agents live',)

# LOCAL TRAINING SETTINGS
argparser.add_argument('-l', '--learner_name',               dest='learner_name',                                  required=0, type=str,   help='name for the learner', )
argparser.add_argument('-m', '--load_main_training',         dest='load_main_training',                            required=0, type=str2bool,  help='load_main_training', )
argparser.add_argument('-c', '--continue_from_latest_point', dest='continue_from_latest_point',                    required=0, type=str2bool,  help='continue_from_latest_point', )
argparser.add_argument('-u', '--force_cpu',                  dest='force_cpu',                                     required=0, type=str2bool,  help='force_cpu', )
argparser.add_argument('-g', '--target_source',              dest='target_source',                                 required=1, type=str,       help='target_source', )

# Too many in parallel might compromise the cpu of the box
argparser.add_argument('-n', '--parallel',              dest='parallel_amount',  default=15, required=0, type=int,  help='amount of containers to start in parallel' )

client = docker.from_env(timeout=300)
steps_per_episode = 200

import logging
logging.getLogger('requests').setLevel(logging.CRITICAL)
logging.getLogger('docker').setLevel(logging.CRITICAL)
logging.getLogger('s3transfer').setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.WARNING)

def get_castle_name():
    castle_name = os.getenv('CASTLE_NAME')
    if castle_name is not None:
        return castle_name
    else:
        return ""

class PortAssigner:
    def __init__(self, start_port, end_port):
        self.start_port   = start_port
        self.current_port = start_port
        self.end_port     = end_port

    def get_new_ports(self):
        apache_port      = self.current_port
        srv_port         = self.current_port + 1
        rev_shell_port   = self.current_port + 2
        rev_shell_port_2 = self.current_port + 3

        if self.current_port + 4 > self.end_port:
            self.current_port = self.start_port
        else:
            self.current_port += 4 # one per port

        return apache_port, srv_port, rev_shell_port, rev_shell_port_2

def get_running_containers_map():
    containers_map = {}
    containers = client.containers.list()
    for container in containers:
        if container.attrs['State']['Running']:
            containers_map[container.id] = container

    return containers_map

def update_agents_table(connection):
    running_containers_map = get_running_containers_map()
    Log.logger.debug(running_containers_map)
    # Get all running agents and check agains the local docker api if they are running
    results = connection.query("SELECT container_id, running FROM agent")
    for result in results:
        container_id = result['container_id']
        running      = result['running']
        # Log.logger.debug("Checking if container %s is still running" % container_id)
        if running == 1 and container_id not in running_containers_map:
            connection.execute("UPDATE agent SET running=0, waiting=0, has_session=0 WHERE container_id=%s", (container_id, ))
            Log.logger.debug("Setting agent %s as not running anymore!" % container_id)
        elif running == 0 and container_id in running_containers_map:
            connection.execute("UPDATE agent SET running=0 WHERE container_id=%s", (container_id, ))
            Log.logger.debug(f"Setting agent {container_id} as running since we found it running and we had it as not running!")

def cleanup_shared_folders(training_id):
    # if os.path.exists(f"{Constants.LOGS_FOLDER_PATH}/{training_id}"):
    #     execute_command(f"rm {Constants.LOGS_FOLDER_PATH}/{training_id}/*", ignore_errors=True)
    # else:
    print("Going through each folder and cleaning it")
    walk_and_clean_directory(Constants.LOGS_FOLDER_PATH)

    print("Going through each folder and cleaning it")
    walk_and_clean_directory(f"Constants.NETWORKS_FOLDER_PATH/{training_id}")

    print("Creating paths for training %s" % training_id)
    execute_command(f"mkdir -p {Constants.LOGS_FOLDER_PATH}/{training_id}")
    execute_command(f"mkdir -p {Constants.NETWORKS_FOLDER_PATH}/{training_id}")

# def kill_screens():
#     execute_command("pkill screen")

# This need to be synced with Setup.py
def create_training_prediction_api(training_id, force_cpu):
    # Ram limited to 8g since leaks could make parrot unstable
    execute_command(f'docker build -t training_prediction -f {Constants.PREDICTION_FOLDER_PATH}/Dockerfile.training_prediction {Constants.MAIN_SERVICE_PATH}')
    # removed -memory="8g" since it might not be needed
    if not force_cpu:
        execute_command(f'docker run -d --name training_prediction --gpus all -v /share:/share --network host -e "TRAINING_ID={training_id}" -e"FORCE_CPU={force_cpu}" -e"CASTLE_NAME={get_castle_name()}" -t training_prediction')
    else:
        execute_command(f'docker run -d --name training_prediction -v /share:/share --network host -e "TRAINING_ID={training_id}" -e"FORCE_CPU={force_cpu}" -e"CASTLE_NAME={get_castle_name()}" -t training_prediction')

# This need to be synced with Setup.py
def create_and_start_learner(game_type, learner_name, training_id, load_main_training, profile, continue_from_latest_point, force_cpu):
    Log.logger.info("Starting now %s learner container.." % game_type)

    execute_command(f'docker build -t learner -f {Constants.LEARNER_FOLDER_PATH}/Dockerfile.learner {Constants.MAIN_SERVICE_PATH}')

    if not force_cpu:
        learner_command =  f'docker run -d --name {game_type}_learner --gpus all -v /share:/share --network host '
    else:
        learner_command = f'docker run -d --name {game_type}_learner -v /share:/share --network host '

    learner_command += f'-e "GAME_TYPE={game_type}" -e "LEARNER_NAME={learner_name}"  -e "TRAINING_ID={training_id}" -e"CASTLE_NAME={get_castle_name()}" '
    learner_command += f'-e "LOAD_MAIN_TRAINING={load_main_training}" -e "PROFILE={profile}" -e "CONTINUE={continue_from_latest_point}" -e"FORCE_CPU={force_cpu}" -t learner'
    execute_command(learner_command)

def stop_all_containers():
    stop_learner_containers()
    stop_agent_containers()
    stop_prediction_containers()

def stop_agent_containers():
    Log.logger.info("Stopping agent containers...")
    execute_command("docker stop $(docker ps -aq --filter name=\"agent-\")", ignore_errors=True)
    execute_command("docker container rm $(docker container ls -aq --filter name=\"agent-\")", ignore_errors=True)

def stop_learner_containers():
    Log.logger.info("Stopping learner containers...")
    execute_command("docker stop $(docker ps -aq --filter name=\"_learner\")", ignore_errors=True)
    execute_command("docker container rm $(docker container ls -aq --filter name=\"_learner\")", ignore_errors=True)

def stop_prediction_containers():
    Log.logger.info("Stopping prediction containers...")
    execute_command("docker stop $(docker ps -aq --filter name=\"prediction\")", ignore_errors=True)
    execute_command("docker container rm $(docker container ls -aq --filter name=\"prediction\")", ignore_errors=True)

def restart_docker():
    execute_command("service docker restart") # to avoid already exists in network host

def remove_stopped_containers():
    Log.logger.info("Removing stopped containers..")
    execute_command("docker container rm $(docker container ls -aq --filter name=\"agent-\" --filter status=exited --filter status=created) 2>/dev/null", ignore_errors=True)

def build_agent_containers(build_mode):
    Log.logger.info("Building agent containers")
    if build_mode == "build_all_and_run":
        execute_command(f"docker build -f {Constants.AGENT_BASE_PATH}/Dockerfile.agent.base -t agent-base {Constants.SERVICES_PATH}")
        execute_command(f"docker build -f {Constants.AGENT_FOLDER_PATH}/Dockerfile.agent -t agent {Constants.MAIN_SERVICE_PATH}")
    elif build_mode == "build_and_run":
        execute_command(f"docker build -f {Constants.AGENT_FOLDER_PATH}/Dockerfile.agent -t agent {Constants.MAIN_SERVICE_PATH}")
    else:
        raise ValueError("Unknown build mode %s" % build_mode)

def get_local_ip(target_source):
    Log.logger.info("Lets retrieve the VPN ip address")

    interface = "enp6s0"
    if target_source == Constants.VM_SOURCE_HACKTHEBOX:
        interface = "tun0"

    local_ip_address = execute_command("ifconfig " + interface + "|grep 'inet'|awk '{print $2}'|head -n1")
    if target_source == Constants.VM_SOURCE_HACKTHEBOX and not local_ip_address.startswith("10."):
        raise ValueError("I was unable to get a VPN address, will stop!")
    else:
        return local_ip_address

def get_amount_of_containers_running():
    training_containers, tester_containers = ([], [])
    containers = client.containers.list()
    for container in containers:
        if container.name.startswith("agent-training"):
            training_containers.append(container)
        elif container.name.startswith("agent-tester"):
            tester_containers.append(container)

    return training_containers, tester_containers

def start_agents(connection, build_mode, agent_name, tester_name, amount_of_agents, training_id, parallel_amount, timeout, profile, clean_up_containers, target_source):
    build_agent_containers(build_mode)

    local_ip_address = get_local_ip(target_source)
    Log.logger.debug("Got local ip address: %s" % local_ip_address)

    if target_source == Constants.VM_SOURCE_HACKTHEBOX:
        # Set limits to VPN
        start_wondershaper()
        Log.logger.debug("Lets check the tun0 is limited properly")
        execute_command('wondershaper tun0')

    training_counter = tester_counter = 0
    if agent_name in ["GoExplore"]:
        port_assigner = PortAssigner(10000, 50000)
        while True:
            try:
                training_containers, tester_containers = get_amount_of_containers_running()

                # To then update the agents table
                container_added = False

                if profile != "EXPLORE":
                    if tester_name.lower() == "none":
                        Log.logger.debug(f"No need to start a tester when its name is {tester_name}")
                    # Check for spawning tester agents
                    elif len(tester_containers) == 0:
                        Log.logger.info("I need to create a new tester agent")
                        tester_counter += 1
                        container_name = f'agent-tester-{tester_name.lower()}-{tester_counter}'
                        start_agent(container_name, tester_name, port_assigner, local_ip_address, training_id, timeout)
                        container_added = True
                else:
                    Log.logger.debug(f"Not starting tester when profile is {profile}")

                # Check for spawning training agents
                training_containers_to_add = amount_of_agents - len(training_containers)
                if training_containers_to_add > 0:
                    Log.logger.info("I need to create %d new training agents" % training_containers_to_add)

                    for _ in range(training_containers_to_add):
                        training_counter += 1
                        container_name = f'agent-training-{agent_name.lower()}-{training_counter}'

                        start_in_background = True
                        if training_counter % parallel_amount == 0: # Every parallel amount we wait for container to finish
                            start_in_background = False

                        start_agent(container_name, agent_name, port_assigner, local_ip_address, training_id, timeout, start_in_background=start_in_background)
                        time.sleep(0.5)
                    container_added = True

                if container_added:
                    update_agents_table(connection)
            except:
                Log.logger.error("ERROR => %s" % traceback.format_exc())

            if clean_up_containers:
                remove_stopped_containers()
            Log.logger.debug("Sleeping for 60 seconds..")
            time.sleep(60)
    else:
        raise NotImplementedError(f"Agent {agent_name} is not implemented")

def start_agent(container_name, agent_name, port_assigner, local_ip_address, training_id, timeout, start_in_background=False):
    apache_port, srv_port, rev_shell_port, rev_shell_port_2 = port_assigner.get_new_ports()

    debug_level = 2

    # --cap-add NET_ADMIN WAS needed to avoid errors such as SIOCSIFFLAGS: Operation not permitted, but it might be breaking the networking for the host machine
    start_command = f'docker run -d --name {container_name} -v /share:/share --cpus 1'
    variables = f'-e"CASTLE_NAME={get_castle_name()}" -e "CONTAINER_NAME={container_name}" -e "PREDICTION_API_IP={local_ip_address}" -e "LOCAL_IP={local_ip_address}" -e "APACHE_PORT={apache_port}" -e "SRV_PORT={srv_port}" -e "REVSHELL_PORT={rev_shell_port}" -e "REVSHELL_PORT_2={rev_shell_port_2}"'
    ports_assignment = f'-p {local_ip_address}:{apache_port}:{apache_port}/tcp -p {local_ip_address}:{srv_port}:{srv_port}/tcp  -p {local_ip_address}:{rev_shell_port}:{rev_shell_port}/tcp -p {local_ip_address}:{rev_shell_port_2}:{rev_shell_port_2}/tcp'
    image_and_command = f'-it agent /app/init.sh -r agent -a {agent_name} -d{debug_level} -s{steps_per_episode} -t {training_id} -y {timeout}'

    full_command = f'{start_command} {variables} {ports_assignment} {image_and_command}'

    if start_in_background:
        full_command += " &"  # start it as a job
    # Log.logger.info("Will run command: %s" % full_command)
    execute_command(full_command, ignore_errors=True)

def start_openvpn():
    execute_command('pkill openvpn', ignore_errors=True)
    execute_command('screen -S openvpn -X quit', ignore_errors=True)
    Log.logger.debug("Starting openvpn..")
    execute_command('screen -S openvpn -d -m')
    execute_command(f"screen -r openvpn -X stuff 'openvpn {Constants.DRAKO_FOLDER_PATH}/labs/hackthebox/nearraen.ovpn\n'")

def start_wondershaper():
    Log.logger.debug("Setting limits to openvpn and the eno1 to 1mb..")
    execute_command('wondershaper tun0 1024 1024')
    try:
        execute_command('wondershaper eno1 2048 2048')
    except:
        Log.logger.warning("Not running wondershaper, this should only happen in AWS") # For AWS

def main():
    args = argparser.parse_args()

    staging_connection = Db(db_host=Constants.DRAGON_STAGING_DB_IP, db_name=Constants.get_dragon_staging_db(), db_password=Constants.DRAGON_DB_PWD)

    cleanup_shared_folders(args.training_id)

    Log.initialize_log("2", f"{Constants.LOGS_FOLDER_PATH}/{args.training_id}/initiate_castle.log")
    Log.logger.info("Starting to initiate castle..")

    if args.target_source == Constants.VM_SOURCE_HACKTHEBOX:
        Log.logger.debug("First start openvpn")
        start_openvpn()

        if not args.only_agents: #Maybe we have it twice to cover the gaps of time?\
            Log.logger.info("Sleeping 10 seconds to get the VPN ip address available")
            time.sleep(10)

    Log.logger.info("Stopping ALL containers")
    stop_all_containers()
    restart_docker()

    # PREDICTION NEEDS TO BE BUILT FIRST SINCE TRAINERS CALL IT TO GET READY
    create_training_prediction_api(args.training_id, args.force_cpu)

    Log.logger.debug("Then go on building trainers")

    Log.logger.info("Now we need to wait until both games are ready...")
    create_and_start_learner("NETWORK", args.learner_name, args.training_id, args.load_main_training, args.profile, args.continue_from_latest_point, args.force_cpu)
    create_and_start_learner("PRIVESC", args.learner_name, args.training_id, args.load_main_training, args.profile, args.continue_from_latest_point, args.force_cpu)

    wait_for_game_training_to_be_ready(staging_connection, args.training_id, "NETWORK")
    wait_for_game_training_to_be_ready(staging_connection, args.training_id, "PRIVESC")

    start_agents(staging_connection, args.build_mode, args.agent_name, args.tester_name, args.amount_of_agents, args.training_id, args.parallel_amount, args.timeout, args.profile, args.clean_up_containers, args.target_source)

    staging_connection.close()

main()
