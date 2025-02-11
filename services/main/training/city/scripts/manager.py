# curl localhost:4000/generate_and_assign_single_target -d 'data={"target_source":"general","target_id":1}'

# docker container rm -f $(docker container ls -aq --filter name=manager)
# docker build -t manager -f services/main/training/city/Dockerfile.manager services/main 
# docker run --name manager -p 4000:4000 -v /var/lib/libvirt/images/:/var/lib/libvirt/images/ -v /etc/libvirt/qemu/:/etc/libvirt/qemu/ -v /run/libvirt/libvirt-sock:/app/libvirt-sock -it -t manager

from asyncio import new_event_loop
import time
import traceback
from flask import Flask, request

import lib.Common.Utils.Log as Log
from   lib.Common.Utils import Constants
from   lib.Training.Trainer import Hackthebox
from   lib.Common import Utils
from   lib.Training.Manager.Inventory import Inventory
from   lib.Training.Manager.Virsh import VIRSH

# INITIALIZATIONS
Log.initialize_log("2")
# Log.add_info_large_ascii("Manager")

SECONDS_IN_MINUTE=60

htb_client = Hackthebox.HTBVIP()

app = Flask(__name__)

################# LIBS

virsh_Client = VIRSH(Constants.VIRSH_SOCKET_LOCATION_DOCKER)
inventory    = Inventory(virsh_Client, Constants.VIRSH_DOCKER_TARGET_FOLDER_PATHS)

def remove_all_assigned_machines():
    while True:
        assigned_machines = htb_client.get_assigned_machines()
        if len(assigned_machines) > 0:
            Log.logger.debug("The following machines are already assigned: %s" % assigned_machines)

        for machine in assigned_machines:
            machine_id = machine['id']
            Log.logger.debug("Will attempt to remove machine %s" % machine_id)
            result = htb_client.remove_machine(machine_id)
            Log.logger.debug("Removed machine %s with result %s" % (machine_id, result))

        break

    Log.logger.info("Finished removing all assigned machines")

def generate_and_assign_htb_target(already_processed_targets, focus_target = None):
    Log.logger.info("=" * 60)
    Log.logger.info("1) First we will remove all assigned machines")
    remove_all_assigned_machines()

    Log.logger.info("2) Now we get the full list of available machines")

    boxes = htb_client.get_machines(focus_target)
    Log.logger.debug(f"There are {len(boxes)} boxes available")

    Log.logger.info("2.1) Checking if we have gone through all possible boxes")
    if len(boxes) == len(already_processed_targets):
        return {
            "success":              True,
            "target":               None,
            "finished_all_targets": True,
        }
    else:
        Log.logger.info("3) Now will go through each box")

        for box_data in boxes:
            box_id = box_data[0]
            if box_id not in already_processed_targets:
                Log.logger.info("3.1) Will now process the box %s(%d) of ip:%s with raiting: %.2f" % (
                box_data[1]['name'], box_id, box_data[1]['ip'], box_data[1]['rating']))

                Log.logger.info("3.2) Lets check if its already spawned by someone else")

                spawned_machines_map = htb_client.get_spawned_machines_map()
                Log.logger.debug(
                    "Will review if this box is one of the %d machines already spawned" % len(spawned_machines_map))
                if not ("force_assign" in box_data[1] and box_data[1]['force_assign']) and (
                        box_id in spawned_machines_map and spawned_machines_map[box_id]):
                    Log.logger.debug("Box %d seems to be spawned by someone else, will skip it" % box_id)
                    continue
                else:
                    Log.logger.debug("The box %d is not a spawned machine" % box_id)

                Log.logger.info("3.3) Now that we have a possible box, we will try to assign it for ourselves")

                res = htb_client.assign_machine(box_id)
                if int(res['success']) == 1:
                    Log.logger.info("3.3.1) Lets wait for 3 minutes for the machine to be deployed...")
                    time.sleep(SECONDS_IN_MINUTE * 3)

                    Log.logger.info("3.3.2) Now we will check it was properly assigned")
                    assigned_machines = htb_client.get_assigned_machines_map()

                    if box_id in assigned_machines:
                        Log.logger.debug("We have box %d assigned and we will use it as our target!" % box_id)
                        target = box_data[1]
                        print(assigned_machines)
                        print(target)
                        print(assigned_machines[box_id])
                        target['ip'] = assigned_machines[box_id]['dedi_ip']
                        
                        return {
                            "success": True,
                            "target":  target,
                            "message": "",
                        }
                elif res['status'].startswith("You need to wait "):
                    Log.logger.info(
                        "3.4) We got as a response: '%s', lets wait for 5 minutes and start again" % res['status'])
                    time.sleep(SECONDS_IN_MINUTE * 3)

                    return {
                        "success": False,
                        "target":  None,
                        "message": "RETRY"
                    }
                else:
                    Log.logger.info("3.5) We failed to assign the machine, lets try with the next one.. => %s" % res)
                    time.sleep(10)

        response = {
            "success":  True,
            "target":   None,
            "message": "FINISHED_ALL_TARGETS"
        }

    return response

################## !LIBS

@app.route("/")
def index():
    return "welcome"

@app.route("/get_targets", methods=['POST'])
def get_targets():
    if 'data' not in request.form:
        Log.logger.error("There needs to be a data field supplied")
        return {
            "success": False,
            "targets": [],
        }

    data_json = request.form['data']
    data      = Utils.json_loads(data_json)

    target_source = data['target_source']

    if target_source == Constants.VM_SOURCE_HACKTHEBOX:
        targets = htb_client.get_available_machines()
    elif target_source == Constants.VM_SOURCE_GENERAL:
        targets = inventory.get_targets(target_source)
    else:
        raise ValueError("i dont know how to process target_source %s" % response)

    response = {
        "success": True,
        "targets": targets,
    }

    return response

@app.route("/generate_and_assign_single_target", methods=['POST'])
def generate_and_assign_single_target():
    if 'data' not in request.form:
        Log.logger.error("There needs to be a data field supplied")
        return {
            "success": False,
            "target":  None,
        }

    data_json = request.form['data']
    data      = Utils.json_loads(data_json)

    target_source = data['target_source']
    target_id     = data['target_id']

    if target_source == Constants.VM_SOURCE_HACKTHEBOX:
        return generate_and_assign_htb_target([], target_id) # returns an object with success and message besides target
    elif target_source == Constants.VM_SOURCE_GENERAL:
        target = inventory.start_by_id(target_source, target_id)
    else:
        raise ValueError("i dont know how to process target_source %s" % target_source)

    return {
        "success": True,
        "target":  target,
    }

    return response

@app.route("/generate_and_assign_target", methods=['POST'])
def generate_and_assign_target():
    if 'data' not in request.form:
        Log.logger.error("There needs to be a data field supplied")
        return {
            "success":              False,
            "target":               None,
            "finished_all_targets": False,
        }

    data_json = request.form['data']
    data      = Utils.json_loads(data_json)

    target_source             = data['target_source']
    already_processed_targets = data['already_processed_targets']

    if target_source == Constants.VM_SOURCE_HACKTHEBOX:
        response = generate_and_assign_htb_target(already_processed_targets)
        return response
    else:
        raise ValueError(f"i dont know how to process target_source {target_source}")

@app.route("/reset_target", methods=['POST'])
def reset_target():
    if 'data' not in request.form:
        raise ValueError("There needs to be a data field supplied")

    data_json = request.form['data']
    data      = Utils.json_loads(data_json)

    target_source = data['target_source']
    target_id     = data['target_id']

    # A LOOP IS ADDED IN CASE RESETTING FAILS DUE TO NETWORK ISSUES
    errors_counter = 0
    assigned_ip    = "MISSING"
    while True:
        try:
            if target_source == Constants.VM_SOURCE_HACKTHEBOX:
                res               = htb_client.reset_machine(target_id)
                assigned_machines = htb_client.get_assigned_machines_map()

                if target_id in assigned_machines:
                    Log.logger.debug("We have box %d assigned and we will use it as our target!" % target_id)
                    print(assigned_machines)
                    print(assigned_machines[target_id])
                    assigned_ip = assigned_machines[target_id]['dedi_ip']
                    break
            elif target_source == Constants.VM_SOURCE_GENERAL:
                target      = inventory.start_by_id(target_source, target_id)
                assigned_ip = target['ip']
                break
            else:
                raise ValueError("Source %s is not known" % target_source)
        except:
            if errors_counter >= 10:
                response = {
                    "status":  "error",
                    "message": "Too many failures resetting the target!",
                }
                return response
            else:
                errors_counter += 1
                sleep_time = 60*errors_counter
                time.sleep(sleep_time)
                Log.logger.error("ERROR, will sleep for %d => %s" % (sleep_time, traceback.format_exc()))

    response = {
        "target_ip": assigned_ip,
        "status":    "success",
    }

    return response