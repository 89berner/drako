import sys
sys.path.append("/root/drako/services/main/")

from lib.Common.Exploration.Environment.State import State
import lib.Common.Utils.Log as Log
import lib.Common.Utils as Utils

import lib.Common.Exploration.Environment.Session as Session


import numpy

numpy.set_printoptions(threshold=sys.maxsize)

state_example1 = """
{
    "hosts": {},
    "jobs": {},
    "sessions": {},
    "target": "10.10.10.3"
}
"""

state_example2 = """
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
                    "80": {
                        "information": {
                            "name": "http",
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

new_session = Session.Session(state_example2)
# print(new_session.toJSON())
import json
res = json.dumps(new_session, cls=Session.CustomEncoder)
print(res)
print(json.dumps(new_session.session_data))

# Log.initialize_log("2")


# def print_state(state_json):
#     new_state = State(Utils.json_loads(state_json))
#     print(new_state.get_state_dict())
#     print(new_state.get_json())
#     # res = new_state.get_transform_state_to_observation("NETWORK")
#     # print(res)
#     state_hash = new_state.get_state_hash("NETWORK")  # utils.get_hash_of_list(res)
#     print(state_hash)


# print_state(state_example1)
# print_state(state_example2)
