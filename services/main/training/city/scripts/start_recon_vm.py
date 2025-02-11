import sys
import argparse
import time

sys.path.append("/root/drako/services/main/")
from lib.Common.Utils import Constants
from lib.Training.Manager.Virsh   import VIRSH
import lib.Common.Utils.Log as Log

argparser = argparse.ArgumentParser(description='Use Start Recon from command line')
argparser.add_argument('--log_level', dest='log_level', default="2", help='specify the log level', choices=("0", "1", "2", "3"))

virsh = VIRSH(Constants.VIRSH_SOCKET_LOCATION_CITY)

def main():
    Log.initialize_log(args.log_level)
    Log.add_info_large_ascii("Recon")

    Log.logger.debug("First deleting any existing vm for recon")
    virsh.destroy_and_undefine_vm(Constants.RECON_VM_NAME)

    Log.logger.info("Will now start creating a clone of the recon VM")
    vm_ip = virsh.clone_start_and_sync_vm(Constants.RECON_VM_NAME, 50, 16)

    Log.logger.info(f"VM was created with IP {vm_ip}")
    virsh.execute_command_in_vm(vm_ip, f"/bin/bash {Constants.RECON_SCRIPTS_PATH}/start_recon_screens.sh")

if __name__ == '__main__':
    # SETTING UP LOGGER
    args = argparser.parse_args()
    main()

