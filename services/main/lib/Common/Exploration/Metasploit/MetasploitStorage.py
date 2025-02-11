import traceback
import lib.Common.Utils.Log as Log
import pickle
import os

import lib.Common.Utils.Constants                as Constants
import lib.Common.Exploration.Actions.Metasploit as MetasploitAction

class MetasploitStorage:
    def __init__(self, environment, metasploit_client = None):
        self.environment       = environment
        self.metasploit_client = metasploit_client

    def regenerate_actions(self):
        Log.logger.warn("Regenerating actions, will start creating them and then copy it to %s" % Constants.METASPLOIT_FILE_PATH)
        self.generate_and_save_metasploit_actions_to_fs()
        Log.logger.warn("Finished loading metasploit actions!")

        Log.logger.warn("Will now copy the actions to /share/")
        os.system("cp %s /share/" % Constants.METASPLOIT_FILE_PATH)
        Log.logger.warn("Finished copying the new metasploit actions file, now we should verify it works by loading it")

    def generate_and_save_metasploit_actions_to_fs(self):
        Log.logger.debug("Collecting metasploit actions")
        metasploit_actions = self._generate_actions_map_from_metasploit()

        Log.logger.debug("Storing metasploit actions!")
        pickle.dump(metasploit_actions, open(Constants.METASPLOIT_FILE_PATH, "wb"))
        return True

    def _generate_actions_map_from_metasploit(self):
        metasploit_actions = {
            "AUXILIARY": {},
            "EXPLOIT":   {},
            "POST":      {},
            "PAYLOADS":  [],
        }

        Log.logger.debug("Loading all payloads")
        metasploit_actions["PAYLOADS"] = list(self.metasploit_client.modules.payloads)

        # setting up metasploit actions
        for exploit_long_name in self.metasploit_client.modules.exploits:
            Log.logger.debug("Loading exploit: %s" % exploit_long_name)
            # add some delay to avoid errors?
            self._add_metasploit_action_to_map(metasploit_actions, "EXPLOIT", exploit_long_name)

        for auxiliary_long_name in self.metasploit_client.modules.auxiliary:
            # add some delay to avoid errors?
            if not auxiliary_long_name.startswith("dos/"):
                Log.logger.debug("Loading auxiliary: %s" % auxiliary_long_name)
                self._add_metasploit_action_to_map(metasploit_actions, "AUXILIARY", auxiliary_long_name)
            else:
                Log.logger.debug("Skipping module %s since its related to a denial of service" % auxiliary_long_name)

        for post_long_name in self.metasploit_client.modules.post:
            Log.logger.debug("Loading post modules: %s" % post_long_name)
            # add some delay to avoid errors?
            self._add_metasploit_action_to_map(metasploit_actions, "POST", post_long_name)

        return metasploit_actions

    def get_stored_metasploit_map_and_build_actions(self):
        metasploit_raw_data = self._read_metasploit_actions_from_fs()

        if metasploit_raw_data is None:
            return None, None

        metasploit_actions = self._build_metasploit_actions(metasploit_raw_data)
        metasploit_payloads = metasploit_raw_data["PAYLOADS"]

        return metasploit_actions, metasploit_payloads

    def _read_metasploit_actions_from_fs(self):
        try:
            Log.logger.debug("Trying to load file %s" % Constants.METASPLOIT_FILE_PATH)
            return pickle.load(open(Constants.METASPLOIT_FILE_PATH, "rb"))
        except:
            Log.logger.error("ERROR: %s" % traceback.format_exc())
            return None

    def _add_metasploit_action_to_map(self, metasploit_actions, action_space, action_long_name):
        if action_long_name == "linux/misc/saltstack_salt_unauth_rce":
            Log.logger.debug("skipping action linux/misc/saltstack_salt_unauth_rce..")
            return

        try:
            action = self.metasploit_client.modules.use(action_space.lower(), action_long_name)
            # Log.logger.debug("Loading action %s" % action)

            metasploit_actions[action_space][action_long_name] = {
                "all_options":       list(map(lambda x: x.upper(), action.options)),
                "mandatory_options": list(map(lambda x: x.upper(), action.missing_required)),
            }

            if action_space == "EXPLOIT":
                # metasploit_actions[action_space][action_long_name]["target_payloads"] = list(map(lambda x:x.upper(), action.targetpayloads()))
                metasploit_actions[action_space][action_long_name]["payloads"] = list(action.payloads)
                metasploit_actions[action_space][action_long_name]["targets"] = {k: v.upper() for k, v in action.targets.items()}

                # Log.logger.debug(metasploit_actions[action_space][action_long_name])

            if 'CHECKMODULE' in metasploit_actions[action_space][action_long_name]['mandatory_options']:
                metasploit_actions[action_space][action_long_name]['mandatory_options'].remove('CHECKMODULE')
            # Log.logger.debug(metasploit_actions[action_space][action_long_name])

            metasploit_actions[action_space][action_long_name]["options_information"] = {}
            for opt_name in action.options:
                if not isinstance(opt_name, bool):
                    metasploit_actions[action_space][action_long_name]["options_information"][opt_name] = action.optioninfo(opt_name)
        except:
            Log.logger.error("Error trying to load exploit: %s in action_space:%s => %s" % (
                action_long_name, action_space, traceback.format_exc()))

    def _build_metasploit_actions(self, metasploit_raw_data):
        if metasploit_raw_data is None:
            return None
        else:
            metasploit_actions = {}
            for action_type in ["EXPLOIT", "AUXILIARY", "POST"]:
                if action_type not in metasploit_actions:
                    metasploit_actions[action_type] = {}

                for action_name in metasploit_raw_data[action_type]:
                    # Log.logger.debug("Will format action_type %s and action %s" % (action_type, action_name))

                    action_data = metasploit_raw_data[action_type][action_name]

                    metasploit_action_name = "%s/%s" % (action_type.lower(), action_name)
                    metasploit_action = MetasploitAction.create_metasploit_action(self.environment, metasploit_action_name, action_type, action_data)

                    metasploit_actions[action_type][metasploit_action.action_name] = metasploit_action

            for key in metasploit_actions:
                Log.logger.debug("Loaded %d elements in %s" % (len(metasploit_actions[key]), key))

            return metasploit_actions