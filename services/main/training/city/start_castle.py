import datetime
import time
from tkinter.tix import MAX
import traceback
import sys
import argparse
import uuid
import os

sys.path.append("/root/drako/services/main/")
from lib.Training.Trainer.Request import request_to_manager
from lib.Exploration.Agent.Utils  import load_agent_options
from lib.Training.Manager.Virsh   import VIRSH

import lib.Common.Utils.Log as Log
from lib.Training.Trainer.Common import create_new_orchestrator, create_new_training, execute_command, cleanup_db, generate_castle_db_name, generate_castle_name
from lib.Common.Utils.Constants  import CITY_FOLDER_PATH, ORCHESTRATOR_SCRIPTS_PATH, VM_SOURCE_GENERAL, VM_SOURCE_HACKTHEBOX
from lib.Common.Utils            import str2bool
from lib.Common import Utils
from lib.Common.Utils.Db import Db
from lib.Common.Utils import Constants

argparser = argparse.ArgumentParser(description='Use Start Castle from command line')
argparser.add_argument('--amount_of_agents', dest='amount_of_agents',   required=True,   type=int,      help='number of agents to spawn')
argparser.add_argument('--log_level',        dest='log_level',       default="2", help='specify the log level', choices=("0", "1", "2", "3"))
argparser.add_argument('--target_source',    dest='target_source', required=True, type=str, help='specify the target source', choices=(VM_SOURCE_HACKTHEBOX, VM_SOURCE_GENERAL))
argparser.add_argument('--target_name',      dest='target_name', type=str, help='specify the target name')
argparser.add_argument('--iterate',          dest='iterate', default=False, type=str, help='iterate over targets')
argparser.add_argument('--hours_per_target', dest='hours_per_target',      type=int,  required=True,    help='how many hours to spend in each target')
argparser.add_argument('--learner_family',   dest='learner_family',        type=str,      help='specify the learner family for Drako', default="dqn",        choices=("dqn",))
argparser.add_argument('--learner_name',     dest='learner_name',          type=str,      help='specify the learner for Drako',        default="DQN",        choices=("PlannerDQN","PlannerPrioDQN","DQN","SimplePrioDQN"))
argparser.add_argument('--time_for_check',   dest='time_for_check',        type=int,      help='time_for_check',        default=10,       )
argparser.add_argument('--skip_until',       dest='skip_until',            type=str,      help='name of the machine to skip until',        required=False,   default=""    )

virsh = VIRSH(Constants.VIRSH_SOCKET_LOCATION_CITY)

def backup_vm(castle_name):
    Log.logger.info("Backing up contents")
    execute_command(f"/bin/bash {Constants.DRAKO_FOLDER_PATH}/scripts/city/extract_logs.sh {castle_name}")

def create_database(castle_db_name):
    command = f"mysql -P {Constants.DRAGON_DB_PORT} -h{Constants.DRAGON_STAGING_DB_IP} -u{Constants.DRAGON_DB_USER} -p{Constants.DRAGON_DB_PWD} "
    command += f"-e 'CREATE DATABASE IF NOT EXISTS {castle_db_name}'"
    execute_command(command)

def stop_manager():
    Log.logger.info("Stopping manager container...")
    execute_command("docker stop $(docker ps -aq --filter name=\"manager\")", ignore_errors=True)
    execute_command("docker container rm $(docker container ls -aq --filter name=\"manager\")", ignore_errors=True)

def start_manager():
    Log.logger.info("Starting manager..")
    execute_command(f'docker build -t manager -f {Constants.CITY_FOLDER_PATH}/Dockerfile.manager {Constants.MAIN_SERVICE_PATH}')
    execute_command(f'docker run --name manager -d -p 4000:4000 -v {Constants.VIRSH_IMAGE_FILE_LOCATION}/:{Constants.VIRSH_IMAGE_FILE_LOCATION}/ -v {Constants.VIRSH_CONFIG_FILE_LOCATION}/:{Constants.VIRSH_CONFIG_FILE_LOCATION}/ -v {Constants.VIRSH_SOCKET_LOCATION_CITY}:{Constants.VIRSH_SOCKET_LOCATION_DOCKER} -it -t manager', ignore_errors=True)

def create_orchestrator_id(staging_connection, castle_options):
    json_data = Utils.dump_json_pretty(castle_options)

    orchestrator_id = create_new_orchestrator(staging_connection, castle_options['target_source'], castle_options['castle_name'], json_data, castle_options['castle_uuid'])
    Log.logger.debug("Created a new orchestrator id entry: %d" % orchestrator_id)

    return orchestrator_id

def request_target_from_name(target_source, target_name):
    targets = get_targets(target_source)
    for target in targets:
        Log.logger.debug(target)
        if target['name'].lower() == target_name.lower():
            return target
    
    raise ValueError(f"I did not find a target by the name of {target_name} at source {target_source}")

def request_target_from_id(target_source, target_id):
    targets = get_targets(target_source)
    for target in targets:
        # Log.logger.debug(target)
        if target['id'] == target_id:
            return target
    
    raise ValueError(f"I did not find a target by the id of {target_id} at source {target_source}")

def generate_castle_options(args, target_name = None, target_id = None):
    if target_name is None:
        target_name = args.target_name

    if target_id is None:
        target    = request_target_from_name(args.target_source, target_name)
        target_id = target['id']
        Log.logger.debug(f"Retrieved target_id %d from target_name %s" % (target_id, target_name))
    else:
         target = request_target_from_id(args.target_source, target_id)

    castle_name = generate_castle_name(args.target_source, target_name)
    castle_options = {
        "castle_name":        castle_name,
        # Depending on the amount of agents specified, set the VM ram we will need
        "ram_needed_in_gb":   int( ( (args.amount_of_agents * 800) + 8000 ) / 1024 ),
        "cpus_needed":        max(int(args.amount_of_agents/100*16), 2),
        "castle_db_name":     generate_castle_db_name(castle_name),
        "amount_of_agents":   args.amount_of_agents,
        "castle_uuid":        str(uuid.uuid4()),
        "target_source":      args.target_source,
        "target_id":          target_id,
        "hours_per_target":   args.hours_per_target,
        "load_main_training": "False",
        "profile":            Constants.PROFILE_EXPLORE,
        "target_name":        target['name'],
        "learner_family":     args.learner_family,
        "learner_name":       args.learner_name,
    }

    return castle_options

def stop_build_and_start_manager():
    stop_manager()
    start_manager()

    Log.logger.debug("Sleeping 10 seconds for manager to boot up")
    time.sleep(10)

def setup_and_start_castle_vm(castle_options):
    Log.logger.info("We will be requesting %dGB of ram and %d cpus since we have %d agents" % (castle_options['ram_needed_in_gb'], castle_options['cpus_needed'], castle_options['amount_of_agents']))

    vm_ip_address = virsh.clone_start_and_sync_vm(castle_options['castle_name'], castle_options['ram_needed_in_gb'], castle_options['cpus_needed'])

    Log.logger.debug("We will set the ENV CASTLE_NAME AND CASTLE_UUID in the VM")
    virsh.execute_command_in_vm(vm_ip_address, "echo \"CASTLE_NAME=" + castle_options['castle_name'] + ";export CASTLE_NAME;CASTLE_UUID=" + castle_options['castle_uuid'] + ";export CASTLE_UUID;\" >> /root/.bashrc")

    return vm_ip_address

def start_orchestrator(castle_options, vm_ip_address, orchestrator_id, new_training_id):
    Log.logger.debug("Start orchestrator")
    profile              = castle_options["profile"]
    load_main_training   = castle_options['load_main_training']
    hours_per_target     = castle_options['hours_per_target']
    target_id            = castle_options['target_id']
    target_source        = castle_options['target_source']
    amount_of_agents     = castle_options['amount_of_agents']
    learner_family       = castle_options['learner_family']
    learner_name         = castle_options['learner_name']
    command = f"/bin/bash {ORCHESTRATOR_SCRIPTS_PATH}/initiate_orchestrator.sh {orchestrator_id} {profile} {amount_of_agents} {load_main_training} {hours_per_target} {target_source} {target_id} {new_training_id} {learner_family} {learner_name}"
    virsh.execute_command_in_vm(vm_ip_address, command)

def add_agent_options(connection, castle_options):
    stmt = """
        INSERT INTO agent_config(agent_config_id, attribute, value, attribute_type)
        VALUES(%s, %s, %s, %s)
    """
    connection.execute(stmt, (114, "TARGET_SOURCE", castle_options['target_source'], "STRING"))
    connection.execute(stmt, (115, "PROFILE",       castle_options['profile'],       "STRING"))

def delete_image(castle_name):
    image_location = f"{Constants.VIRSH_IMAGE_FILE_LOCATION}/{castle_name}.img"
    Log.logger.info(f"Deleting now the castle image at {image_location}")
    try:
        os.remove(image_location)
    except:
        Log.logger.warning(f"Error trying to delete image {traceback.format_exc()}")

def start_castle(castle_options, orchestrator_id, training_id):
    castle_name = castle_options['castle_name']
    Log.logger.info(f"Starting castle for {castle_name}")

    virsh.destroy_and_undefine_vm(castle_options['castle_name'])

    vm_ip_address = setup_and_start_castle_vm(castle_options)

    start_orchestrator(castle_options, vm_ip_address, orchestrator_id, training_id)

    Log.logger.info(f"Finished starting castle for {castle_name}")

def get_targets(target_source):
    data = {
        "target_source": target_source,
    }

    error = None
    MAX_ATTEMPTS = 5
    attemtps = 0
    while attemtps < MAX_ATTEMPTS:
        response, success = request_to_manager("get_targets", data)
        if 'success' not in response or not response['success'] or not success:
            error = f"Error requesting targets: {response}"
            Log.logger.error(error)
            attemtps += 1
        else:
            return response['targets']

    raise ValueError(error)

def destroy_vms(castle_options):
    Log.logger.debug(f"Destroying VMS for {castle_options['castle_name']}")
    virsh.destroy_vm(castle_options['castle_name'])
    virsh.undefine_vm(castle_options['castle_name'])
    delete_image(castle_options['castle_name'])

    if castle_options['target_source'] != Constants.VM_SOURCE_HACKTHEBOX:
        virsh.destroy_vm(castle_options['target_name'])

def ensure_networks_are_running():
    Log.logger.debug("Ensuring isolated network is running")
    virsh.define_network("/root/drako/services/main/training/city/resources/isolated-net.xml")
    virsh.start_network("isolated")

def steps_in_last_period(connection, training_id, amount_of_minutes):
    stmt = "SELECT count(*) as amount FROM step WHERE training_id=%s AND created_at>NOW() - INTERVAL " + f"{amount_of_minutes}" + " minute"
    results = connection.query(stmt, (training_id, ))
    if len(results) > 0:
        return results[0]['amount']
    else:
        return 0

# TODO: Add connectivity to our database as well
def check_castle_connectivity_to_target(connection, castle_name):
    vm_ip     = virsh.get_vm_ip_address(castle_name, internal=False, source="agent")
    target_ip = load_agent_options(connection, ["TRAINING_TARGET_IP"])['TRAINING_TARGET_IP']

    Log.logger.info(f"Will now check connectivity to the target {target_ip}")
    output = virsh.execute_command_in_vm(vm_ip, f"ping -c 1 {target_ip}", ignore_errors=True)
    if "1 packets transmitted, 1 packets received" in output:
        return True
    elif "port 22: No route to host" in output:
        Log.logger.warning("CANT ENSURE THERE IS NO CONNECTIVITY, WILL ALLOW THIS")
        return True
    else:
        return False

def update_training_target_finish_reason(connection, training_id, message):
    res = connection.query("select max(id) as id FROM training_target")
    if len(res) > 0:
        target_id = res[0]['id']
        stmt = "UPDATE training_target SET finish_reason=%s WHERE training_id=%s and finish_reason =%s AND id=%s"
        connection.execute(stmt, (message, training_id, "NOT_FINISHED", target_id))
        Log.logger.debug(f"Tried to update the training_target to {message}")
    else:
        Log.logger.debug(f"I did not find a training_target to update")

def perform_checks(castle_name, connection, training_id, amount_of_minutes):
    restart = False

    Log.logger.debug("Performing check on castle..")
    amount_of_steps = steps_in_last_period(connection, training_id, amount_of_minutes)
    Log.logger.info(f"Got {amount_of_steps} steps in the last {amount_of_minutes} minutes")

    # TODO: Check if this is actually needed
    if args.target_source != "hackthebox":
        connectivity_ok = check_castle_connectivity_to_target(connection, castle_name)
        if not connectivity_ok:
            Log.logging.warning("We failed a connectivity check with our target, we should recreate it")

    if amount_of_steps == 0:
        Log.logger.info("=" * 100)
        Log.logging.warning(f"There were no steps created in the last {amount_of_minutes} minutes, we will recreate it")
        restart = True

    return restart

def print_restart_message(attempts_amount, MAX_ATTEMPTS):
    Log.logger.debug(f"({attempts_amount}/{MAX_ATTEMPTS}) We need to perform a restart")
    Log.logger.info("=" * 100)
    Log.logger.info("=" * 100)
    Log.logger.info("=" * 100)
    Log.logger.info("=" * 100)
    Log.logger.info("=" * 100)

def check_if_orchestrator_finished(connection, orchestrator_id):
    orchestrator_finished = False

    res = connection.query("SELECT finished FROM orchestrator WHERE orchestrator_id=%s", (orchestrator_id, ))
    if len(res) != 1:
        raise ValueError(f"Orchestrator has more than 1 row, this should not happen: {res}")

    orchestrator_finished = res[0]['finished']

    return orchestrator_finished

def start_and_monitor_castle(castle_options, time_for_check):
    connection, orchestrator_id, training_id = prepare_environment(castle_options)
    start_castle(castle_options, orchestrator_id, training_id)
    Log.logger.debug("Doing initial sleep of 20 minutes after start of the machine")
    time.sleep(60*20)

    start_time = int(time.time())
    amount_of_minutes = time_for_check

    MAX_ATTEMPTS    = 5
    attempts_amount = 0
    Log.logger.info(f"Will now sleep for {castle_options['hours_per_target']} hours")

    did_not_reach_max_attempts   = attempts_amount < MAX_ATTEMPTS
    did_not_reach_amount_of_time = int(time.time()) < start_time + castle_options['hours_per_target'] * 60*60
    while did_not_reach_max_attempts and did_not_reach_amount_of_time:
        # First we check if the orchestrator finished
        orchestrator_finished = check_if_orchestrator_finished(connection, orchestrator_id)

        restart = perform_checks(castle_options['castle_name'], connection, training_id, amount_of_minutes)

        if orchestrator_finished:
            Log.logger.info("Orchestrator finished so we will finish here as well")
            break
        elif restart:
            print_restart_message(attempts_amount, MAX_ATTEMPTS)
            backup_vm(castle_options['castle_name'])
            start_castle(castle_options, orchestrator_id, training_id)
            attempts_amount += 1

        Log.logger.info(f"Will now sleep for {amount_of_minutes} minutes")
        time.sleep(60*amount_of_minutes)

    if not did_not_reach_max_attempts:
        update_training_target_finish_reason(connection, training_id, "reached_city_max_attempts")
    elif not did_not_reach_amount_of_time:
        update_training_target_finish_reason(connection, training_id, "reached_city_max_time")
    else:
        update_training_target_finish_reason(connection, training_id, "unknown_reason")
    
    connection.close()

def prepare_environment(castle_options):
    # create_database(castle_options['castle_db_name'])
    cleanup_db(castle_options['castle_db_name'])

    connection = Db(db_host=Constants.DRAGON_STAGING_DB_IP, db_name=castle_options['castle_db_name'], db_password=Constants.DRAGON_DB_PWD)

    add_agent_options(connection, castle_options)

    orchestrator_id = create_orchestrator_id(connection, castle_options)
    new_training_id = create_new_training(connection, orchestrator_id, castle_options['learner_family'], castle_options['learner_name'], Utils.dump_json(castle_options))

    return connection, orchestrator_id, new_training_id

def delete_broken_database(castle_db_name):
    Log.logger.warning(f"Dropping database {castle_db_name}")
    connection = Db(db_host=Constants.DRAGON_STAGING_DB_IP, db_name=castle_db_name, db_password=Constants.DRAGON_DB_PWD)
    connection.execute(f"DROP DATABASE {castle_db_name}")

def main(args):
    skipping_until_target=True # only valid if we have the skip_until flag
    Log.initialize_log(args.log_level)
    Log.add_info_large_ascii("City")
    Log.logger.debug("Starting with log level: %s" % args.log_level)
    
    stop_build_and_start_manager()

    ensure_networks_are_running()

    if args.iterate:
        # First we get all the target names
        targets = get_targets(args.target_source)
        for target in targets:
            # Then we iterate by them
            if skipping_until_target and args.skip_until != "" and target['name'].lower() != args.skip_until.lower():
                Log.logger.debug(f"Skipping target {target['name']} since i'm waiting for {args.skip_until}")
                continue
            elif skipping_until_target and target['name'].lower() == args.skip_until.lower():
                skipping_until_target = False
                Log.logger.warning(f"We reached the target {target['name']} so we can continue from the next one")
                continue

            try:
                castle_options = generate_castle_options(args, target['name'], target['id'])

                start_and_monitor_castle(castle_options, args.time_for_check)

                destroy_vms(castle_options)
            except:
                Log.logger.warning(f"Error trying to run target {castle_options} => {traceback.format_exc()}")
                destroy_vms(castle_options)
                delete_broken_database(castle_options['castle_db_name'])
    else:
        castle_options = generate_castle_options(args)

        start_and_monitor_castle(castle_options, args.time_for_check)

if __name__ == '__main__':
    # SETTING UP LOGGER
    args = argparser.parse_args()
    main(args)
