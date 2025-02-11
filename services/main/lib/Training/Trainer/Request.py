import lib.Common.Utils.Constants as Constants
import requests
import lib.Common.Utils.Log as Log
from lib.Common import Utils

def request_to_manager(endpoint, data_to_send):
    url = f"http://{Constants.CITY_IP}:{Constants.CITY_MANAGEMENT_PORT}/{endpoint}"
    response = requests.post(url, data={"data": Utils.dump_json(data_to_send)}) # we send it so we can send it with structures like arrays
    if response.status_code != 200:
        Log.logger.warn(f"Error with {endpoint} request for url {url} with data {data_to_send}! => {response.text}")
        
        return {}, False
    else:
        # Log.logger.debug(f"API RESPONSE => {response.text}")
        response_data = Utils.json_loads(response.text)

        return response_data, True