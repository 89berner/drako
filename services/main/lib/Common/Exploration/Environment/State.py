import time
import copy
from dictdiffer import diff
import hashlib
import lib.Common.Utils.Log as Log
import lib.Common.Utils as Utils
import lib.Common.Utils.Constants as Constants
from lib.Common.Exploration.Environment.Session import Session

import sys
import numpy as np
np.set_printoptions(threshold=sys.maxsize)

tcp_port_list_num_map = {i: 1 for i in Constants.TCP_PORT_LIST_NUM}
udp_port_list_num_map = {i: 1 for i in Constants.UDP_PORT_LIST_NUM}

class NumpyState:
    def __init__(self, total_array_size):
        self.array = np.zeros(total_array_size, dtype=np.uint8)
        self.total_size = total_array_size
        self.arr_pos = 0
        # Log.logger.debug("Created an NumpyState of size %d" % self.total_size)

    def get_position(self):
        return self.arr_pos

    def increment_position(self, amount):
        self.arr_pos += amount

    def add_string_as_hash(self, input_str, length):
        if input_str == "":  # empty string is just zeros
            # Log.logger.debug("Input data is empty so will add zeros")
            for pos in range(0, length):
                self.array[self.arr_pos + pos] = 0
        else:
            # Log.logger.debug("Hashing value => %s" % input_str)
            input_str = str(input_str)

            m = hashlib.sha256()
            m.update(bytes(input_str, 'ascii'))
            created_hash = m.digest()

            for pos in range(0, length):
                val = created_hash[pos]
                if val == 0:  # we never use val 0 since that means empty
                    val = 1
                self.array[self.arr_pos + pos] = val

        # Now lets move the needle
        self.arr_pos += length

    def mark_in_hash_bucket(self, input_str, bucket_size):
        m = hashlib.sha256()
        m.update(bytes(input_str, 'ascii'))
        created_hash_val = int.from_bytes(m.digest(), byteorder='big') % bucket_size
        self.array[self.arr_pos + created_hash_val] = 1

        # Log.logger.debug("Bucket allocated => %s" % created_hash_val)

    def get(self, start=None, end=None):
        if start is None:
            return self.array
        else:
            return self.array[start:end]

    def get_up_to_counter(self, start_pos=None):
        if start_pos is None:
            return self.array[:self.arr_pos]
        else:
            return self.array[start_pos:self.arr_pos]

    def log_state(self):
        # Log.logger.debug("Numpy array of size %d has its counter at position %d" % (self.total_size, self.arr_pos))
        pass


class State:
    def __init__(self, initial_state_dict=None):
        self.hosts     = {}
        self.sessions  = {}
        self.jobs      = {}
        self.target    = None
        self.target_ip = None

        self.transactions_since_step_started        = []
        self.transactions_since_last_raw_observaton = []

        if initial_state_dict is not None:
            self.load_state_dict(initial_state_dict)

    def set_target(self, target):
        self.target = target

    def set_target_ip(self, target_ip):
        self.target_ip = target_ip

    def deduce_game_type(self):
        if len(self.sessions) > 0:
            return "PRIVESC"
        else:
            return "NETWORK"

    def _get_empty_host_structure(self):
        return {
            "ports": {
                "tcp": {},
                "udp": {},
            },
            "commands_result": {},
            "information": {},
            "loot": self._get_empty_loot_structure(),
        }

    def _get_empty_loot_structure(self):
        return {
            "file_contents": {},
            "files_list":    {},
            "credentials":   {},
        }

    def save_state_change_transaction(self, previous_state):
        diff_transactions = list(diff(previous_state, self.get_state_dict()))

        for transaction in diff_transactions:
            # Log.logger.debug("Will now save the following transaction:")
            # Log.logger.debug(transaction)
            self.transactions_since_step_started.append(transaction)
            self.transactions_since_last_raw_observaton.append(transaction)

    def get_and_clean_transactions_since_last_raw_observaton(self):
        transactions = self.transactions_since_last_raw_observaton
        self.transactions_since_last_raw_observaton = []

        return transactions

    def get_and_clean_transactions_since_step_started(self):
        transactions = self.transactions_since_step_started
        self.transactions_since_step_started = []

        return transactions

    def get_open_ports(self):
        target_key = self.get_target()
        if len(self.hosts) == 0:
            return []
        else:
            ports_to_use = list(self.hosts[target_key]["ports"]["tcp"].keys())
            ports_to_use.extend(list(self.hosts[target_key]["ports"]["udp"].keys()))

            return ports_to_use

    def get_open_ports_map(self):
        target_key = self.get_target()

        if target_key in self.hosts:
            return self.hosts[target_key]["ports"]
        else:
            return {}

    def get_newest_session_id(self):
        sessions_list = self.get_sessions()
        if len(sessions_list) > 0:
            return max(sessions_list.keys())
        else:
            raise ValueError("No sessions available!")

    def get_newest_session_information(self):
        latest_session_id = self.get_newest_session_id()
        return self.sessions[latest_session_id].get_dict()

    def get_newest_session(self):
        latest_session_id = self.get_newest_session_id()
        return self.sessions[latest_session_id]

    # MODIFY STATE

    def add_host(self, address_received, hostname=None, os_name=None, os_flavor=None):
        address_allowed = self.validate_address(address_received)
        if not address_allowed:
            return

        # address must be our current target, which we validated before
        address = self.get_target()
        if address not in self.hosts:
            Log.logger.debug("Address %s is missing, will add the host" % address)
            # GET PREVIOUS STATE
            previous_state = copy.deepcopy(self.get_state_dict())
            # UPDATE STATE
            self.hosts[address] = self._get_empty_host_structure()
            # RECORD CHANGES TO LOG
            self.save_state_change_transaction(previous_state)

        # GET PREVIOUS STATE
        previous_state = copy.deepcopy(self.get_state_dict())

        self.replace_value(self.hosts[address]["information"], "hostname", hostname)
        self.replace_value(self.hosts[address]["information"], "os_name", os_name)

        # Limit the size of os_flavor since some actions might put random content there when they fail
        if os_flavor is not None and len(os_flavor) > 100:
            os_flavor = os_flavor[:100]

        self.replace_value(self.hosts[address]["information"], "os_flavor", os_flavor)

        # RECORD CHANGES TO LOG
        self.save_state_change_transaction(previous_state)

    def get_os_name(self):
        target_key = self.get_target()

        if target_key in self.hosts:
            if "information" in self.hosts[target_key] and 'os_name' in self.hosts[target_key]['information']:
                return self.hosts[target_key]['information']['os_name']

        return None

    def add_service(self, address_received, port, protocol, state=None, name=None, application=None):
        address_allowed = self.validate_address(address_received)
        if not address_allowed:
            return False

        # address must be our current target, which we validated before
        address = self.get_target()

        if state != Constants.OPEN_PORT:
            Log.logger.warning(f"Only open states are added, state provided is: {state}")
            return False

        # Log.logger.debug("Adding service %s" % address)
        # ADD HOST IF MISSING

        # FORCE PORT TO BE A STRING
        port = str(port)

        self.add_host(address)

        if protocol not in ["udp", "tcp"]:
            raise ValueError("Invalid protocol %s, only tcp or udp allowed" % protocol)

        # ADD PORT STRUCTURE IF MISSING

        if port not in self.hosts[address]["ports"][protocol]:
            # GET PREVIOUS STATE
            previous_state = copy.deepcopy(self.get_state_dict())

            self.hosts[address]["ports"][protocol][port] = {
                "information": {},
                "notes": {},
            }

            # RECORD CHANGES TO LOG
            self.save_state_change_transaction(previous_state)

        # ADD SERVICE INFORMATION

        # GET PREVIOUS STATE
        previous_state = copy.deepcopy(self.get_state_dict())

        self.replace_value(self.hosts[address]["ports"][protocol][port]["information"], "state", state)
        self.replace_value(self.hosts[address]["ports"][protocol][port]["information"], "name", name)
        self.replace_value(self.hosts[address]["ports"][protocol][port]["information"], "application", application)

        # RECORD CHANGES TO LOG
        self.save_state_change_transaction(previous_state)

        return True

    def add_session_command(self, address_received, platform, username, session_command, session_command_output):
        address_allowed = self.validate_address(address_received)
        if not address_allowed:
            return

        # address must be our current target, which we validated before
        address = self.get_target()

        # ADD HOST IF MISSING
        self.add_host(address, None, None, platform)

        # CREATE USERNAME SPACE

        # GET PREVIOUS STATE
        previous_state = copy.deepcopy(self.get_state_dict())

        if username not in self.hosts[address]["commands_result"]:
            self.hosts[address]["commands_result"][username] = {}

            # RECORD CHANGES TO LOG
        self.save_state_change_transaction(previous_state)

        # STORE SESSION COMMAND OUTPUT

        # GET PREVIOUS STATE
        previous_state = copy.deepcopy(self.get_state_dict())

        if session_command not in self.hosts[address]["commands_result"][username]:
            self.hosts[address]["commands_result"][username][session_command] = {}

        self.hosts[address]["commands_result"][username][session_command][time.time()] = session_command_output

        # RECORD CHANGES TO LOG
        self.save_state_change_transaction(previous_state)

        # GET PREVIOUS STATE
        previous_state = copy.deepcopy(self.get_state_dict())

        # RECORD CHANGES TO LOG
        self.save_state_change_transaction(previous_state)

    # check the target ip is allowed for this target
    def validate_address(self, address):
        target    = self.get_target()
        target_ip = self.get_target_address()

        if address == target_ip or address == target:
            return True
        else:
            Log.logger.warning("Address %s is not allowed, will not add information (target is %s and target_ip is %s)" % (address, self.target, target_ip))
            return False

    def add_session(self, session_id, session_data):
        # FIRST LETS CHECK IF THIS ACTUALLY ADDS NEW DATA SINCE THESE ARE OBJECTS
        # if session_id in self.sessions:
        #     prev_json = Session(session_data).get_json()
        #     curr_json = self.sessions[session_id].get_json()
        #     Log.logger.debug(f"Compare:\n{prev_json}\n{curr_json}")
        #     if prev_json == curr_json:
        #         return # Nothing to be done
        #     else:
        #         Log.logger.debug("JSONs are different!")

        # GET PREVIOUS STATE
        previous_state = copy.deepcopy(self.get_state_dict())

        self.sessions[session_id] = Session(session_data)

        # RECORD CHANGES TO LOG
        self.save_state_change_transaction(previous_state)

    def add_note(self, address_received, port, note_type, data, protocol):
        address_allowed = self.validate_address(address_received)
        if not address_allowed:
            return

        # address must be our current target, which we validated before
        address = self.get_target()

        # First create the service if missing
        service_added = self.add_service(address, port, protocol)
        if service_added:
            # CREATE NOTE TYPE

            # GET PREVIOUS STATE
            previous_state = copy.deepcopy(self.get_state_dict())

            # Force port to be a string
            port = str(port)

            if note_type not in self.hosts[address]["ports"][protocol][port]["notes"]:
                self.hosts[address]["ports"][protocol][port]["notes"][note_type] = {}

            # RECORD CHANGES TO LOG
            self.save_state_change_transaction(previous_state)

            # STORE NOTE

            # GET PREVIOUS STATE
            previous_state = copy.deepcopy(self.get_state_dict())

            data_hash = Utils.get_hash_of_dict(data)[:8]
            self.hosts[address]["ports"][protocol][port]["notes"][note_type][data_hash] = data

            # RECORD CHANGES TO LOG
            self.save_state_change_transaction(previous_state)
        else:
            Log.logger.warning("%s %s was not added" % (protocol, str(port)))

    def remove_missing_sessions(self, sessions_map):
        session_ids_to_delete = []
        for session_id in self.sessions:
            if session_id not in sessions_map:
                session_ids_to_delete.append(session_id)

        for session_id in session_ids_to_delete:
            # GET PREVIOUS STATE
            previous_state = copy.deepcopy(self.get_state_dict())
            del self.sessions[session_id]
            Log.logger.debug(f"Removed session_id:{session_id}")

            # RECORD CHANGES TO LOG
            self.save_state_change_transaction(previous_state)

    def set_jobs_map(self, jobs_list):
        # GET PREVIOUS STATE
        previous_state = copy.deepcopy(self.get_state_dict())

        self.jobs = jobs_list

        # RECORD CHANGES TO LOG
        self.save_state_change_transaction(previous_state)

    def add_file_content(self, entry):
        filename = entry["filename"]
        filepath = entry["filepath"]
        file_contents = entry["file_contents"]
        address = entry["address"]

        # First add host if missing
        self.add_host(address)
        # host = self._get_empty_host_structure()
        # if (address in self.hosts):
        #     host = self.hosts[address]
        #     if ("loot" not in host):
        #         host["loot"] = self._get_empty_loot_structure()

        # Log.logger.debug(host["loot"]["file_contents"])

        # GET PREVIOUS STATE
        previous_state = copy.deepcopy(self.get_state_dict())

        Log.logger.debug("Will add file %s to state" % filename)

        self.hosts[address]["loot"]["file_contents"][filename] = {
            "path": filepath,
            "content": file_contents
        }

        # RECORD CHANGES TO LOG
        self.save_state_change_transaction(previous_state)

    def add_credentials(self, address_received, loot_space, loot):
        address_allowed = self.validate_address(address_received)
        if not address_allowed:
            return

        # address must be our current target, which we validated before
        address = self.get_target()

        # FIRST ADD HOST IF MISSING
        self.add_host(address)

        Log.logger.debug("Will add credentials %s to state" % loot)

        # CREATE LOOT SPACE

        # GET PREVIOUS STATE
        previous_state = copy.deepcopy(self.get_state_dict())

        if loot_space not in self.hosts[address]["loot"]["credentials"]:
            self.hosts[address]["loot"]["credentials"][loot_space] = {}

        # RECORD CHANGES TO LOG
        self.save_state_change_transaction(previous_state)

        # SAVE CREDENTIAL

        # GET PREVIOUS STATE
        previous_state = copy.deepcopy(self.get_state_dict())

        uuid = time.time()
        self.hosts[address]["loot"]["credentials"][loot_space][uuid] = loot

        # RECORD CHANGES TO LOG
        self.save_state_change_transaction(previous_state)

    # ! MODIFY STATE

    def add_file_found(self, address_received, file, filesize):
        address_allowed = self.validate_address(address_received)
        if not address_allowed:
            return

        # address must be our current target, which we validated before
        address = self.get_target()

        # ADD HOST
        self.add_host(address)

        # ADD FILE TO STATE

        # GET PREVIOUS STATE
        previous_state = copy.deepcopy(self.get_state_dict())

        # ADD FILE
        self.hosts[address]["loot"]["files_list"][file] = filesize

        # RECORD CHANGES TO LOG
        self.save_state_change_transaction(previous_state)

    # STATE FOR NEURAL NETWORKS
    def _build_input_string_as_hash(self, input_arr, input_str, length):

        if input_str == "":  # empty string is just zeros
            for pos in range(0, length):
                input_arr.append(0)
        else:
            m = hashlib.sha256()
            m.update(bytes(input_str, 'ascii'))
            created_hash = m.digest()

            # if (input_str != ""):
            #    print("Hashing value => %s" % input_str)

            for position in range(0, length):
                val = created_hash[position]
                if val == 0:  # we never use val 0 since that means empty
                    val = 1
                input_arr.append(val)

    def _get_int_from_hash(self, input_str, range_provided):
        m = hashlib.sha256()
        m.update(bytes(input_str, 'ascii'))
        created_hash = m.digest()

        val = created_hash[0] % range_provided

        return val

    def get_state_hash(self, game_type):
        observation = self.get_transform_state_to_observation(game_type)
        # print(str(observation))
        return Utils.get_hash_of_list(observation)

    def get_transform_state_to_observation(self, game_type):
        if game_type == "NETWORK":
            return self.get_transform_state_to_network_observation()
        elif game_type == "PRIVESC":
            return self.get_transform_state_to_privesc_observation()
        else:
            raise ValueError("Game type %s is not known" % game_type)

    def add_to_numpy_state_host_information(self, SPACE, target_address, numpy_state):
        if target_address in self.hosts:
            information_data = self.hosts[target_address]["information"]

            if "os_flavor" in information_data:
                numpy_state.add_string_as_hash(information_data["os_flavor"], SPACE["OS_FLAVOR"])
            else:
                numpy_state.add_string_as_hash("", SPACE["OS_FLAVOR"])

            if "os_name" in information_data:
                # Log.logger.debug("looking into OS data")
                numpy_state.add_string_as_hash(information_data["os_name"], SPACE["OS_NAME"])
            else:
                numpy_state.add_string_as_hash("", SPACE["OS_NAME"])
        else:
            # numpy_state.add_string_as_hash("",  SPACE["HOSTNAME"])
            numpy_state.add_string_as_hash("", SPACE["OS_FLAVOR"])
            numpy_state.add_string_as_hash("", SPACE["OS_NAME"])

    def get_transform_state_to_privesc_observation(self):
        target_key = self.get_target()

        SPACE = {
            "HOSTNAME": 4,
            "OS_FLAVOR": 4,
            "OS_NAME": 4,
            "SPACE_FOR_PRESENT_FLAG": 1,
            "SESSION": {
                "ARCH": 1,
                "DESC": 1,
                "ROUTES": 1,
                "TYPE": 1,
                "USER": 1,
                "USERNAME": 1,
                "PLATFORM": 1,
                # "VIA_EXPLOIT": 1,
                "VIA_PAYLOAD": 1,
            },
        }
        TOTAL_AMOUNT_OF_SESSIONS = 1

        host_information_size = SPACE['OS_FLAVOR'] + SPACE['OS_NAME']

        sessions_information_size =  SPACE['SPACE_FOR_PRESENT_FLAG'] + SPACE["SESSION"]["ARCH"] + SPACE["SESSION"]["DESC"]
        sessions_information_size += SPACE["SESSION"]["ROUTES"]      + SPACE["SESSION"]["TYPE"]
        sessions_information_size += SPACE["SESSION"]["USER"]        + SPACE["SESSION"]["USERNAME"]
        sessions_information_size += SPACE["SESSION"]["PLATFORM"] + SPACE["SESSION"]["VIA_PAYLOAD"] #SPACE["SESSION"]["VIA_EXPLOIT"] +

        total_size = host_information_size + ( sessions_information_size * TOTAL_AMOUNT_OF_SESSIONS )

        numpy_state = NumpyState(total_size)

        ## STEP 1 INFORMATION ON THE HOST
        self.add_to_numpy_state_host_information(SPACE, target_key, numpy_state)

        ## STEP 2: ADD SESSIONS INFORMATIONw

        if TOTAL_AMOUNT_OF_SESSIONS > 1:
            for idx in range(1, TOTAL_AMOUNT_OF_SESSIONS + 1):
                if len(self.sessions) >= idx:
                    numpy_state.add_string_as_hash("PRESENT", 1)
                    for key in SPACE["SESSION"]:
                        self.add_session_key_to_numpy_state(numpy_state, SPACE["SESSION"], key, idx)
                else:
                    numpy_state.add_string_as_hash("NOT PRESENT", 1)
                    for key in SPACE["SESSIONS"]:
                        numpy_state.add_string_as_hash("", SPACE["SESSION"][key])  # VIA_PAYLOAD
        else:
            if len(self.sessions) >= 1:
                numpy_state.add_string_as_hash("PRESENT", 1)
                for key in SPACE["SESSION"]:
                    max_session_idx = max(self.sessions.keys())
                    self.add_session_key_to_numpy_state(numpy_state, SPACE["SESSION"], key, max_session_idx)
            else:
                numpy_state.add_string_as_hash("NOT PRESENT", 1)
                for key in SPACE["SESSION"]:
                    numpy_state.add_string_as_hash("", SPACE["SESSION"][key])  # VIA_PAYLOAD

        numpy_state.log_state()

        return numpy_state.get()

    def add_session_key_to_numpy_state(self, numpy_state, space_obj, key, idx):
        # Log.logger.debug([space_obj, key, idx])
        # Log.logger.debug(self.sessions)
        session_obj  = self.sessions[str(idx)]
        session_dict = session_obj.get_dict()

        lower_case_key = key.lower()
        if lower_case_key in session_dict:
            numpy_state.add_string_as_hash(session_dict[lower_case_key], space_obj[key])
        else:
            numpy_state.add_string_as_hash("", space_obj[key])  # VIA_PAYLOAD

    def get_target(self):
        """
        This should find in the current state the target address to use for the state information.
        """
        return self.target

    def get_target_address(self):
        """
        This should find in the current state the target address to use for the state information.
        """
        return self.target_ip

    def get_transform_state_to_network_observation(self):
        target_key = self.get_target()
        # print(target_address)
        SPACE = {
            "HOSTNAME": 4,
            "OS_FLAVOR": 4,
            "OS_NAME": 4,
            "PORT_SPACE": {
                "NAME": 1,
                "APPLICATION": 1,
            },
        }
        host_information_size = SPACE['OS_FLAVOR'] + SPACE['OS_NAME']

        port_size = SPACE['PORT_SPACE']['NAME'] + SPACE['PORT_SPACE']['APPLICATION']
        tcp_top_ports_size = port_size * 1000
        udp_top_ports_size = port_size * 100
        tcp_ports_bucket_size = 1000
        udp_ports_bucket_size = 100

        ports_size = tcp_top_ports_size + udp_top_ports_size + tcp_ports_bucket_size + udp_ports_bucket_size

        application_size = SPACE['PORT_SPACE']['APPLICATION'] * 100

        sessions_size = 1

        # 0) CREATE NUMPY ARRAY AND POSITION COUNTER
        total_array_size = host_information_size + ports_size + application_size + sessions_size
        numpy_state      = NumpyState(total_array_size)

        ## STEP 1 INFORMATION ON THE HOST
        self.add_to_numpy_state_host_information(SPACE, target_key, numpy_state)

        # Log.logger.debug(numpy_state.get(0,host_information_size))

        ## STEP 2, INFORMATION ON THE PORTS

        # 1) WE ADD THE MOST COMMON 1K TCP PORTS
        # 2) WE ADD THE MOST COMMON 100 UDP PORTS

        # Log.logger.debug(target_address)
        # Log.logger.debug(self.hosts)
        for protocol, list_of_ports in [("tcp", Constants.TCP_PORT_LIST_NUM), ("udp", Constants.UDP_PORT_LIST_NUM)]:
            for port in list_of_ports:
                # if target_address in self.hosts:
                #     Log.logger.debug([port, self.hosts[target_address]["ports"][protocol]])
                if target_key in self.hosts and port in self.hosts[target_key]["ports"][protocol]:
                    # Log.logger.debug(self.hosts[target_address])
                    port_data = self.hosts[target_key]["ports"][protocol][port]["information"]
                    # CHECK PORT BEING OPEN
                    # Log.logger.debug(port_data)
                    if "state" in port_data and port_data["state"] == Constants.OPEN_PORT:
                        if "name" in port_data:
                            numpy_state.add_string_as_hash(port_data["name"], SPACE["PORT_SPACE"]["NAME"])
                        else:
                            numpy_state.add_string_as_hash("MISSING", SPACE["PORT_SPACE"]["NAME"])

                        if "application" in port_data:
                            numpy_state.add_string_as_hash(port_data["application"], SPACE["PORT_SPACE"]["APPLICATION"])
                        else:
                            numpy_state.add_string_as_hash("MISSING", SPACE["PORT_SPACE"]["APPLICATION"])
                    else:
                        numpy_state.add_string_as_hash("", SPACE["PORT_SPACE"]["APPLICATION"] + SPACE["PORT_SPACE"]["NAME"])
                else:
                    numpy_state.add_string_as_hash("", SPACE["PORT_SPACE"]["APPLICATION"] + SPACE["PORT_SPACE"]["NAME"])
                # Log.logger.debug([protocol, port, numpy_state.get_up_to_counter(start_counter)])
                # if (protocol == "udp"):
                # time.sleep(1)

        # 3) WE GO THROUGH ALL TCP PORTS NOT IN THE LIST AND PLACE THEM INTO BUCKETS OF 1000
        # 4) WE GO THROUGH ALL UDP PORTS NOT IN THE LIST AND PLACE THEM INTO BUCKETS OF 100
        for protocol, bucket_size, map_of_top_ports in [("tcp", tcp_ports_bucket_size, tcp_port_list_num_map),
                                                        ("udp", udp_ports_bucket_size, udp_port_list_num_map)]:
            # Log.logger.debug("Will use a bucket of %d positions for protocol %s" % (bucket_size, protocol))
            # Log.logger.debug(map_of_top_ports)
            if target_key in self.hosts:
                protocol_data = self.hosts[target_key]["ports"][protocol]
                for port in range(1, 65536):
                    port = str(port) # IMPORTANT HAVE PORTS AS STRING

                    if port in protocol_data and port not in map_of_top_ports:
                        # Log.logger.debug("port %s not in map_of_top_ports" % port)
                        port_data = protocol_data[port]["information"]
                        if "state" in port_data and port_data["state"] == Constants.OPEN_PORT:
                            numpy_state.mark_in_hash_bucket(port, bucket_size)

            numpy_state.increment_position(bucket_size)

        ## STEP 3, INFORMATION ON THE APPLICATIONS
        # Log.logger.debug("Will use a bucket of %d positions for applications" % application_size)
        if target_key in self.hosts:
            for protocol in ["tcp", "udp"]:
                protocol_data = self.hosts[target_key]["ports"][protocol]
                # Log.logger.debug(protocol_data)
                for port in protocol_data:
                    port_data = protocol_data[port]["information"]
                    if "name" in port_data and "state" in port_data and port_data["state"] == Constants.OPEN_PORT:
                        app_name = port_data["name"]
                        numpy_state.mark_in_hash_bucket(app_name, application_size)
        numpy_state.increment_position(application_size)

        if len(self.sessions) > 0:
            numpy_state.add_string_as_hash("sessions_found", sessions_size)

        numpy_state.log_state()

        return numpy_state.get()

    def get_observation_shape_size(self):
        return 100

    # STATE FOR NEURAL NETWORKS

    def get_sessions(self):
        return self.sessions

    def get_hosts(self):
        return self.hosts

    def replace_value(self, obj, key, value):
        if key in obj:
            previous_value = obj[key]

            # We never replace an actual value with an empty one
            if previous_value != value and value != "" and value is not None:
                # Log.logger.debug("Replacing key %s from value %s to %s" % (key, previous_value, value))
                obj[key] = value
            else:
                return False
        else:
            # Log.logger.debug("Adding key %s of value %s" % (key, value))
            if value is not None and value != "":
                obj[key] = value

        return True

    # UTILS

    def get_state_dict(self):
        # Transform to dict to avoid comparing objects by diff
        sessions_dict = {}
        for session_id in self.sessions:
            sessions_dict[session_id] = self.sessions[session_id].get_dict()

        return {
            "hosts":     self.hosts,
            "sessions":  sessions_dict,
            "jobs":      self.jobs,
            "target":    self.target,
            "target_ip": self.target_ip
        }

    def load_state_dict(self, state_dict):
        self.hosts     = state_dict["hosts"]
        self.jobs      = state_dict["jobs"]
        self.target    = state_dict["target"]
        self.target_ip = state_dict["target_ip"]

        sessions = state_dict["sessions"]
        for session_id in sessions:
            self.add_session(session_id, sessions[session_id])

    def get_json(self):
        return Utils.dump_json(self.get_state_dict())


# {
#     "hosts": {
#         "10.10.10.4": {
#             "commands_result": {},
#             "information": {
#                 "hostname": "LEGACY",
#                 "os_name": "Windows XP"
#             },
#             "loot": {
#                 "credentials": {},
#                 "file_contents": {},
#                 "files_list": {},
#             },
#             "ports": {
#                 "tcp": {
#                     "139": {
#                         "information": {
#                             "name": "smb",
#                             "state": "open"
#                         },
#                         "notes": {}
#                     },
#                     "445": {
#                         "information": {
#                             "application": "Windows XP SP3 (language:English) (name:LEGACY) (workgroup:HTB)",
#                             "name": "smb",
#                             "state": "open"
#                         },
#                         "notes": {}
#                     }
#                 },
#                 "udp": {}
#             }
#         }
#     },
#     "jobs": {},
#     "sessions": {
#         "1": {
#             "arch": "x86",
#             "desc": "Meterpreter",
#             "exploit_uuid": "ubzaaxqu",
#             "info": "NT AUTHORITY\\SYSTEM @ LEGACY",
#             "platform": "windows",
#             "routes": "",
#             "session_host": "10.10.10.4",
#             "session_port": 445,
#             "target_host": "10.10.10.4",
#             "tunnel_local": "172.17.0.20:43462",
#             "tunnel_peer": "10.10.10.4:1032",
#             "type": "meterpreter",
#             "user": "unknown",
#             "username": "unknown",
#             "uuid": "odvhbur6",
#             "via_exploit": "exploit/windows/smb/ms08_067_netapi",
#             "via_payload": "payload/windows/meterpreter/reverse_tcp",
#             "workspace": "narzde"
#         }
#     },
#     "target": "10.10.10.4"
# }