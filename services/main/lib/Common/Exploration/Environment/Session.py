import json
import lib.Common.Utils.Log as Log
import lib.Common.Utils as Utils
import lib.Common.Utils.Constants as Constants

class Session:
    def __init__(self, session_data = {}):
        if 'arch' in session_data:
            self.arch         = session_data['arch']
        else:
            self.arch = "unknown"

        if 'desc' in session_data:
            self.desc         = session_data['desc']
        else:
            self.desc = "unknown"

        if 'exploit_uuid' in session_data:
            self.exploit_uuid = session_data['exploit_uuid']
        else:
            self.exploit_uuid = "unknown"

        if 'info' in session_data:
            self.info         = session_data['info']
        else:
            self.info = "unknown"

        if 'session_host' in session_data:
            self.session_host = session_data['session_host']
        else:
            self.session_host = "unknown"

        if 'session_port' in session_data:
            self.session_port = session_data['session_port']
        else:
            self.session_port = "unknown"

        if 'target_host' in session_data:
            self.target_host  = session_data['target_host']
        else:
            self.target_host = "unknown"

        if 'tunnel_local' in session_data:
            self.tunnel_local = session_data['tunnel_local']
        else:
            self.tunnel_local = "unknown"

        if 'tunnel_peer' in session_data:
            self.tunnel_peer  = session_data['tunnel_peer']
        else:
            self.tunnel_peer = "unknown"

        if 'type' in session_data:
            self.type         = session_data['type']
        else:
            self.type = "unknown"

        if 'uuid' in session_data:
            self.uuid         = session_data['uuid']
        else:
            self.uuid = "unknown"

        if 'via_exploit' in session_data:
            self.via_exploit  = session_data['via_exploit']
        else:
            self.via_exploit = "unknown"

        if 'via_payload' in session_data:
            self.via_payload  = session_data['via_payload']
        else:
            self.via_payload = "unknown"

        if 'workspace' in session_data:
            self.workspace    = session_data['workspace']
        else:
            self.workspace = "unknown"

        if 'username' in session_data:
            self.username = session_data['username']
        else:
            self.username = "unknown"

        if 'user' in session_data:
            self.user = session_data['user']
        else:
            self.user = self.username

        if self.target_host == "" and self.session_host != "":
            self.target_host = self.session_host

        self.deduce_user_name()

    def username_is_unknown(self):
        if self.username == "unknown" or self.username == "":
            # Log.logger.debug(f"Username:{self.username} is unknown")
            return True
        else:
            # Log.logger.debug(f"Username:{self.username} is NOT unknown")
            return False

    def user_is_unknown(self):
        if self.user == "unknown" or self.user == "":
            return True
        else:
            return False

    # THIS COVERS BOTH USERNAME AND USER
    def no_user_is_known(self):
        if self.username_is_unknown() and self.user_is_unknown():
            return True
        else:
            return False

    def deduce_user_name(self):
        # Log.logger.debug(f"Will try to deduce username with info being {self.info}")

        if self.username_is_unknown() and "\\" in self.info:
            self.user = self.info.split("\\")[1].split(" ")[0]

        # Log.logger.debug([self.username_is_unknown(), '@' in self.info, 'uid=' in self.info, 'gid=' in self.info])
        if self.username_is_unknown() and '@' in self.info and 'uid=' in self.info and 'gid=' in self.info:
            # Log.logger.debug("Will use info for placing user")
            self.user = self.info.split("@")[0].split(" ")[0]
            # Log.logger.debug(f"Now user is {self.user}")

        if self.user_is_unknown() and not self.username_is_unknown():
            self.user = self.username

        if self.username_is_unknown() and not self.user_is_unknown():
            self.username = self.user

        # Log.logger.debug(f"Now username is: {self.username} and user: {self.user}")

    def get_dict(self):
        return {
            "arch":         self.arch,
            "desc":         self.desc,
            "exploit_uuid": self.exploit_uuid,
            "info":         self.info,
            "session_host": self.session_host,
            "session_port": self.session_port,
            "target_host":  self.target_host,
            "tunnel_local": self.tunnel_local,
            "tunnel_peer":  self.tunnel_peer,
            "type":         self.type,
            "username":     self.username,
            "user":         self.user,
            "uuid":         self.uuid,
            "via_exploit":  self.via_exploit,
            "via_payload":  self.via_payload,
            "workspace":    self.workspace,
        }

    def get_json(self):
        return Utils.dump_json(self.get_dict())

    def set_username(self, username):
        self.username = username

    def set_user(self, user):
        self.user = user

    def is_super_user_session(self):
        if self.username.lower() in Constants.SUPER_USERS_LIST:
            return True
        else:
            return False
