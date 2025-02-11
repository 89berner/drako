import sys
import random
from datetime import datetime

from lib.Common.Exploration.Actions.Debug import DebugHosts
from lib.Common.Exploration.Actions.Debug import DebugServices
from lib.Common.Exploration.Actions.Debug import DebugListAllActions
from lib.Common.Exploration.Actions.Debug import DebugListMainActions
from lib.Common.Exploration.Actions.Debug import DebugStatus
from lib.Common.Exploration.Actions.Debug import DebugClear
from lib.Common.Exploration.Actions.Debug import DebugHelp
from lib.Common.Exploration.Actions.Debug import DebugExit
from lib.Common.Exploration.Actions.Debug import ListSessions
from lib.Common.Exploration.Actions.Debug import PredictAction

from lib.Common.Exploration.Actions.Metasploit import MetasploitDbNmap
from lib.Common.Exploration.Actions.Metasploit import DeleteMetasploitSessions
from lib.Common.Exploration.Actions.Metasploit import CreateMeterpreterListener
from lib.Common.Exploration.Actions.Metasploit import CreateMeterpreterFileServerAndListener
from lib.Common.Exploration.Actions.Metasploit import ExecuteMeterpreterShellCommandInMetasploitSession

from lib.Common.Exploration.Actions.Metasploit import ExecuteMeterpreterCommandInMetasploitSession
from lib.Common.Exploration.Actions.Metasploit import UpgradeMetasploitSession

# from lib.Common.Exploration.Actions.Custom import EternalBlueExploit
from lib.Common.Exploration.Actions.Custom import APPhpRCE

import lib.Common.Utils.Log as Log
import lib.Common.Utils.Constants as Constants

this = sys.modules[__name__]
this.client = None

class Actions:
    def __init__(self, environment=None):
        self.environment = environment
        # Environment might not be set when an action does not need execution
        if environment is not None:
            Log.logger.debug("Starting to initialize Actions object WITH environment SET..")
        else:
            Log.logger.debug("Starting to initialize Actions object WITHOUT environment SET..")

        # creating action map
        self.actions_map = {
            "DEBUG": {
                "services":    DebugServices(environment, "services"),
                "hosts":       DebugHosts(environment, "hosts"),
                "all_actions": DebugListAllActions(environment, "all_actions"),
                "actions":     DebugListMainActions(environment, "actions"),
                "status":      DebugStatus(environment, "status"),
                "state":       DebugStatus(environment, "status"),
                "clear":       DebugClear(environment, "clear"),
                "help":        DebugHelp(environment, "help"),
                "exit":        DebugExit(environment, "exit"),
                "predict":     PredictAction(environment, "predict")
            },
            "NETWORK": {
                "CUSTOM": {
                    "db_nmap":         MetasploitDbNmap(environment, "db_nmap"),
                    "delete_sessions": DeleteMetasploitSessions(environment, "delete_sessions"),
                    "sessions":        ListSessions(environment, "sessions"),
                    # "eternalblue":     EternalBlueExploit(environment, "eternalblue"),
                    "fileserver_and_metasploitlistener": CreateMeterpreterFileServerAndListener(environment, "fileserver_and_metasploitlistener"),
                    "apphp_exploit":      APPhpRCE(environment, "apphp_exploit"),
                    "metasploitlistener": CreateMeterpreterListener(environment, "metasploitlistener"),
                },
                "METASPLOIT": {
                    "EXPLOIT": {},
                    "AUXILIARY": {},
                },
            },
            "PRIVESC": {
                "CUSTOM": {
                    # DISABLED SINCE IT DOES NOT WORK PROPERLY: TODO 
                    # "execute_meterpreter_command_in_session":      ExecuteMeterpreterCommandInMetasploitSession(environment, "execute_meterpreter_command_in_session"),
                    # "execute_meterpretershell_command_in_session": ExecuteMeterpreterShellCommandInMetasploitSession(environment, "execute_meterpretershell_command_in_session"),
                    "upgrade_metasploit_session":                  UpgradeMetasploitSession(environment, "upgrade_metasploit_session")
                },
                "METASPLOIT": {
                    "POST": {},
                    "EXPLOIT": {},
                },
            },
            "WEB": {
                "CUSTOM": {},
            },
        }

    def load_metasploit_actions(self, metasploit_client = None):
        from lib.Common.Exploration.Metasploit.MetasploitStorage import MetasploitStorage
        # This loads the map of Metasploit actions from the FS and adds it to the actions_map
        Log.logger.info("Loading metasploit actions..")
        metasploit_storage    = MetasploitStorage(self.environment, metasploit_client)
        metasploit_actions, _ = metasploit_storage.get_stored_metasploit_map_and_build_actions()

        # add all metasploit actions created
        for metasploit_space in ['AUXILIARY']:
            for metasploit_action in metasploit_actions[metasploit_space]:
                self.actions_map[Constants.GAME_TYPE_NETWORK]["METASPLOIT"][metasploit_space][metasploit_action] = metasploit_actions[metasploit_space][metasploit_action]

        for metasploit_space in ['EXPLOIT']:
            for metasploit_action in metasploit_actions[metasploit_space]:
                action_options_picked = metasploit_actions[metasploit_space][metasploit_action].get_options()

                # HERE WE CHECK IF THIS IS AN EXPLOIT AIMING AT A SESSION OR AS A NETWORK
                if ("RHOST" not in action_options_picked and "RHOSTS" not in action_options_picked) or "SESSION" in action_options_picked:
                    self.actions_map[Constants.GAME_TYPE_PRIVESC]["METASPLOIT"][metasploit_space][metasploit_action] = metasploit_actions[metasploit_space][metasploit_action]
                    # Log.logger.debug(f"Loaded in privesc: {metasploit_action}")
                else:
                    self.actions_map[Constants.GAME_TYPE_NETWORK]["METASPLOIT"][metasploit_space][metasploit_action] = metasploit_actions[metasploit_space][metasploit_action]

        for metasploit_action in metasploit_actions["POST"]:
            self.actions_map[Constants.GAME_TYPE_PRIVESC]["METASPLOIT"]["POST"][metasploit_action] = metasploit_actions["POST"][metasploit_action]

        # Log.logger.debug(self.actions_map["PRIVESC"])

    def get_action(self, game_type, action_name):
        all_actions_map = self.get_all_actions(game_type)
        if action_name in all_actions_map:
            return all_actions_map[action_name]
        else:
            return None

    def get_missing_mandatory_options(self, game_type, action_name, already_set_options):
        return self.get_missing_options(game_type, action_name, already_set_options, "mandatory")

    def get_missing_optional_options(self, game_type, action_name, already_set_options):
        return self.get_missing_options(game_type, action_name, already_set_options, "optional")

    def get_all_options(self, game_type, action_name):
        action = self.get_action(game_type, action_name)
        return action.get_options()

    def get_action_type(self, game_type, action_name):
        action = self.get_action(game_type, action_name)
        return action.action_type

    def get_missing_options(self, game_type, action_name, already_set_options, is_required):
        # Log.logger.debug("Will try to find action of game_type %s and name %s" % (game_type, action_name))
        action = self.get_action(game_type, action_name)
        if action is None:
            # Log.logger.info(self.actions_map[game_type]["METASPLOIT"]["AUXILIARY"].keys())
            # Log.logger.info(len(self.actions_map[game_type]["METASPLOIT"]["AUXILIARY"].keys()))
            raise ValueError(f"Unable to find action {action_name} for game_type {game_type}")

        action_options = action.get_options()
        # Log.logger.debug(action_options)

        missing_options = {}
        for option in action_options:
            option_data = action_options[option]

            if option not in already_set_options:
                if is_required == "mandatory" and option_data["required"] == "yes":
                    missing_options[option] = option_data
                elif is_required == "optional" and option_data["required"] == "no":
                    missing_options[option] = option_data
                elif is_required is None:
                    missing_options[option] = option_data

        return missing_options

    def get_all_actions(self, game_type=None):
        all_actions = self._get_all_actions_map(game_type)
        return all_actions

    def get_main_actions(self):
        main_actions = self._get_main_actions_map()
        return list(main_actions.keys())

    def get_seeded_random_actions(self, game_type, seed, amount):
        random.seed(seed)
        actions = self._get_random_actions(game_type, amount)
        random.seed(datetime.now())

        return actions

    def _get_all_actions_map(self, game_type=None):
        # Log.logger.debug("Getting all game actions..")
        all_actions = self._get_main_actions_map(game_type)
        # Log.logger.debug(all_actions)
        if game_type is None:
            game_type = self.environment.get_current_game_type()

        # Log.logger.debug(self.actions_map[game_type])
        for action_space in self.actions_map[game_type]["METASPLOIT"]:
            for action_name in self.actions_map[game_type]["METASPLOIT"][action_space]:
                all_actions[action_name] = self.actions_map[game_type]["METASPLOIT"][action_space][action_name]
        # Log.logger.debug(all_actions)

        return all_actions

    def _get_main_actions_map(self, game_type=None):
        if game_type is None:
            game_type = self.environment.get_current_game_type()

        main_actions = {}
        for action_name in self.actions_map["DEBUG"]:
            main_actions[action_name] = self.actions_map["DEBUG"][action_name]

        for action_name in self.actions_map[game_type]["CUSTOM"]:
            main_actions[action_name] = self.actions_map[game_type]["CUSTOM"][action_name]

        return main_actions

    def _get_random_actions(self, game_type, amount):
        actions_picked = []

        all_actions = list(self.get_all_actions(game_type).keys())
        if amount > len(all_actions):
            amount = len(all_actions)

        # Log.logger.debug("Will now sample %d actions" % amount)
        actions_sampled = random.sample(all_actions, amount)
        # Log.logger.debug("Actions sampled are:")
        # Log.logger.debug(actions_sampled)
        for action_name_picked in actions_sampled:
            action_func           = self.get_action(game_type, action_name_picked)
            action_options_picked = action_func.get_options()
            # we skip any action that does not have rhosts or sesions
            # Log.logger.debug(action_func.is_debug())

            if action_func.is_debug():  # DEBUG ACTIONS ARE NOT FOR AUTOMATED AGENTS
                # Log.logger.debug("Skipping action %s since its debug" % action_name_picked)
                pass
            else:
                actions_picked.append(action_name_picked)

        return actions_picked

def initialize(environment=None):
    if this.client is None:
        Log.logger.info("Initializing Actions..")
        this.client = Actions(environment)
    else:
        Log.logger.warning("Skipping initialization of Actions client since its already initialized")
