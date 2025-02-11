import pickle
import random
import string
import sys
import time
import traceback

from lib.Common.Utils import Log as Log
from lib.Common.Exploration.Environment.Session import Session


DB_NMAP_TIMEOUT = 600
ACTION_DEFAULT_TIMEOUT = 300
ACTION_TIMEOUTS = {
    "auxiliary/scanner/portscan/tcp": 1200,
    "auxiliary/scanner/portscan/ack": 1200,
    "auxiliary/scanner/portscan/syn": 1200,
    "db_nmap":                        DB_NMAP_TIMEOUT, # this is not being used
}

class Metasploit:
    def __init__(self, environment):
        # LOAD METASPLOIT
        Log.logger.debug("Initializing metasploit..")
        self.environment = environment
        # Log.logger.debug(environment)

        self.init_client()

        if self.environment.environment_type == "NETWORK" and not self.environment.inside_a_container():
            Log.logger.info("Will delete all metasploit data in the database..")
            self.delete_all_metasploit_data()

        Log.logger.debug("[IMPORTANT] Finished setting up metasploit..")

    def init_client(self):
        from pymetasploit3.msfrpc import MsfRpcClient

        # ONLY SETUP IF ITS NOT A LEARNER TO AVOID WASTING TIME
        msfrpc_port = self.environment.get_msfrpc_port()
        Log.logger.debug("Connecting with msfrpc port %s" % msfrpc_port)
        self.client = MsfRpcClient('Amdspon200ss11a', port=msfrpc_port)

        postgresql_port = self.environment.get_postgressql_port()
        Log.logger.debug("Connecting with postgresql port %s" % postgresql_port)
        result = self.client.db.connect(username='msf', database='msf', host='127.0.0.1', password='1PostGresPass2',
                               port=postgresql_port)
        time.sleep(1)

        self.workspace_name = self._get_random_string(6)
        Log.logger.debug("Using workspace_name %s" % self.workspace_name)
        self.client.db.workspaces.add(self.workspace_name)
        self.client.db.workspaces.set(self.workspace_name)

        self.console_id = self.client.consoles.console().cid
        Log.logger.debug("Using console_id %s" % self.console_id)
        self.console    = self.client.consoles.console(self.console_id)

        # Clean buffer
        self.console.read()
        self.console.read()

        # Checking workspace is set properly
        try:
            self.client.db.workspaces.workspace().hosts.list
        except KeyError as e:
            Log.logger.error("[IMPORTANT] Error with database connection!")
            raise e
        Log.logger.debug("Workspace is set properly!")

        Log.logger.info("Now setting debug mode")
        response = self._write_to_metasploit("setg LogLevel 5\n")
        Log.logger.debug(response)


    def gather_current_metasploit_information(self):
        default_hosts    = self.client.db.workspaces.workspace().hosts.list
        default_services = self.client.db.workspaces.workspace().services.list
        if len(default_hosts) > 0 or len(default_services) > 0:
            Log.logger.warn("[IMPORTANT_WARNING] FOUND DATA IN DEFAULT THAT SHOULD NOT EXIST!")
            Log.logger.warn([default_hosts, default_services])

        data = {
            'hosts_list':    self.client.db.workspaces.workspace(self.workspace_name).hosts.list,
            'services_list': self.client.db.workspaces.workspace(self.workspace_name).services.list,
            'sessions_map':  self.get_current_metasploit_sessions(),
            'jobs_list':     self._get_workspace_jobs(),
            'vulns':         self.client.db.workspaces.workspace(self.workspace_name).vulns.list
        }

        # Log.logger.debug(["services", self.workspace_name, self.client.db.workspaces.workspace(self.workspace_name).services.list])

        events_data = self.client.db.workspaces.workspace(self.workspace_name).events.list
        data['events'] = []
        for event in events_data:
            if (event["name"] == "module_complete" or event["name"] == "ui_command" or event["name"] == "ui_start" or
                    event["name"] == "ui_stop" or event["name"] == "module_run"):
                continue
            data['events'].append(event)

        data['notes'] = self.client.db.workspaces.workspace(self.workspace_name).notes.list

        return data

    def get_current_metasploit_sessions(self):
        sessions_list = {}
        for session_id in self.client.sessions.list:
            if self.client.sessions.list[session_id]['workspace'] == self.workspace_name:
                sessions_list[session_id] = Session(self.client.sessions.list[session_id]).get_dict() #Ensure same session structure

        # Log.logger.debug(["self.client.sessions.list", self.client.sessions.list])
        # Log.logger.debug(["sessions_list", sessions_list])

        return sessions_list

    def terminate_running_jobs_for_workspace(self):
        """
            Goes through all jobs and only stops the ones for this workspace
        :return: Nothing
        """
        jobs_list = self.client.jobs.list
        Log.logger.debug("Will decide if I should delete any of these jobs: %s" % jobs_list)
        for job_id in jobs_list:
            kill_job = True
            job_data = self.client.jobs.info(job_id)
            # Log.logger.debug([job_id, job_data])
            workspace_name = job_data['datastore']['WORKSPACE']
            if workspace_name == self.workspace_name:
                job_name = job_data['name']
                if job_name.startswith("Exploit: "):
                    Log.logger.debug("Will check if we should keep the job %s with name %s" % (job_id, job_name))
                    exploit_name_parts = job_name.split("Exploit: ")
                    if len(exploit_name_parts) == 2:
                        exploit_name = exploit_name_parts[1]
                        possible_exploit_path = "exploit/" + exploit_name
                        sessions =  self.get_current_metasploit_sessions()
                        for session_id in sessions:
                            Log.logger.debug(["REMOVE_DEBUG_STATEMENT", job_id, exploit_name, possible_exploit_path, sessions[session_id]])
                            if sessions[session_id]["via_exploit"] == possible_exploit_path:
                                kill_job = False
                                break
                    else:
                        Log.logger.Error("WE TRIED TO SPLIT THE EXPLOIT JOB BUT SOMETHING WENT WRONG, REVIEW THIS!")
        
                # Log.logger.debug([job_id, job_data])

                if kill_job:
                    Log.logger.warn("[IMPORTANT_WARNING] I found a job %s (%s) in my workspace %s, will delete it!" % (job_id, job_data['name'], workspace_name))
                    self.client.jobs.stop(job_id)
                else:
                    Log.logger.debug("We are not killing the job %s since it matches a running session exploit", job_id)
            else:
                Log.logger.warn("Ignoring job %s since its not mine but belongs to workspace %s" % (job_id, workspace_name))
        Log.logger.debug("Finished terminating running jobs")

    def perform_execution(self, action_type, command, options, time_for_timeout=ACTION_DEFAULT_TIMEOUT):
        """
        Handle a metasploit command.
        Mandatory Arguments:
        - command : the command to execute and name of session.
        - options : key value pairs to set as options.
        """

        # stats = self.client.core.stats
        # Log.logger.debug("Stats => %s" % stats)
        # threads = self.client.core.threads
        # Log.logger.debug("Threads => %s" % threads)

        # FIRST CHECK DB CONNECTION
        # data_to_write = "db_status\n"
        # response = self._write_to_metasploit(data_to_write, '[*] Connected to msf. Connection type: postgresql.', exploit_action=False, time_for_timeout=time_for_timeout)
        # db_status = self.client.db.status
        # Log.logger.debug("(1) DB STATUS IS => %s" % db_status)

        # TREAT DB_NMAP AS AN EXCEPTION
        if command.startswith("db_nmap") or command.startswith("sessions -k "):
            response = self._write_to_metasploit(command + "\n", exploit_action=False, time_for_timeout=DB_NMAP_TIMEOUT)
        elif command.startswith("sessions -u "):
            response = self._write_to_metasploit(f"setg LHOST {self.environment.get_default_local_ip()}\n", exploit_action=False, time_for_timeout=time_for_timeout)
            Log.logger.debug(response)
            response = self._write_to_metasploit(f"setg LPORT {self.environment.get_default_reverse_shell_port_2()}\n", exploit_action=False, time_for_timeout=time_for_timeout)
            Log.logger.debug(response)
            response = self._write_to_metasploit(command + "\n", exploit_action=False, time_for_timeout=time_for_timeout)
            Log.logger.debug(response)
            # TODO: Unset Global var?
        else:
            tries = 1
            while True:
                try:
                    WRITE_EACH_COMMAND_ONE_AT_A_TIME = False # This allows us to execute all options simultaneously

                    # This replaces the _single_command module since it got too many "Matching modules" as a response
                    data_to_write = command + "\n"
                    response = self._write_to_metasploit(data_to_write, exploit_action=False, time_for_timeout=60)

                    # Sometimes we fail to load a module, this could be because there is a mismatch between modules in agent and learner
                    if 'Failed to load module: ' in response and not '[*] Using ' in response:
                        raise ValueError(response)

                    # Option to force exploits even if the check says it should not be possible
                    # options["ForceExploit"] = "true"
                    # TODO: REVIEW
                    options["AutoCheck"] = "False"

                    integrated_command = ""
                    integrated_expected_response  = ""
                    for key in options:
                        if key != "DELAY_TO_OBSERVE":
                            data_to_write     = "set %s %s\n" % (key, options[key])
                            expected_response = "%s => %s" % (key, options[key])
                            if WRITE_EACH_COMMAND_ONE_AT_A_TIME:
                                self._write_to_metasploit(data_to_write, expected_response=expected_response, exploit_action=False, time_for_timeout=20)
                            else:
                                integrated_command += data_to_write 
                                integrated_expected_response += expected_response + "\n"
                    
                    data_to_write     = "set WORKSPACE %s\n" % self.workspace_name
                    expected_response = "WORKSPACE => %s" % self.workspace_name
                    if WRITE_EACH_COMMAND_ONE_AT_A_TIME:
                        self._write_to_metasploit(data_to_write, expected_response=expected_response, exploit_action=False, time_for_timeout=20)
                    else:
                        integrated_command += data_to_write
                        # integrated_expected_response += expected_response

                    # ADDITIONAL TIMEOUT FOR POST EXPLOITS
                    data_to_write = "set Powershell::Post::timeout 300\n"
                    if WRITE_EACH_COMMAND_ONE_AT_A_TIME:
                        self._write_to_metasploit(data_to_write, exploit_action=False, time_for_timeout=20)
                    else:
                        integrated_command += data_to_write
                        # integrated_expected_response += expected_response

                    if not WRITE_EACH_COMMAND_ONE_AT_A_TIME:
                        self._write_to_metasploit(integrated_command, expected_response=integrated_expected_response, exploit_action=False, time_for_timeout=60)

                    break #breaking since it worked properly

                except SystemError as error:
                    # This error happened setting options, so lets assume its a connection error, reconnect and retry
                    if tries < 5:
                        Log.logger.error("Error while trying to run command, will retry: %s" % str(error))
                        self.init_client()
                        tries += 1
                    else:
                        raise error

                except BaseException as error:
                    raise error

            ########## Handle custom timeouts ###################
            if command.startswith("use "):
                action_name = command.split("use ")[1]
                if action_name in ACTION_TIMEOUTS:
                    time_for_timeout = ACTION_TIMEOUTS[action_name]
                    Log.logger.debug("Setting timeout of action to %d" % time_for_timeout)

            if action_type == "exploit":
                time_for_timeout = 100 # Based on checking time taken

            Log.logger.debug("Using as timeout %d" % time_for_timeout)

            # db_status = self.client.db.status
            # Log.logger.debug("(2) DB STATUS IS => %s" % db_status)

            if action_type == "exploit":
                data_to_write = "exploit -j\n"
                response = self._write_to_metasploit(data_to_write, exploit_action=True, time_for_timeout=time_for_timeout)
            else:
                data_to_write = "run\n"
                response = self._write_to_metasploit(data_to_write, exploit_action=False, time_for_timeout=time_for_timeout)

        # Log.logger.debug(data_to_write)

        # db_status = self.client.db.status
        # Log.logger.debug("(3) DB STATUS IS => %s" % db_status)

        extra_response = self._read_until_finished(time_for_timeout=time_for_timeout)
        if extra_response != "":
            Log.logger.debug("Extra response => %s" % extra_response)
            response += extra_response

        if command == "use exploit/multi/handler":
            Log.logger.info("Sleeping extra 10 seconds due to waiting for session to arrive")
            time.sleep(10)

        # Lets check if the command is entering a particular path for us to leave
        # if command.startswith("use "):
        #     self.set_background_and_go_all_the_way_back()

        # PRINT JOBS
        current_jobs = self._get_workspace_jobs()
        Log.logger.debug(current_jobs)

        return response

    def get_newest_session_id(self):
        if len(self.get_current_metasploit_sessions()) > 0:
            return max(self.get_current_metasploit_sessions().keys())
        else:
            raise NotImplementedError("No sessions available!")

    def delete_all_metasploit_data(self):
        self.clean_active_sessions()

    def clean_active_sessions(self):
        Log.logger.debug("Cleaning sessions")
        sessions = self.get_current_metasploit_sessions()
        for session_id in sessions:
            self.perform_execution("auxiliary", "sessions -k %s" % session_id, {}, time_for_timeout=30)
            Log.logger.info("Removing session %s" % session_id)

    def _read_until_finished(self, sleep_after_reading=True, time_for_timeout=ACTION_DEFAULT_TIMEOUT, extra_reads=False):
        if sleep_after_reading:
            time.sleep(1)
        response = ""
        data = self.console.read()
        # print(data)
        response += data['data']
        # Log.logger.debug(data)

        # Log.logger.debug("Will first wait 10 seconds to see if there is any more data coming in")
        TIME_TO_SLEEP_FOR_EXTRA_READS = 20
        more_data_was_available = False
        if extra_reads:
            # Log.logger.debug("Doing an extra read..")
            time.sleep(TIME_TO_SLEEP_FOR_EXTRA_READS)
            data = self.console.read()
            if len(data['data']) > 0:
                response += data['data']
                more_data_was_available = True
                Log.logger.debug("More data found: %s" % data['data'])

        start_time = time.time()
        while more_data_was_available or data['busy']:
            more_data_was_available = False

            time.sleep(1)
            # Log.logger.debug("Waiting 1 more second while console is busy...")
            data = self.console.read()
            # print(data)
            response += data['data']

            if extra_reads:
                # Log.logger.debug("Doing an extra read..")
                time.sleep(TIME_TO_SLEEP_FOR_EXTRA_READS)
                data = self.console.read()
                if len(data['data']) > 0:
                    response += data['data']
                    more_data_was_available = True
                    Log.logger.debug("More data found: %s" % data['data'])

            if (time.time() > start_time + time_for_timeout and data['busy']) or (time.time() > start_time + time_for_timeout * 1.5):
                raise SystemError(
                    "Timeout waiting for console to stop being busy after %d seconds! I got until now response:\n%s" % (
                        time_for_timeout, response))

        # print("Finished!")
        MAX_RESPONSE_SIZE = 50000
        return response.strip()[:MAX_RESPONSE_SIZE]

    def _set_background_and_go_all_the_way_back(self):

        # place anything in background
        # self.console.write("bg" + "\n")

        # go all the way back
        self.console.write("back" + "\n")
        self.console.write("back" + "\n")
        self.console.write("back" + "\n")
        self.console.write("back" + "\n")

    def _write_to_metasploit(self, data_to_write, expected_response=None, time_for_timeout=10, exploit_action=False, sleep_after_reading=True):
        # if string == "exploit -j":
        #     time.sleep(1)
        # else:
        # time.sleep(0.1)
        start_time = time.time()

        Log.logger.debug(">>>> %s [with timeout %d]" % (data_to_write.strip(), time_for_timeout))
        self.console.write(data_to_write)

        extra_reads = False
        # if string == "exploit -j":
        if exploit_action:
            extra_reads = True
            time.sleep(20)
        else:
            time.sleep(1)

        response = self._read_until_finished(time_for_timeout=time_for_timeout, sleep_after_reading=sleep_after_reading, extra_reads=extra_reads)

        if expected_response is not None:
            # Make sure to make both lowercase for comparisson
            while expected_response.lower() not in response.lower():
                response += self._read_until_finished(time_for_timeout=time_for_timeout, sleep_after_reading=sleep_after_reading, extra_reads=extra_reads)
                if expected_response.lower() not in response.lower() and time.time() - start_time > time_for_timeout:
                    # we timed out, lets reconnect just in case
                    # self.init_client()
                    raise SystemError("Timed out after waiting for %d seconds for string: \"%s\" and got instead: \"%s\"" % (time_for_timeout, expected_response, response))
                else:
                    time.sleep(1) #lets wait a second

        time.sleep(1)
        Log.logger.debug("Metasploit response => %s" % response)

        return response

    def _get_workspace_jobs(self):
        workspace_jobs_list = {}
        jobs_list = self.client.jobs.list
        for job_id in jobs_list:
            job_data       = self.client.jobs.info(job_id)
            workspace_name = job_data['datastore']['WORKSPACE']
            if workspace_name == self.workspace_name:
                workspace_jobs_list[job_id] = jobs_list[job_id]

        # Log.logger.debug("Got workspace jobs: %s" % workspace_jobs_list)
        return workspace_jobs_list

    def _get_random_string(self, length):
        letters    = string.ascii_lowercase
        result_str = ''.join(random.sample(letters, length))
        return result_str