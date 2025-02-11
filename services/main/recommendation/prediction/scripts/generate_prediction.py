import json
import sys
import argparse
import time

sys.path.append("/root/drako/services/main/")

from werkzeug.datastructures import MultiDict

import lib.Recommendation.Prediction        as Prediction
import lib.Recommendation.Prediction.Helper as Helper
import lib.Common.Utils                     as Utils
import lib.Common.Utils.Constants           as Constants
import lib.Common.Utils.Log                 as Log

from lib.Common.Utils.Db                      import Db
from lib.Common.Exploration.Environment.State import State

import lib.Common.Exploration.Actions as Actions

argparser = argparse.ArgumentParser(description='Use Trainer from command line')
argparser.add_argument('--amount_of_predictions', dest='amount_of_predictions', type=int,  help='amount of predictions to run', default=1)
args = argparser.parse_args()

Log.initialize_log("2")

Actions.initialize()
Actions.client.load_metasploit_actions()

prod_connection    = Db(db_host=Constants.DRAGON_PROD_DNS,      db_name=Constants.DRAGON_PROD_DB_NAME,    db_password=Constants.DRAGON_DB_PWD)
staging_connection = Db(db_host=Constants.DRAGON_STAGING_DB_IP, db_name=Constants.get_dragon_staging_db(), db_password=Constants.DRAGON_DB_PWD)

network_state_json = """
{
    "hosts": {
        "10.10.10.3": {
            "commands_result": {},
            "information": {
                "os_name": "Unknown"
            },
            "loot": {
                "credentials": {},
                "file_contents": {},
                "files_list": {},
            },
            "ports": {
                "tcp": {
                    "445": {
                        "information": {
                            "application": "Unix (Samba 3.0.20-Debian)",
                            "name": "smb",
                            "state": "open"
                        },
                        "notes": {}
                    }
                },
                "udp": {}
            }
        }
    },
    "jobs": {},
    "sessions": {},
    "target": "10.10.10.3"
}
"""

privesc_state_json = """
{
    "hosts": {
        "10.10.10.3": {
            "commands_result": {},
            "information": {
                "os_name": "Unknown"
            },
            "loot": {
                "credentials": {},
                "file_contents": {},
                "files_list": {},
            },
            "ports": {
                "tcp": {
                    "445": {
                        "information": {
                            "application": "Unix (Samba 3.0.20-Debian)",
                            "name": "smb",
                            "state": "open"
                        },
                        "notes": {}
                    }
                },
                "udp": {}
            }
        }
    },
    "jobs": {},
    "sessions": {
        "1": {
            "arch": "cmd",
            "desc": "Command shell",
            "exploit_uuid": "irx2tlqx",
            "info": "",
            "routes": "",
            "session_host": "10.10.10.3",
            "session_port": 139,
            "target_host": "10.10.10.3",
            "tunnel_local": "172.17.1.19:28166",
            "tunnel_peer": "10.10.10.3:49171",
            "type": "shell",
            "user": "unknown",
            "username": "unknown",
            "uuid": "fwihyndu",
            "via_exploit": "exploit/multi/samba/usermap_script",
            "via_payload": "payload/cmd/unix/reverse_netcat",
            "workspace": "obzwxq"
        }
    },
    "target": "10.10.10.3"
}
"""

state_json = network_state_json
# game_type = "NETWORK"

state_json = privesc_state_json
game_type = "PRIVESC"

state_dict = Utils.json_loads(state_json)
state = State(state_dict)
training_id = 1

exploration_method = "COUNTER"
environment_options = {
    "target":             "10.10.10.3",
    "local_ip":           "127.0.0.1",
    "reverse_shell_port": "12345",
    "server_port":        "34567"
}
action_history = []

form_data = MultiDict([
    ('game_type',           game_type),
    ('environment_options', Utils.dump_json(environment_options)),
    ('state',               state_json),
    ('action_history',      Utils.dump_json(action_history)),
    ('exploration_method',  exploration_method)
])

for i in range(1):
    network_information = Helper.load_network_information(staging_connection, training_id)
    time.sleep(1)

for i in range(args.amount_of_predictions):
    result = Prediction.predict(form_data, network_information)
    # Remove to avoid too much noise in the response
    del result['action_data']

    print(Utils.dump_json_pretty(result))

prod_connection.close()
staging_connection.close()