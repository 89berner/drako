import time
import datetime

from lib.Training.Trainer.Common import execute_command

import lib.Common.Utils.Log as Log
from   lib.Common.Utils import Constants

class VIRSH:
    def __init__(self, socket_location):
        self.socket_location = socket_location

    def destroy_vm(self, castle_name):
        Log.logger.debug(f"Destroying VM {castle_name}")
        command = f"virsh -c qemu+unix:///system?socket={self.socket_location} destroy {castle_name}"
        execute_command(command, ignore_errors=True)

    def undefine_vm(self, castle_name):
        Log.logger.debug(f"Undefining VM {castle_name}")
        command = f"virsh -c qemu+unix:///system?socket={self.socket_location} undefine {castle_name}"
        execute_command(command, ignore_errors=True)

    def destroy_and_undefine_vm(self, vm_name):
        self.destroy_vm(vm_name)
        self.undefine_vm(vm_name)

    def sync_latest_data_to_vm(self, vm_name):
        Log.logger.info("Sync latest drako code to VM")
        counter = 0
        while True:
            try:
                # We will keep retrying since we need to wait for the VM to boot up
                command = f"/bin/bash /root/drako/scripts/city/sync_to_vm.sh {vm_name}"
                execute_command(command, ignore_errors=False)
                break
            except Exception as error:
                if counter < 30:
                    counter += 1
                    Log.logger.warning("Error syncing to VM, will retry in 10 seconds")
                    time.sleep(10)
                else:
                    raise error
        Log.logger.debug("Finished syncing latest drako code to VM")

    def start_vm(self, vm_name):
        Log.logger.info("Now starting the VM")
        command = f"virsh -c qemu+unix:///system?socket={self.socket_location} start {vm_name}"
        execute_command(command, ignore_errors=True)

    def define_vm(self, xml_file_path):
        Log.logger.debug("Finally we define the VM")
        command = f"virsh -c qemu+unix:///system?socket={self.socket_location} define {xml_file_path}"
        execute_command(command)

    def create_xml_file_from_vmdk(self, vmdk_config, vmdk_disk_qcow2, xml_file, target_name):
        Log.logger.debug(f"Now we will create the xml file {xml_file}")
        command = f"python3 /app/vmware2libvirt.py -f {vmdk_config} -d {vmdk_disk_qcow2} -a {target_name} -r qcow2 > {xml_file}"
        execute_command(command)

        return True

    def convert_vmdk_to_qcow2(self, vmdk_disk: str):
        vmdk_disk_qcow2 = vmdk_disk.replace(".vmdk", ".qcow2")
        Log.logger.debug(f"First we transform the disk {vmdk_disk} into {vmdk_disk_qcow2}")
        command = f"qemu-img convert -f vmdk {vmdk_disk} -O qcow2 {vmdk_disk_qcow2}"
        execute_command(command)

        return vmdk_disk_qcow2, True

    def get_vm_ip_address(self, castle_vm, internal=False, source=None):
        vm_ip_address = ""

        MAX_TRIES = 100
        counter   = 0
        while vm_ip_address == "":
            vm_ip_address = self.get_vm_ip_address_step(castle_vm, internal, source)
            if vm_ip_address == "":
                Log.logger.debug("We did not get an ip yet, let's wait for the machine to boot up")
                time.sleep(10)
                if counter > MAX_TRIES:
                    raise ValueError(f"We tried {counter} times so we will give up trying to get the ip")
                else:
                    counter += 1
            else:
                Log.logger.debug("VM IP IS %s" % vm_ip_address)
                return vm_ip_address

    def get_vm_ip_address_step(self, castle_vm, internal, source):
        Log.logger.debug("Getting ip address..")

        source_str = ""
        if source=="agent":
            source_str = " --source=agent"

        command = f"virsh -c qemu+unix:///system?socket={self.socket_location} domifaddr " + castle_vm + source_str + "|grep ipv4|awk '{print $4}'|cut -d '/' -f 1"

        output = execute_command(command, ignore_errors=True, hide_output=True)

        output_lines = output.split("\n")
        Log.logger.debug(output_lines)
        for line in output_lines:
            if line.startswith("127.0.0.1") or line.startswith("localhost"):
                continue

            if (internal and not line.startswith("10.4.4")) or (not internal and not line.startswith("192.168.122")):
                continue
            
            return line
        
        return ""

    def add_isolated_network_to_vm(self, vm_name):
        command = f"virt-xml -c qemu+unix:///system?socket={self.socket_location} --add-device --network network=isolated,model=virtio {vm_name}"
        execute_command(command)

    def remove_all_networks_from_vm(self, vm_name):
        command = f"virt-xml -c qemu+unix:///system?socket={self.socket_location} --remove-device --network all {vm_name}"
        execute_command(command)

    def define_target_network(self, vm_name):
        self.remove_all_networks_from_vm(vm_name)
        self.add_isolated_network_to_vm(vm_name)

    def define_network(self, file_path):
        command = f"virsh -c qemu+unix:///system?socket={self.socket_location} net-define {file_path}"
        execute_command(command)

    def start_network(self, network_name):
        command = f"virsh -c qemu+unix:///system?socket={self.socket_location} net-start {network_name}"
        execute_command(command, ignore_errors=True)

    def backup_vm(self, vm_name):
        Log.logger.info(f"Backing up vm {vm_name}")

        self.destroy_vm(vm_name) # Important destroy it before backing it up

        date_str = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M")

        # IMPORTANT We need to first copy before undefining 
        bkp_filename  = f"{vm_name}_{date_str}.xml.bkp"
        curr_filename = f"{vm_name}.xml"
        command = f"cp {Constants.VIRSH_CONFIG_FILE_LOCATION}/{curr_filename} {Constants.VIRSH_CONFIG_FILE_LOCATION}/{bkp_filename}"
        Log.logger.debug(f"Moving the current vm conifg file ")
        execute_command(command, ignore_errors=True)

        Log.logger.debug("Now moving the vm image")
        bkp_filename  = f"{vm_name}_{date_str}.img"
        curr_filename = f"{vm_name}.img"
        command = f"mv {Constants.VIRSH_IMAGE_FILE_LOCATION}/{curr_filename} {Constants.VIRSH_IMAGE_FILE_LOCATION}/{bkp_filename}"
        execute_command(command, ignore_errors=True)

        self.undefine_vm(vm_name)

    def clone_vm(self, vm_name, ram_needed, cpus_needed):
        Log.logger.info("Will now clone the base image")
        command = f"/bin/bash {Constants.CITY_FOLDER_PATH}/clone_vm.sh {vm_name} {ram_needed} {cpus_needed}"
        execute_command(command)

    def increase_vm_size(self, vm_name, size):
        Log.logger.debug("Increasing VM size by {size}GB...")
        execute_command(f"qemu-img resize -f raw {Constants.VIRSH_IMAGE_FILE_LOCATION}/{vm_name}.img +{size}G")

    def execute_command_in_vm(self, vm_ip, command_to_execute_in_castle, ignore_errors=False):
        command_to_execute = "timeout -s SIGKILL 120 ssh -oUserKnownHostsFile=/dev/null -oStrictHostKeyChecking=no -i /root/drako/.keys/id_rsa root@%s '%s';echo 'FINISHED';" % (
            vm_ip, command_to_execute_in_castle)

        return execute_command(command_to_execute, ignore_errors)

    def clone_start_and_sync_vm(self, vm_name, ram, cpus):
        self.clone_vm(vm_name, ram, cpus)

        self.increase_vm_size(vm_name, 30)

        self.start_vm(vm_name)

        Log.logger.debug("Will wait 2 minutes for the VM to boot up")
        time.sleep(120)

        initial_ip_address = self.get_vm_ip_address(vm_name, internal=False, source="agent")

        Log.logger.debug(f"Let's now adjust the system uuid to get a different IP than {initial_ip_address}")
        self.execute_command_in_vm(initial_ip_address, "rm /etc/machine-id; systemd-machine-id-setup; reboot")

        Log.logger.debug("Will wait 30 seconds for the machine to reboot..")
        time.sleep(30)

        vm_ip_address = self.get_vm_ip_address(vm_name, internal=False, source="agent")

        Log.logger.debug("Now lets adjust the FS to the new size..")
        self.execute_command_in_vm(vm_ip_address, "growpart /dev/vda 2; resize2fs /dev/vda2")

        Log.logger.debug("Now we will set the hostname")
        hostname = vm_name.replace("_", "-")
        self.execute_command_in_vm(vm_ip_address, f"echo {hostname} > /etc/hostname; hostname {hostname}")

        self.sync_latest_data_to_vm(vm_name)

        return vm_ip_address