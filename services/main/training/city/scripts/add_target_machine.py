import time
import traceback
import argparse
import sys

sys.path.append("/root/drako/services/main/")
from lib.Training.Manager.Inventory import Inventory
from lib.Training.Manager.Virsh import VIRSH
from lib.Common.Utils import Constants
import lib.Common.Utils.Log as Log

argparser = argparse.ArgumentParser(description='Use Start Castle from command line')
argparser.add_argument('--disk_type',         dest='disk_type',   required=True,   type=str,              help='disk_type')
argparser.add_argument('--url',               dest='url',         required=True,   type=str,              help='url')
argparser.add_argument('--source',            dest='source',      required=True,   type=str,              help='source file', )
argparser.add_argument('--name',              dest='name',        required=True,   type=str,              help='name')
argparser.add_argument('--description',       dest='description',                  type=str,              help='description')
argparser.add_argument('--cpus',              dest='cpus',                         type=int, default="2", help='cpus' )
argparser.add_argument('--ram',               dest='ram',                          type=int, default="4", help='ram in gb', )
argparser.add_argument('--health_check_port', dest='health_check_port',            type=int,              help='ram in gb', )

# INITIALIZATIONS
Log.initialize_log("2")

virsh_Client = VIRSH(Constants.VIRSH_SOCKET_LOCATION_CITY)
inventory    = Inventory(virsh_Client, Constants.VIRSH_CITY_TARGET_FOLDER_PATHS)

def main(args):
    print("Starting to add target")
    name = args.name.lower()
    try:
        inventory.add_target(args.disk_type, args.source, args.url, name, args.description, args.cpus, args.ram, args.health_check_port)
    except:
        Log.logger.debug(f"ERROR adding target => {traceback.format_exc()}")

if __name__ == '__main__':
    # SETTING UP LOGGER
    args = argparser.parse_args()
    main(args)

