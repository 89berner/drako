import time
import traceback
import argparse
import sys
from turtle import down
import requests
import re
import pickle


sys.path.append("/root/drako/services/main/")
from lib.Training.Manager.Inventory import Inventory
from lib.Common.Utils import Constants
from lib.Common.Utils import str2bool
from lib.Training.Manager.Virsh import VIRSH 
from lib.Common.Utils import Log

argparser = argparse.ArgumentParser(description='Use Start Castle from command line')
argparser.add_argument('--load_targets', dest='load_targets', required=False, type=str2bool, help='should we load targets from disk')
argparser.add_argument('--force',        dest='force',        required=False, type=str2bool, help='should we force to re download existing entries')

# INITIALIZATIONS
Log.initialize_log("2")

TARGETS_PICKLE_LOCATION = f'{Constants.ROOT_INVENTORY_LOCATION}/targets.pkl'
virsh_Client = VIRSH(Constants.VIRSH_SOCKET_LOCATION_CITY)

def save_targets(targets_to_add):
    with open(TARGETS_PICKLE_LOCATION, 'wb') as f:
        pickle.dump(targets_to_add, f)

def load_targets():
    with open(TARGETS_PICKLE_LOCATION, 'rb') as f:
        targets_to_add = pickle.load(f)
        return targets_to_add

def main(args):

    targets_to_add = {}
    if args.load_targets:
        targets_to_add = load_targets()
    else:
        # FIRST I GET ALL THE VM LINKS
        url = "https://www.vulnhub.com/timeline/"
        r = requests.get(url)
        # print(r.text)

        links = {}
        separator = "~ <a href=\""
        for line in r.text.split("\n"):
            if separator in line:
                link = line.split(separator)[1].split("\"")[0]
                rest = line.split(separator)[1].split("\"")[1]
                name = rest.split(">")[1].split("<")[0].rstrip()
                name = re.sub(r'[^a-zA-Z0-9]', '_', name)
                name = re.sub('_+','_',name)
                name = re.match(r'^(.*?)_?$', name).group(1).lower()
                links[name] = link
                # print(rest)

        # print(links)
        print(f"We got {len(links)} links to process")

        for machine_name in links:
            link = links[machine_name]
            link_full = f"https://www.vulnhub.com{link}"
            # print(f"Processing link {link_full}")
            r = requests.get(link_full)
            # print(f"Got {len(r.text)} chars")
            download_url = ""
            for line in r.text.split("\n"):
                if 'Download (Mirror)' in line:
                    # print(line)
                    separator = "<a href=\""
                    if separator in line:
                        download_url = line.split(separator)[1].split("\"")[0]
                        # print(f"Got download link {download_url}")
            
            if download_url != "":
                print(f"Will add the machine {machine_name} with download url at {download_url}")

                disk_type = download_url.split("/")[-1].split(".")[-1]


                targets_to_add[machine_name] = {
                    "disk_type":   disk_type,
                    "source":      Constants.VM_SOURCE_VULNHUB,
                    "url":         download_url,
                    "name":        machine_name,
                    "description": link_full,
                    "cpus":        2,
                    "ram":         4,
                }
            else:
                print(f"I did not find a url for {machine_name}")
                # time.sleep(60)

        save_targets(targets_to_add)

    for machine_name in targets_to_add:
        target = targets_to_add[machine_name]
        print(f"Processing target {target}")

        try:
            inventory = Inventory(virsh_Client, Constants.VIRSH_CITY_TARGET_FOLDER_PATHS)

            inventory.add_target(target['disk_type'], target['source'], target['url'], target['name'], target['description'], target['cpus'], target['ram'], args.force)
        except:
            Log.logger.debug(f"ERROR adding target, will wait 30 seconds => {traceback.format_exc()}")
            time.sleep(30)

    # NOW WE ADD THE TARGET

if __name__ == '__main__':
    args = argparser.parse_args()
    main(args)

