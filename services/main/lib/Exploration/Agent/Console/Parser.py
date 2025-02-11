import lib.Exploration.Agent.Console.Console as Console
from lib.Common.Exploration.Actions.Data import ActionRecommendation
import lib.Common.Utils.Log as Log
import lib.Common.Exploration.Actions as Actions
import lib.Common.Recommendation.PredictionRequest as PredictionRequest

CLEAN_STATE                   = 0
COLLECTING_OPTIONS            = 1
ACTIONS_AND_OPTIONS_COLLECTED = 2

### TEMPLATE COMMENTS
"""
Report Loot to the database
Mandatory Arguments:
- path : the filesystem path to the Loot
- type : the type of Loot
- ltype : the same as 'type', not required if 'type' is specified.
Optional Keyword Arguments:
- host : an IP address or a Host object to associate with this Note
- ctype : the content type of the loot, e.g. 'text/plain'
- content_type : same as 'ctype'.
- service : a service to associate Loot with.
- name : a name to associate with this Loot.
- info : additional information about this Loot.
- data : the data within the Loot.
"""

class Parser:
    def __init__(self, agent, environment, agent_options, playbook, episode_id):
        self.agent         = agent
        self.environment   = environment
        self.playbook      = playbook
        self.action_source = "PARSER"
        self.action_extra  = agent_options
        self.action_reason = "DECIDED_BY_SCRIPT"

        self.reset_command_state()

        if playbook is not None:
            f = open(playbook,'r',encoding = 'utf-8')
            self.playbook_actions_and_options = f.readlines()
        elif episode_id is not None:
            self.playbook_actions_and_options = self.create_playbook_from_episode(episode_id)
            Log.logger.debug(self.playbook_actions_and_options)

    def create_playbook_from_episode(self, episode_id):
        raise ValueError(f"Will first request the data for episode:{episode_id}")

    def get_next_action_from_cli(self):
        """
            Get the next action and options by collecting them from the command line. 
        """

        while self.state != ACTIONS_AND_OPTIONS_COLLECTED:
            input_str = input(self.prompt).lower()
            self._process_input_line(input_str)

        options = self.options
        action  = self.action_name

        self.reset_command_state()

        action_source = "COMMAND_LINE"
        action_reason = "DECIDED_BY_CLIENT"

        action_recommendation = ActionRecommendation(action_source, action_reason, action, None, options, {}, None, self.action_extra)

        return action_recommendation

    def closed(self):
        if self.playbook is not None:
            return len(self.playbook_actions_and_options) == 0
        else:
            return False

    def get_next_action_from_playbook(self):
        """
            Get the next action and options by collecting information from a playbook.
            The playbook should already be configured for the parser.
        """

        while self.state != ACTIONS_AND_OPTIONS_COLLECTED:
            if len(self.playbook_actions_and_options) == 0:
                #error_message = "Process finished without executing because we ran out of actions to perform in the playbook!"
                #Console.raise_exception(error_message)
                Log.logger.debug("Exiting while loop since there are no more actions to execute")

                # set the exit action and options
                self.action_name    = "exit"
                self.action_options = {}

                break
            else:
                input_str = self.playbook_actions_and_options.pop(0).strip().lower()

            if input_str == "":
                continue
            # Deal with comments
            elif input_str.startswith("#") or input_str == "":
                #Console.print_input_prompt(input_str)
                Log.logger.debug("Ignoring comment: %s" % input_str)
            else:
                input_message = "%s%s" % (self.prompt, input_str) 
                Console.print_input_prompt(input_message)

                # Remove comments, anything after # will be ignored
                cleaned_input_str = input_str.split("#")[0]
                self._process_input_line(cleaned_input_str)
                if self.state == ACTIONS_AND_OPTIONS_COLLECTED:
                    Log.logger.debug("Exiting while loop since we finished executing an action")
                    break

        options = self.options
        action  = self.action_name

        self.reset_command_state()

        action_recommendation = ActionRecommendation(self.action_source, self.action_reason, action, None, options, {}, None, self.action_extra)

        return action_recommendation

    def reset_command_state(self):
        """
        Reset the command state at the start or after an action was executed
        """

        self.action_name    = ""
        self.options        = {}
        self.state          = CLEAN_STATE
        self.options_errors = {}
        self._set_prompt("> ")

    def _set_prompt(self, prompt):
        """
        Set the prompt of the shell

        Mandatory Arguments:
        - prompt : The prompt which will be written such as Action>
        """

        self.prompt = prompt

    def _options_as_str(self, all_options_data):
        """
        Turn the dictionary of options into a string for printing in the console

        Mandatory Arguments:
        - all_options_data : The dictionary of options
        """

        options_str = ""
        for option in all_options_data:
            if options_str != "":
                options_str += "\n"
            options_data = all_options_data[option]
            options_str += "%s:" % option

            if option in self.options:
                options_str += "\n\tValue: %s" % self.options[option]

            if 'default' in options_data:
                options_str += "\n\tDefault value: %s" % options_data["default"]
            options_str += "\n\tType: %s" % options_data['type']
            if 'range' in options_data:
                options_str += "\n\tRange from %s to %s" % (options_data['range'][0], options_data['range'][1])
            if 'allowed_values' in options_data:
                options_str += "\n\tAllowed values: %s" % (",".join(options_data['allowed_values']))
            if 'description' in options_data:
                options_str += "\n\tDescription: %s" % options_data['description']

        return options_str

    def _process_input_line(self, input_str):
        """
        Get the input string and performs the following steps
            1) Divide it into different commands by splitting on the ";" character
            2) Review any of these are Parser specific actions such as info / options / exit (they dont impact the state)
            3) Execute command in _process_command

        Mandatory Arguments:
            - input_str : The string of command or commands to execute
        """

        clean_input_str = input_str.split("#")[0] # We take everything before the comment sign
        commands = clean_input_str.split(";")
        for command in commands:
            # Pre process command
            command = self._pre_process_command(command).lstrip()

            if command == "exit":
                Console.print_to_console("Exit requested, stopping flow...")
                self.state = ACTIONS_AND_OPTIONS_COLLECTED
                self.environment.finish_episode("EXIT COMMAND")

                # set the exit action and options
                self.action_name    = "exit"
                self.action_options = {}
                return
            elif (command == "info" or command == "options") and self.action_name != "":
                Console.print_to_console("Information on current action: %s" % self.action_name)

                mandatory_options_data = Actions.client.get_missing_mandatory_options(self.environment.get_current_game_type(), self.action_name, self.options)
                missing_options_str    = self._options_as_str(mandatory_options_data)
                if missing_options_str != "":
                    print("=" * 50)
                    Console.print_to_console("Mandatory options missing\n%s\n" % missing_options_str)

                print("=" * 50)
                options_data     = self._get_current_options_data(only_defaults=False)
                options_data_str = self._options_as_str(options_data)
                Console.print_to_console("Options manually set\n%s\n" % options_data_str)

                print("=" * 50)
                options_data     = self._get_current_options_data(only_defaults=True)
                options_data_str = self._options_as_str(options_data)
                Console.print_to_console("Options set to default value\n%s\n" % options_data_str)

                optional_options_data = Actions.client.get_missing_optional_options(self.environment.get_current_game_type(), self.action_name, self.options)
                optional_options_str  = self._options_as_str(optional_options_data)
                if optional_options_str != "":
                    print("=" * 50)
                    Console.print_to_console("Optional options missing\n%s" % optional_options_str)

            elif command.startswith("set_game_type"):
                game_type = command.split()[1].upper()
                Log.logger.debug("Game_type to set => %s" % game_type)
                if game_type != "NETWORK" and game_type != "PRIVESC" and game_type != "WEB":
                    raise ValueError("Game type %s is not allowed" % game_type)
                else:
                    Log.logger.debug("Setting game type...")
                    self.environment.set_game_type(game_type)
                    Console.print_to_console("Game type now set to %s" % game_type)
            elif command.startswith("set_target"):
                target = command.split()[1]
                Log.logger.debug("Target to set => %s" % target)
                self.environment.set_target(target)
                self.agent.set_target(target)
                Console.print_to_console("Target now set to %s and Target IP to %s" % (self.environment.get_target(), self.environment.get_target_ip()))
            elif command != "":
                Log.logger.debug("Command executed: %s" % command)
                self._process_command(command)

    def _process_command(self, command):
        """
        Executes a command, there are two possible states:
            a) CLEAN_STATE: Initial state when no action is set
                a.1) It will prepare the environment
                a.2) It will check if any options are missing
                    a.2.1) If options are missing it will set the collecting_options state
                    a.2.2) If no options are missing it will run the action 
            b) COLLECTING_OPTIONS
                b.1) It will call the _collect_options method

        Mandatory Arguments:
            - command : Command to execute
        """
        # Log.logger.debug(" %s" % command)

        if self.state == CLEAN_STATE:
            Log.logger.debug("In clean state, will now get action to use")

            self.action_name = command
            self.state       = COLLECTING_OPTIONS
            self._set_prompt("action/%s> " % self.action_name)

            action = Actions.client.get_action(self.environment.get_current_game_type(), self.action_name)
            if action is not None:
                action_options = action.get_options()

                # If there are no options to collect, lets just execute it
                if len(action_options) == 0:
                    self._collect_options("run")

                for option_name in action_options:
                    if 'default' in action_options[option_name]:
                        self.options[option_name] = action_options[option_name]['default']
            else:
                raise NotImplementedError("Action %s was not found, this should not happen" % self.action_name)

        elif self.state == COLLECTING_OPTIONS:
            self._collect_options(command)
        else:
            raise NotImplementedError("Unknown state %s" % self.state)

    def _get_current_options_data(self, only_defaults):
        """
        Gets the options for the current action

        Mandatory Arguments:
            - only_defaults : It specifies if we only show default options or all of them
        """

        action = Actions.client.get_action(self.environment.get_current_game_type(), self.action_name)
        action_options  = action.get_options()

        options_data = {}
        for option in self.options:
            if option in action_options:
                if not only_defaults and ('default' not in action_options[option] or action_options[option]['default'] != self.options[option]):
                    options_data[option] = action_options[option]
                elif only_defaults and ('default' in action_options[option] and action_options[option]['default'] == self.options[option]):
                    options_data[option] = action_options[option]

        return options_data

    def _collect_options(self, command):
        if command == "run":
            missing_parameters = Actions.client.get_missing_mandatory_options(self.environment.get_current_game_type(), self.action_name, self.options)
            if len(missing_parameters) > 0:
                Console.print_to_console("[-] You need to specify the following mandatory parameters: %s" % ",".join(missing_parameters.keys()), "warning")
            else:
                self.state = ACTIONS_AND_OPTIONS_COLLECTED
        elif command.startswith("set "):
            options_data_str = " ".join(command.split("set ")[1:])
            options_data     = options_data_str.split(" ")
            option_key       = options_data[0].upper()
            option_value     = " ".join(options_data[1:])

            self.options[option_key] = option_value
            # Log.logger.debug("set %s to value %s, now option keys are => %s" % (option_key, option_value, self.options))
        elif command == "set_default_game_options":
            result = PredictionRequest.request_options(self.environment, self.environment.target_ip, self.environment.current_state, self.action_name)

            action_options = result['action_options']
            #     "action_options":        action_options,
            #     "action_options_source": action_options_source,
            #     "option_errors":         option_errors,

            for option_name in action_options:
                option_value = action_options[option_name]
                if option_name in self.options:
                    Log.logger.warning(f"REPLACING {option_name} from {self.options[option_name]} to {option_value}")
                else:
                    Log.logger.debug(f"Will set {option_name} to {option_value}")

                self.options[option_name] = option_value

            Log.logger.debug(self.options)

        elif command == "back":
            Console.print_to_console("[*] Leaving...", "warning")
            self.reset_command_state()
        else:
            missing_mandatory_options = Actions.client.get_missing_mandatory_options(self.environment.get_current_game_type(), self.action_name, self.options)
            missing_parameters = ",".join(missing_mandatory_options.keys())
            
            Console.print_to_console("[-] Command %s not understood. Either exit, set the options needed (%s)" % (command, missing_parameters), "warning")

    def _pre_process_command(self, original_command):
        """
            Replaces particular templates with loaded variables
        :param original_command:
        :return:
        """
        if "<metasploit_session_id>" in original_command:
            metasploit_session_id = self.environment.get_newest_session_id()
            command = original_command.replace("<metasploit_session_id>", metasploit_session_id)
            Log.logger.debug("string replace with new metasploit id from %s => %s" % (original_command, command))
        elif "<revshell_port>" in original_command:
            revshell_port = self.environment.get_default_reverse_shell_port()
            command = original_command.replace("<revshell_port>", revshell_port)
            Log.logger.debug("string replace with REVSHELL_PORT from %s => %s" % (original_command, command))
        elif "<revshell_port_2>" in original_command:
            revshell_port_2 = self.environment.get_default_reverse_shell_port_2()
            command = original_command.replace("<revshell_port_2>", revshell_port_2)
            Log.logger.debug("string replace with REVSHELL_PORT_2 from %s => %s" % (original_command, command))
        elif "<srv_port>" in original_command:
            srv_port = self.environment.get_default_server_port()
            command = original_command.replace("<srv_port>", srv_port)
            Log.logger.debug("string replace with SRV_PORT from %s => %s" % (original_command, command))
        elif "<apache_port>" in original_command:
            apache_port = self.environment.get_default_apache_port()
            command = original_command.replace("<apache_port>", apache_port)
            Log.logger.debug("string replace with APACHE_PORT from %s => %s" % (original_command, command))
        elif "<local_ip>" in original_command:
            local_ip = self.environment.get_default_local_ip()
            command  = original_command.replace("<local_ip>", local_ip)
            Log.logger.debug("string replace with LOCAL_IP from %s => %s" % (original_command, command))
        else:
            command = original_command

        return command.strip()


