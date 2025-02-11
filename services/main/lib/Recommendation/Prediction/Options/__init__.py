import numpy
import string
import random

import lib.Common.Utils.Log as Log
import lib.Common.Exploration.Actions as Actions
from   lib.Common.Utils import Constants

PCT_TO_PICK_RECOMMENDED_OPTIONS = 0.5 #0.5

##############################################################################
######                        <OPTIONS GUESSING>                        ######
##############################################################################

## < GENERATORS >

def _generate_payload(options_data, state, environment_options):
    values = options_data["allowed_values"]
    return numpy.random.choice(values), None


def _generate_target(options_data, state, environment_options):
    values = options_data["allowed_values"]
    choice = numpy.random.choice(values)
    return values.index(choice), None

def _generate_string(options_data, state, environment_options):
    if 'string_size' in options_data:
        string_length = options_data['string_size']
    else:
        string_length = 8

    letters = string.ascii_lowercase
    return ''.join(numpy.random.choice(list(letters)) for i in range(string_length)), None


def _generate_port(options_data, state, environment_options):
    ports_available = state.get_open_ports() #['open_ports'], #environment.get_open_ports()
    if len(ports_available) == 0:
        # return random.randint(1, 65535)
        return None, "Cannot just guess a port for an exploit module"
    else:
        # raise ValueError("Cannot just guess a port for an exploit module")
        return numpy.random.choice(ports_available), None


def _generate_address(options_data, state, environment_options):
    return environment_options['target'], None


def _generate_command(options_data, state, environment_options):
    windows_useful_commands = [
        # r"search -d C:\\ -f user.txt",
        # r"search C:\\ -f root.txt",
        r'cat C:\\Documents\ and\ Settings\\john\\Desktop\\user.txt',
        r'cat C:\\Documents\ and\    Settings\\Administrator\\Desktop\\root.txt',
    ]
    linux_useful_commands = [
        "cat /root/root.txt",
        # "find /root -name root.txt 2>/dev/null",
    ]
    useful_commands = linux_useful_commands + windows_useful_commands

    os_name = state.get_os_name()
    if os_name is not None:
        Log.logger.debug(f"Got as os_name {os_name}")
        if os_name.lower() in ['debian', 'f5', 'junyper', 'juniper junos']:
            return numpy.random.choice(linux_useful_commands), None
        elif os_name.lower().startswith("windows"):
            return numpy.random.choice(windows_useful_commands), None
    else:
        Log.logger.debug("I did not have an os_name to use")

    return numpy.random.choice(useful_commands), None

TYPES_DISPATCHER = {
    "string":        _generate_string,
    "port":          _generate_port,
    "address":       _generate_address,
    "shell_command": _generate_command,
    # "payload":       self._generate_payload,
    # "target":        self._generate_target,
}


## < GENERATORS />

def _get_environment_option_values(action_type, game_type, all_available_options, state, environment_options, options_source):

    if game_type == "NETWORK":
        default_options = {
            "DST_IP":           environment_options['target'],
            "RHOST":            environment_options['target'],
            "RHOSTS":           environment_options['target'],
            "LHOST":            environment_options['local_ip'],           # self.environment.get_default_local_ip(),
            "LPORT":            environment_options['reverse_shell_port'], # self.environment.get_default_reverse_shell_port(),
        }
    elif game_type == "PRIVESC":
        default_options = {
            "SESSION_ID":       state.get_newest_session_id(),
            "SESSION":          state.get_newest_session_id(),
            "TIMEOUT":          30,
            "LHOST":            environment_options['local_ip'],             # self.environment.get_default_local_ip(),
            "LPORT":            environment_options['reverse_shell_port_2'], # self.environment.get_default_reverse_shell_port(),
        }
    else:
        default_options = {}

    if environment_options['target_source'] == Constants.VM_SOURCE_HACKTHEBOX and (action_type == "exploit" or game_type == "PRIVESC"):
        default_options['DELAY_TO_OBSERVE'] = 30
    else:
        default_options['DELAY_TO_OBSERVE'] = 1

    optional_options = {
        "SRVPORT":    environment_options['server_port'],
        "DISABLE_FW": 1,
    }

    for option_name in optional_options:
        if option_name in all_available_options:
            default_options[option_name] = optional_options[option_name]

    for option_name in default_options:
        options_source[option_name] = "DEFAULT"

    return default_options

def generate_options(prediction_req_data, action_name, options_recommender=None):
    """

    :param state:
    :param game_type:
    :param action_name_picked:
    :param environment_options:
    :return:
    """
    game_type = prediction_req_data.game_type

    Log.logger.info(f"Will generate options for action {action_name}")
    options_to_set        = Actions.client.get_missing_mandatory_options(game_type, action_name, {})
    all_available_options = Actions.client.get_all_options(game_type, action_name)
    action_type           = Actions.client.get_action_type(game_type, action_name)

    # 1 out of 2 times check if we have any good option available and select it
    recommended_options = {}
    if options_recommender is not None and random.random() > PCT_TO_PICK_RECOMMENDED_OPTIONS: #0.5
        recommended_options = options_recommender.get_recommended_options(prediction_req_data.target, prediction_req_data.state.get_state_hash(game_type), action_name)
        Log.logger.info("Picked recommended options from our environment: %s" % recommended_options)

    action_options, action_options_source, options_errors = generate_random_option_values(action_name, prediction_req_data.state, game_type, action_type, options_to_set, all_available_options, prediction_req_data.environment_options, recommended_options)

    return action_options, action_options_source, options_errors

def generate_random_option_values(action_name, state, game_type, action_type, options_to_set, all_available_options, environment_options, recommended_options):
    """
    Returns the options for an action.
    This should do its own analysis based on the rewards given for each action and parameters
    Mandatory Arguments:
    - command : the command to execute and name of session.
    - options : key value pairs to set as options.
    """
    options_errors = {}
    options_source = {}

    # Log.logger.debug("Will try to generate options for action %s of type %s with options to set %s" % (action_name, action_type, list(options_to_set.keys())))

    # WE ALWAYS SET PORT OPTIONS
    # Log.logger.debug(options_to_set)
    for option_name in all_available_options:
        # Log.logger.debug(option_name)

        ## IMPORTANT
        ## HERE WE FORCE PORT TO BE SET
        ## THIS IS SO WE DEPEND ON THE ENVIRONMENT TO BE FILLED FIRST
        ## WE DONT GUESS PORTS THAT ARE NOT THERE, THIS SHOULD HAVE A QUICK FEEDBACK LOOP
        ## ONLY FOR EXPLOIT FUNCTIONS
        if action_type == "exploit" and all_available_options[option_name]["type"] == "port" and option_name != "CPORT":  # and all_available_options[option_name]["required"] == "yes"
            options_to_set[option_name] = all_available_options[option_name]
    # Log.logger.debug(options_to_set)

    # FIRST WE TRY TO ASSIGN OPTIONS BASED ON THE ENVIRONMENT
    options_to_return = _get_environment_option_values(action_type, game_type, all_available_options, state, environment_options, options_source)

    # 2) NOW IF WE HAVE ANY RECOMMENDED OPTIONS, WE SET THOSE WHERE POSSIBLE
    # Log.logger.debug(options_to_return)
    for option_name in recommended_options:
        if option_name not in options_to_return:
            options_to_return[option_name] = recommended_options[option_name]
            Log.logger.debug("I added key %s => %s from recommended options" % (option_name, recommended_options[option_name]))
            options_source[option_name] = "RECOMMENDED_OPTION"

    # MARK OPTIONS AS ALREADY ASSIGNED IF PRESENT
    for option_name in options_to_return:
        if option_name in options_to_set:
            del options_to_set[option_name]

    # NOW WE GUESS VALUES FOR REMAINING OPTIONS
    if len(options_to_set) > 0:
        Log.logger.debug("We still have options to set, we will try to guess their values..")

        # Log.logger.warning(mandatory_options)
        for option_name in options_to_set:
            # Log.logger.warning(options_to_set[option_name])
            # Log.logger.warning("I need to add a new mandatory option missing (%s) with a random value" % option_name)

            option_data = options_to_set[option_name]
            option_type = option_data["type"]
            if option_type in TYPES_DISPATCHER:
                options_to_return[option_name], option_error = TYPES_DISPATCHER[option_type](option_data, state, environment_options)
                options_source[option_name] = "RANDOM"

                if option_error is not None:
                    options_errors[option_name] = option_error
            else:
                Log.logger.warning("Missing method to handle options type %s" % option_type)

    # HERE WE ADD ACTION SPECIFIC OPTIONS
    if action_name == "db_nmap":
        nmap_options = ["top_100", "top_1000", "top_10000", "all"]
        options_to_return["MODE"] = random.choice(nmap_options)
        options_source["MODE"]    = "HARDCODED"

    DISABLE_OPTIONS_ERRORS = False
    if DISABLE_OPTIONS_ERRORS:
        options_errors = {}

    return options_to_return, options_source, options_errors

###############################################################################
######                        </RANDOM BEHAVIOUR>                        ######
###############################################################################
