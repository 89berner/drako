import requests
import time
import re

import lib.Common.Utils.Log as Log
import lib.Common.Utils.Constants as Constants

SECONDS_IN_MINUTE=75 #60

#https://github.com/kulinacs/htb/blob/master/htb/__init__.py
class HTBVIP:
    """
    Hack the Box API Wrapper
    :attr api_key: API Key used for authenticated queries
    :attr user_agent: The User-Agent to be used with all requests
    """
    BASE_URL = 'https://www.hackthebox.eu/api'

    def __init__(self, user_agent='Python HTB Client 1.1.0'):
        self.api_key = HTB_API_KEY
        self.headers = {'User-Agent': user_agent}
        self.timeout = 180

    def _get(self, path: str) -> dict:
        """
        Helper function to get an API endpoint and validate the response
        :params self: the HTB object
        :params path: the path to get including leading forward slash
        :returns: the response dict from the endpoint
        """
        time.sleep(3)
        return requests.get(self.BASE_URL + path, headers=self.headers, timeout=self.timeout).json()

    def _post(self, path: str, data: dict = None) -> dict:
        """
        Helper function to get an API endpoint and validate the response
        :params self: the HTB object
        :params path: the path to get including leading forward slash
        :returns: the response dict from the endpoint
        """
        time.sleep(3)
        return requests.post(self.BASE_URL + path, data=data, headers=self.headers, timeout=self.timeout).json()

    def _auth(self, path: str) -> str:
        """
        Helper function to generate an authenticated URL
        :params self: HTB object in use
        :params path: string containing path to query
        :returns: path to authenticated query
        """
        return "{}?api_token={}".format(path, self.api_key)

    def connection_status(self) -> dict:
        """
        Return connection status information
        Success key seems to be behaving incorrectly
        :params self: HTB object in use
        :returns: connection_status dict
        """
        return requests.post(self.BASE_URL + self._auth('/users/htb/connection/status/'), headers=self.headers).json()

    def get_difficulties_map(self) -> dict:
        """
        Get all machines on the network
        :params self: HTB object in use
        :returns: machines dict
        """
        response = requests.get(self.BASE_URL + self._auth('/machines/difficulty/'), headers=self.headers).json()
        # print(response)

        difficulty_map = {}
        for machine in response:
            # print(machine)
            difficulty_ratings = machine['difficulty_ratings']
            total_votes  = sum(difficulty_ratings)
            total_amount = 0
            for counter in range (1,11):
                # print(counter)
                total_amount += counter * difficulty_ratings[counter - 1]
                # print(total_amount)

            if total_votes > 0:
                rating = total_amount/total_votes
                # print("Machine had %d votes with an average of %.2f" % (total_votes, rating))
                difficulty_map[machine['id']] = rating

        return difficulty_map

    def _get_machines(self):
        response = requests.get(self.BASE_URL + self._auth('/machines/get/all/'), headers=self.headers).json()

        return response

    def get_machines(self, target = None) -> dict:
        """
        Get all machines on the network IF THEY ARE RETIRED
        :params self: HTB object in use
        :returns: machines dict
        """
        parsed_machines = {}

        # ADD
        #BLACKLISTED_HACKTHEBOX_IPS_WITH_REWARD     = ["10.10.10.40", "10.10.10.4", "10.10.10.15", "10.10.10.14", "10.10.10.8", "10.10.10.3", "10.10.10.16"]
        BLACKLISTED_HACKTHEBOX_IPS_WITH_REWARD = []
        BLACKLISTED_HACKTHEBOX_IPS_WITHOUT_REWARD  = ["10.10.10.60", "10.10.10.56", "10.10.10.68", "10.10.10.37", "10.10.10.152", "10.10.10.95"]
        BLACKLISTED_HACKTHEBOX_IPS_WITHOUT_REWARD += ["10.10.10.5", "10.10.10.48", "10.10.10.7", "10.10.10.75", "10.10.10.198", "10.10.10.29"]
        BLACKLISTED_HACKTHEBOX_IPS_WITHOUT_REWARD += ["10.10.10.84", "10.10.10.85", "10.10.10.74", "10.10.10.11", "10.10.10.137", "10.10.10.79"]
        BLACKLISTED_HACKTHEBOX_IPS_WITHOUT_REWARD += ["10.10.10.10", "10.10.10.184", "10.10.10.13", "10.10.10.236", "10.10.10.140", "10.10.10.51", "10.10.10.220", "10.10.10.6", "10.10.10.76", "10.10.10.191"]
        BLACKLISTED_HACKTHEBOX_IPS_WITHOUT_REWARD += ["10.10.10.121", "10.10.10.98", "10.10.10.46", "10.10.10.24", "10.10.10.117", "10.10.10.91", "10.10.10.171", "10.10.10.181", "10.10.10.160", "10.10.10.150"]
        BLACKLISTED_HACKTHEBOX_IPS_WITHOUT_REWARD += ["10.10.10.27", "10.10.10.222", "10.10.10.214", "10.10.10.199", "10.10.10.100", "10.10.10.138", "10.10.10.9", "10.10.10.18", "10.10.10.146"]

        BLACKLISTED_HACKTHEBOX_IPS = BLACKLISTED_HACKTHEBOX_IPS_WITH_REWARD + BLACKLISTED_HACKTHEBOX_IPS_WITHOUT_REWARD

        harcoded_machines = False
        if harcoded_machines:
            parsed_machines = [
                [1, {
                    "name": "Lame",
                    "ip": "10.129.78.31",
                    "rating": 1,
                    "id": 1,
                    "force_assign": True,
                    "health_check_port": 139,
                    "wait_for_super": True,
                }]
                ,
                [2, {
                    "name": "Legacy",
                    "ip": "10.10.10.4",
                    "rating": 1,
                    "id": 2,
                    "force_assign": True,
                    "health_check_port": 139,
                    "wait_for_super": True,
                }],
                [6, {
                    "name": "Optimum",
                    "ip": "10.10.10.8",
                    "rating": 1,
                    "id": 6,
                    "force_assign": True,
                    "health_check_port": 80,
                    "wait_for_super": True,
                }],
                [14, {
                    "name": "Granny",
                    "ip": "10.10.10.15",
                    "rating": 1,
                    "id": 14,
                    "force_assign": True,
                    "health_check_port": 80,
                    "wait_for_super": True,
                }],
                [13, {
                    "name": "Grandpa",
                    "ip": "10.10.10.14",
                    "rating": 1,
                    "id": 13,
                    "force_assign": True,
                    "health_check_port": 80,
                    "wait_for_super": True,
                }],
                [51, {
                    "name": "Blue",
                    "ip": "10.10.10.40",
                    "rating": 2,
                    "id": 51,
                    "force_assign": True,
                    "health_check_port": 139,
                    "wait_for_super": True,
                }]
            ]
        else:
            response = requests.get(self.BASE_URL + self._auth('/machines/get/all/'), headers=self.headers).json()
            # print(response)

            difficulties_map = self.get_difficulties_map()

            for machine in response:
                machine_ip = machine['ip']
                if machine_ip not in BLACKLISTED_HACKTHEBOX_IPS:
                    if machine['retired']:
                        parsed_machines[machine['id']] = {
                            'name':   machine['name'],
                            'ip':     machine_ip,
                            'rating': difficulties_map[machine['id']],
                            'id':     machine['id'],
                            'source': Constants.VM_SOURCE_HACKTHEBOX,
                        }

            parsed_machines = sorted(parsed_machines.items(), key=lambda k_v: k_v[1]['rating'])

            # print(parsed_machines)
            if target is not None:
                Log.logger.debug("Target ID is %s!" % target)
                for machine in parsed_machines:
                    # Log.logger.debug(f"Checking on machine {machine}")
                    if machine[1]['id'] == target:
                        target_parsed_machines = [machine]
                        Log.logger.debug(f"Returning: {target_parsed_machines}")
                        return target_parsed_machines

        return parsed_machines

    def get_assigned_machines(self) -> dict:
        response = requests.get(self.BASE_URL + self._auth('/machines/assigned/'), headers=self.headers).json()
        return response

    def get_assigned_machines_map(self) -> dict:
        # return self.get_spawned_machines_map()

        assigned_machines = None
        while True:
            assigned_machines = self.get_assigned_machines()

            break_now = True
            for machine in assigned_machines:
                if machine['spawning']:
                    print(machine)
                    Log.logger.debug("Will keep waiting since we are still spawning machine %d" % machine['id'])
                    time.sleep(60)
                    break_now = False

            if break_now:
                break

        assigned_machines_map = {}
        for machine in assigned_machines:
            assigned_machines_map[machine['id']] = machine

        return assigned_machines_map

    def get_available_machines(self):
        all_machines     = self._get_machines()
        # spawned_machines = self.get_spawned_machines_map() # Disabled for VIP

        available_machines = []
        # print(all_machines)
        for machine in all_machines:
            # print(machine)
            machine_id = machine['id']
            # if machine_id not in spawned_machines: # Disabled for VIP
            available_machines.append(machine)

        return available_machines

    def get_spawned_machines_map(self) -> dict:
        response = requests.get(self.BASE_URL + self._auth('/machines/spawned/'), headers=self.headers).json()

        # print(response)

        spawned_machines_map = {}
        for machine in response:
            spawned_machines_map[machine['id']] = machine['spawned']

        return spawned_machines_map

    def get_machine(self, mid: int) -> dict:
        """
        Get a single machine on the network
        :params self: HTB object in use
        :params mid: Machine ID
        :returns: machine dict
        """
        # print([self.BASE_URL + self._auth('/machines/get/{}/'.format(mid)), self.headers])
        response = requests.get(self.BASE_URL + self._auth('/machines/get/{}/'.format(mid)), headers=self.headers)
        # print("Response is %s" % response)

        return response.json()

    def remove_machine(self, mid: int) -> dict:
        """
        Remove a machine on the network
        :params self: HTB object in use
        :params mid: Machine ID
        :returns: reset_machine dict
        """
        res = self._post(self._auth('/vm/vip/remove/{}/'.format(mid)))

        if 'success' in res and int(res['success']) == 1:
            return True
        else:
            print("Error trying to remove machine, will try first to reset it")
            res = self.reset_machine(mid)
            print("Got response: %s will now sleep 3 minutes so the machine finishes reseting" % res)
            time.sleep(3*SECONDS_IN_MINUTE)

            res = self._post(self._auth('/vm/vip/remove/{}/'.format(mid)))
            if 'success' not in res or int(res['success']) != 1:
                raise ValueError("ERROR trying to remove machine: %s" % res)

        return res

    def assign_machine(self, mid: int) -> dict:
        """
        Reset a machine on the network
        :params self: HTB object in use
        :params mid: Machine ID
        :returns: reset_machine dict
        """
        res = self._post(self._auth('/vm/vip/assign/{}/'.format(mid)))

        # print("assign_machine => %s" % res)

        if res['success'] == '0':
            wait_time_nums = re.findall(r'\d+', res['status'])
            # print(wait_time_nums)
            if len(wait_time_nums) == 1:
                wait_time = int(wait_time_nums[0]) + 1
                print(f"assign_machine: Will sleep {wait_time} minutes and try again since the message was {res['status']}")
                time.sleep(wait_time * SECONDS_IN_MINUTE)
                res = self._post(self._auth('/vm/vip/assign/{}/'.format(mid)))

        return res


    def reset_machine(self, mid: int) -> dict:
        """
        Reset a machine on the network
        :params self: HTB object in use
        :params mid: Machine ID
        :returns: reset_machine dict
        """

        # First we reset the machine
        print("Reseting machine")
        response_reset = self._post(self._auth('/vm/reset/{}/'.format(mid)))
        print(response_reset)

        print("Waiting 30 seconds before assigning it")
        time.sleep(30)
        # Now just in case we assign it
        response_assign = self.assign_machine(mid)
        print(response_assign)
        
        return str(response_reset) + " ==> " + str(response_assign)

# class HTBVIPPLUS:
#     """
#     Hack the Box API Wrapper
#     :attr api_key: API Key used for authenticated queries
#     :attr user_agent: The User-Agent to be used with all requests
#     """
#     BASE_URL = 'https://www.hackthebox.eu/api'

#     # https://www.hackthebox.eu/api/v4/user/connection/status

#     def __init__(self, user_agent='Python HTB Client 1.1.0'):
#         self.api_key = HTB_API_KEY
#         self.headers = {'User-Agent': user_agent}

#     def _get(self, path: str) -> dict:
#         """
#         Helper function to get an API endpoint and validate the response
#         :params self: the HTB object
#         :params path: the path to get including leading forward slash
#         :returns: the response dict from the endpoint
#         """
#         time.sleep(3)
#         return requests.get(self.BASE_URL + path, headers=self.headers).json()

#     def _post(self, path: str, data: dict = None) -> dict:
#         """
#         Helper function to get an API endpoint and validate the response
#         :params self: the HTB object
#         :params path: the path to get including leading forward slash
#         :returns: the response dict from the endpoint
#         """
#         time.sleep(3)
#         return requests.post(self.BASE_URL + path, data=data, headers=self.headers).json()

#     def _auth(self, path: str) -> str:
#         """
#         Helper function to generate an authenticated URL
#         :params self: HTB object in use
#         :params path: string containing path to query
#         :returns: path to authenticated query
#         """
#         return "{}?api_token={}".format(path, self.api_key)

#     def connection_status(self) -> dict:
#         """
#         Return connection status information
#         Success key seems to be behaving incorrectly
#         :params self: HTB object in use
#         :returns: connection_status dict
#         """
#         return requests.post(self.BASE_URL + self._auth('/v4/user/connection/status'), headers=self.headers).json()

#     def get_difficulties_map(self) -> dict:
#         return NotImplementedError("Not implemented!")
#         """
#         Get all machines on the network
#         :params self: HTB object in use
#         :returns: machines dict
#         """
#         # response = requests.get(self.BASE_URL + self._auth('/machines/difficulty/'), headers=self.headers).json()
#         # # print(response)

#         # difficulty_map = {}
#         # for machine in response:
#         #     # print(machine)
#         #     difficulty_ratings = machine['difficulty_ratings']
#         #     total_votes  = sum(difficulty_ratings)
#         #     total_amount = 0
#         #     for counter in range (1,11):
#         #         # print(counter)
#         #         total_amount += counter * difficulty_ratings[counter - 1]
#         #         # print(total_amount)

#         #     if (total_votes > 0):
#         #         rating = total_amount/total_votes
#         #         # print("Machine had %d votes with an average of %.2f" % (total_votes, rating))
#         #         difficulty_map[machine['id']] = rating

#         # return difficulty_map

#     def get_machines(self) -> dict:
#         # return NotImplementedError("Not implemented!")

#         """
#         Get all machines on the network IF THEY ARE RETIRED
#         :params self: HTB object in use
#         :returns: machines dict
#         """

#         # https://www.hackthebox.eu/api/v4/machine/list/retired
#         response = requests.get(self.BASE_URL + self._auth('/v4/machine/list/retired'), headers=self.headers).json()
#         # print(response)

#         # difficulties_map = self.get_difficulties_map()

#         parsed_machines = {}
#         for machine in response:
#             parsed_machines[machine['id']] = {
#                 'name':   machine['name'],
#                 'ip':     machine['ip'],
#                 'rating': machine['difficulty'],
#                 'id':     machine['id'],
#             }
#         parsed_machines = sorted(parsed_machines.items(), key=lambda k_v: k_v[1]['rating'])

#         return parsed_machines

#     # https://www.hackthebox.eu/api/v4/machine/active
#     def get_assigned_machines(self) -> dict:
#         response = requests.get(self.BASE_URL + self._auth('/v4/machine/active'), headers=self.headers)
#         print(response)
#         response_json = response.json()

#         return response_json

#     def get_assigned_machines_map(self) -> dict:
#         assigned_machines = self.get_assigned_machines()

#         assigned_machines_map = {}
#         for machine in assigned_machines:
#             assigned_machines_map[machine['id']] = 1

#         return assigned_machines_map        

#     # def get_spawned_machines_map(self) -> dict:
#     #     response = requests.get(self.BASE_URL + self._auth('/machines/spawned/'), headers=self.headers).json()

#     #     spawned_machines_map = {}
#     #     for machine in response:
#     #         spawned_machines_map[machine['id']] = machine['spawned']

#     #     return spawned_machines_map

#     def get_machine(self, mid: int) -> dict:
#         """
#         Get a single machine on the network
#         :params self: HTB object in use
#         :params mid: Machine ID
#         :returns: machine dict
#         """
#         response = requests.get(self.BASE_URL + self._auth('/v4/machine/info/{}'.format(mid)), headers=self.headers).json()
#         response = response['info']

#         # print(response)

#         return response

#     def remove_machine(self, mid: int) -> dict:
#         """
#         Remove a machine on the network
#         :params self: HTB object in use
#         :params mid: Machine ID
#         :returns: reset_machine dict
#         """
#         res = self._post(self._auth('/v4/vm/terminate/{}'.format(mid)))

#         if 'message' in res and int(res['message']) == 'Machine terminated.':
#             return True
#         else:
#             print("Error trying to remove machine => %s, will try first to reset it" % res)
#             res = self.reset_machine(mid)
#             print("Got response: %s will now sleep 5 minutes so the machine finishes reseting" % res)
#             time.sleep(5*30)

#             res = self._post(self._auth('/v4/vm/terminate/{}/'.format(mid)))
#             if 'message' in res and int(res['message']) == 'Machine terminated.':
#                 raise ValueError("ERROR trying to remove machine: %s" % res)

#         return res

#     def assign_machine(self, mid: int) -> dict:
#         """
#         Reset a machine on the network
#         :params self: HTB object in use
#         :params mid: Machine ID
#         :returns: reset_machine dict
#         """
#         res = self._post(self._auth('/v4/vm/spawn'), {"machine_id": mid})
#         print(res)

#         return res


#     def reset_machine(self, mid: int) -> dict:
#         """
#         Reset a machine on the network
#         :params self: HTB object in use
#         :params mid: Machine ID
#         :returns: reset_machine dict
#         """
#         res = self._post(self._auth('/v4/vm/reset/'), {"machine_id": mid})
#         print(res)

#         return res

