import yaml
import lib.Common.Utils.Log as Log
import os
import string
import random
import re
import urllib.request
import uuid
import shutil
from pathlib import Path

from lib.Common.Utils import Constants
from lib.Training.Manager.Virsh import VIRSH
from lib.Training.Trainer.Common import execute_command

class Inventory:
    def __init__(self, virsh_client: VIRSH, configuration_folder_path: str):
        self.virsh_client = virsh_client
        self.configuration_folder_path = configuration_folder_path
        self.tmp_folder_path           = "/tmp/inventory"
        self.inventory_by_name, self.inventory_by_id, self.inventory_arr = self.load_inventory()

    def load_inventory(self):
        directory = os.fsencode(self.configuration_folder_path)
        inventory_by_name = {}
        inventory_by_id   = {}
        inventory_arr     = {}

        for filename in os.listdir(directory):
            full_file_path = os.path.join(directory, filename)
            # Log.logger.debug(filename)

            target_source  = filename.decode("utf-8").split(".")[0]
            extension      = filename.decode("utf-8").split(".")[1]
            if extension == "yaml":
                if target_source not in inventory_by_name:
                    inventory_by_name[target_source] = {}
                    inventory_by_id[target_source]   = {}
                    inventory_arr[target_source]     = []

                with open(full_file_path, 'r') as stream:
                    try:
                        data = yaml.safe_load(stream)
                        if data is not None:
                            for entry in data:
                                id   = entry['id']
                                name = entry['name']
                                name_clean = re.sub('[^0-9a-zA-Z_]+', '', name).lower() #clean names
                                
                                entry['name'] = name_clean
                                inventory_by_name[target_source][name_clean] = entry
                                inventory_by_id[target_source][id]     = entry
                                inventory_arr[target_source].append(entry)
                    except yaml.YAMLError as exc:
                        Log.logger.warning("Error parsing YAML")
                        raise exc

        # Log.logger.debug(inventory_by_name)
        # Log.logger.debug(inventory_by_id)

        return inventory_by_name, inventory_by_id, inventory_arr

    def get_targets(self, target_source):
        return self.inventory_arr[target_source]

    def get_by_id(self, target_source, target_id):
        return self.inventory_by_id[target_source][target_id]

    def get_by_name(self, target_source, target_name):
        return self.inventory_by_name[target_source][target_name]

    def start_by_name(self, target_source, target_name):
        target = self.get_by_name(target_source, target_name)
        return self.start_by_id(target_source, target['id'])

    def start_by_id(self, target_source, target_id):
        target = self.get_by_id(target_source, target_id)

        if target_source == Constants.VM_SOURCE_GENERAL:
            self.start_general_target(target)

            target_ip = self.virsh_client.get_vm_ip_address(target['name'], internal=True)

            target_for_res = {
                "name":              target['name'],
                "id":                target_id,
                "ip":                target_ip,
                "wait_for_super":    True,
                "source":            target_source,
            }

            if 'health_check_port' in target:
                target_for_res["health_check_port"] = target['health_check_port'],

            return target_for_res
        else:
            raise NotImplementedError(f"target_source {target_source} has not been implemented")

    def start_general_target(self, target):
        Log.logger.info(target)

        self.virsh_client.destroy_and_undefine_vm(target['name'])

        filename     = os.path.basename(target['disk_location'])
        new_location = f"{Constants.VIRSH_IMAGE_FILE_LOCATION}/{filename}"

        Log.logger.debug(f"Copying image from {target['disk_location']} to {new_location}")
        execute_command(f"cp {target['disk_location']} {new_location}")

        filename     = os.path.basename(target['configuration_file'])
        new_location = f"{Constants.VIRSH_CONFIG_FILE_LOCATION}/{filename}"
        Log.logger.debug(f"Copying configuration from {target['configuration_file']} to {new_location}")
        execute_command(f"cp {target['configuration_file']} {new_location}")

        # if target['disk_type'] == Constants.VMDK_DISK_TYPE:
        #     vmdk_disk_qcow2, _ = self.virsh_client.convert_vmdk_to_qcow2(target['vmdk_disk'])

        #     xml_file = f"/etc/libvirt/qemu/{target['name']}.xml"
        #     self.virsh_client.create_xml_file_from_vmdk(target['vmdk_config'], vmdk_disk_qcow2, xml_file, target['name'])

        #     self.virsh_client.define_vm(xml_file)
        # else:
        #     raise NotImplementedError(f"disk_type {target['disk_type']} has not been implemented")

        # Now we remove the networks and add only the isolated network
        xml_file = f"{Constants.VIRSH_CONFIG_FILE_LOCATION}/{target['name']}.xml"
        self.virsh_client.define_vm(xml_file)

        self.virsh_client.define_target_network(target['name'])

        self.virsh_client.start_vm(target['name'])

    def add_target_to_file(self, source, new_target):
        full_file_path = f"{self.configuration_folder_path}/{source}.yaml"

        from pathlib import Path

        # Create the yaml file if it does not exist
        myfile = Path(full_file_path)
        myfile.touch(exist_ok=True)

        with open(full_file_path) as f:
            source_list = yaml.safe_load(f)
        if source_list is None:
            source_list = []

        new_target['id'] = None
        largest_id = 0

        for target in source_list:
            if target['id'] > largest_id:
                largest_id = target['id']
            
            if target['name'] == new_target['name']:
                Log.logger.warning(f"We will use id {target['id']} since the name of the target matches our name")
                new_target['id'] = target['id']
        
        if new_target['id'] is None:
            new_target['id'] = largest_id + 1
        else:
            # Since we are updating a target, let's replace it
            source_list = [x for x in source_list if not x['id'] == new_target['id']]

        source_list.append(new_target)

        with open(full_file_path, "w") as f:
            yaml.dump(source_list, f, sort_keys=False)

    def create_temporary_folder(self):
        letters = string.ascii_lowercase
        random_name = ''.join(random.choice(letters) for i in range(10))

        random_folder = f"{self.tmp_folder_path}/{random_name}"
        # TODO: replace for os
        execute_command(f"mkdir -p {random_folder}")

        return random_folder

    def download_url(self, url, random_folder, name, disk_type):
        file_location = f"{random_folder}/{name}.{disk_type}"
        Log.logger.debug(f"Downloading {url} into {file_location}")
        # urllib.request.urlretrieve(url, file_location)

        # opener = urllib.request.URLopener()
        # opener.addheader('User-Agent', 'Wget/1.21.2')
        # filename, headers = opener.retrieve(url, file_location)
        execute_command(f"wget -q {url} -O {file_location}")

        return file_location

    def locate_file_by_extension(self, folder, file_extension):
        Log.logger.debug(f"Locating {file_extension} file..")

        from os import listdir
        from os.path import isfile, join

        onlyfiles = [os.path.join(dp, f) for dp, dn, fn in os.walk(os.path.expanduser(folder)) for f in fn]
        # onlyfiles = [f for f in listdir(folder) if isfile(join(folder, f))]

        if len(onlyfiles) > 1:
            raise ValueError(f"We got {len(onlyfiles)} vmdk files, will stop")

        for file in onlyfiles:
            if file.endswith(f".{file_extension}"):
                return file

        return None

    def get_vmdk_from_ova_file(self, random_folder, file_location):
        Log.logger.debug("Extracting ova file")
        command = f"cd {random_folder}; tar xvf \"{file_location}\""
        execute_command(command)

        file = self.locate_file_by_extension(random_folder, "vmdk")

        return file

    def get_vmdk_from_zip_file(self, random_folder, file_location):
        Log.logger.debug("Extracting zip file")
        command = f"cd {random_folder}; 7za e \"{file_location}\""
        execute_command(command)

        file = self.locate_file_by_extension(random_folder, "vmdk")

        return file

    def get_vmdk_from_rar_file(self, random_folder, file_location):
        Log.logger.debug("Extracting rar file")
        command = f"cd {random_folder}; unrar x \"{file_location}\""
        execute_command(command)

        file = self.locate_file_by_extension(random_folder, "vmdk")

        return file

    def get_vmdk_from_gz_file(self, random_folder, file_location):
        Log.logger.debug("Extracting gz file")
        command = f"cd {random_folder}; tar -xvzf \"{file_location}\""
        execute_command(command)

        file = self.locate_file_by_extension(random_folder, "vmdk")

        # if file is None:
        #     Log.logger.debug("We will try to extract the file")

        return file

    def get_vmdk_from_7z_file(self, random_folder, file_location):
        Log.logger.debug("Extracting zip file")
        command = f"cd {random_folder}; 7zr x \"{file_location}\""
        execute_command(command)

        file = self.locate_file_by_extension(random_folder, "vmdk")

        return file

    def create_domain_file(self, source, name, cpus, ram, disk_location):
        with open(Constants.VIRSH_DEFAULT_TARGET_XML, 'r') as file :
            default_target_xml = file.read()

        default_target_xml = default_target_xml.replace("TEMPLATE_NAME_VALUE", name)
        default_target_xml = default_target_xml.replace("TEMPLATE_UUID_VALUE", str(uuid.uuid1()) )

        mem_in_kb = ram * 1024 * 1024
        default_target_xml = default_target_xml.replace("TEMPLATE_MEMORY_VALUE", f"{mem_in_kb}")
        default_target_xml = default_target_xml.replace("TEMPLATE_CPUS_VALUE", f"{cpus}")
        default_target_xml = default_target_xml.replace("TEMPLATE_DISK_LOCATION_VALUE", disk_location)

        random_mac_address = "52:54:00:%02x:%02x:%02x" % tuple(random.randint(0, 255) for v in range(3))
        default_target_xml = default_target_xml.replace("TEMPLATE_MAC_ADDRESS_VALUE",  random_mac_address)

        config_file_location = f"{Constants.VIRSH_CONFIG_FILE_LOCATION}/{source}"
        if not os.path.exists(config_file_location):
            Log.logger.debug(f"Creating the folder {config_file_location} since it does not exist")
            Path(config_file_location).mkdir()

        # Write the file out again
        new_filename = f"{config_file_location}/{name}.xml"
        with open(new_filename, 'w') as file:
            file.write(default_target_xml)

        return new_filename

    def check_for_ova(self, random_folder):
        Log.logger.debug("No vmdk_file was found, let's look for an ova")
        ova_file_location = self.locate_file_by_extension(random_folder, "ova")

        if ova_file_location is not None:
            return self.get_vmdk_from_ova_file(random_folder, ova_file_location)
        else:
            raise ValueError("vmdk and ova file is missing")

    def add_target(self, disk_type, source, url, name, description, cpus, ram, force=None, health_check_port=None):
        # Download URL
        if source not in Constants.VIRSH_TARGET_SOURCES:
            raise NotImplementedError(f"source {source} not allowed")

        if source in self.inventory_by_name and name in self.inventory_by_name[source]:
            Log.logger.warning(f"Skipping adding {name} since it was already present in our inventory!")
            return

        random_folder = self.create_temporary_folder()
        Log.logger.debug(f"Created random folder {random_folder}")

        file_location = self.download_url(url, random_folder, name, disk_type)
        Log.logger.debug(f"Downloaded {url} to {file_location}")

        if disk_type == "ova":
            vmdk_file = self.get_vmdk_from_ova_file(random_folder, file_location)
        elif disk_type == "7z":
            vmdk_file = self.get_vmdk_from_7z_file(random_folder, file_location)
        elif disk_type == "rar":
            vmdk_file = self.get_vmdk_from_rar_file(random_folder, file_location)
        elif disk_type == "gz":
            vmdk_file = self.get_vmdk_from_gz_file(random_folder, file_location)
        elif disk_type == "zip":
            vmdk_file = self.get_vmdk_from_zip_file(random_folder, file_location)
        elif disk_type == "vmdk":
            Log.logger.debug("disk_type is already vmdk so we don't need to do anything extra")
            vmdk_file = file_location
        else:
            raise NotImplementedError(f"I don't know how to handle disk type {disk_type}")

        if vmdk_file is None:
            vmdk_file = self.check_for_ova(random_folder)
            if vmdk_file is None: #still none?
                raise ValueError("vmdk file is missing")

        vmdk_file_new = f"{name}.vmdk"

        if vmdk_file != f"{random_folder}/{vmdk_file_new}":
            Log.logger.debug(f"Now we modify the name of the virtual disk {vmdk_file} to {vmdk_file_new}")
            execute_command(f"mv \"{vmdk_file}\" \"{random_folder}/{vmdk_file_new}\"")
        else:
            Log.logger.warning(f"Not moving since files are identical: \"{vmdk_file}\" \"{random_folder}/{vmdk_file_new}\"")

        vmdk_disk_qcow2, _ = self.virsh_client.convert_vmdk_to_qcow2(f"{random_folder}/{vmdk_file_new}")
        new_disk_type      = "qcow2"
        
        image_location = f"{Constants.VIRSH_IMAGE_EPHEMERAL_LOCATION}/{source}"
        if not os.path.exists(image_location):
            Log.logger.debug(f"Creating the folder {image_location} since it does not exist")
            Path(image_location).mkdir()

        vmdk_disk_qcow2_file = os.path.basename(vmdk_disk_qcow2)
        
        disk_location = f"{image_location}/{vmdk_disk_qcow2_file}"

        Log.logger.debug(f"Now moving new disk file to {disk_location}")
        execute_command(f"mv {vmdk_disk_qcow2} {disk_location}")

        Log.logger.debug(f"Now creating a new domain file for {name}")
        image_location_for_xml = f"{Constants.VIRSH_IMAGE_FILE_LOCATION}/{vmdk_disk_qcow2_file}"
        configuration_file     = self.create_domain_file(source, name, cpus, ram, image_location_for_xml)
        Log.logger.debug(f"Created file {configuration_file}")

        new_target = {
            "name":               name,
            "description":        description,
            "disk_url":           url,
            "disk_type":          new_disk_type,
            "disk_location":      disk_location,
            "cpus":               cpus,
            "memory":             ram,
            "configuration_file": configuration_file,
        }

        if health_check_port is not None:
            new_target['health_check_port'] = health_check_port

        Log.logger.debug(f"We will now add the target {new_target} to the file for {source}")
        self.add_target_to_file(source, new_target)

        Log.logger.debug(f"Finally we delete folder created {random_folder}")
        shutil.rmtree(random_folder)
