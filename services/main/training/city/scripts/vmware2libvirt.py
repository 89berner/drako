#! /usr/bin/env python3
#
# vmware2libvirt: migrate a vmware image to libvirt
# Author: Jamie Strandboge <jamie@canonical.com>
#
# Copyright (C) 2008 Canonical Ltd.
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License version 3,
#    as published by the Free Software Foundation.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Retrieved Thu June 16, 2022 15:12:43 PM from:
#   http://bazaar.launchpad.net/~ubuntu-virt/virt-goodies/trunk/view/head:/vmware2libvirt
#
# Updated by Benjamin Porter:
#
#   * Update from Python 2 to Python 3
#   * Bug fixes
#
#

# https://github.com/FreedomBen/vmware-to-kvm 

from optparse import OptionParser
import os
import re
import subprocess
import sys

version = "0.1"
programName = "vmware2libvirt"


class V2LError(Exception):
    '''This class represents vmware2libvirt exceptions'''
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)

def warn(msg):
    '''Print warning message'''
    print("WARN: " + msg, file=sys.stderr)

def error(msg):
    '''Print error message and exit'''
    print("ERROR: " + msg, file=sys.stderr)
    sys.exit(1)

def cmd(command):
    '''Try to execute the given command.'''
    try:
        sp = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except OSError as e:
        return [127, str(e)]

    out = sp.communicate()[0]
    return [sp.returncode,out]

def get_vmx_value(vmx, key):
    '''Return value from a vmx key'''
    value = ""
    pat = re.compile(r'^' + key + '\s+=\s+')
    for line in vmx:
        if pat.search(line):
            # extract value without quotes
            value = pat.sub('', line)
            value = value.strip()
            value = value[1:-1]

    if value == "":
        raise V2LError("Bad value for '" + key + "'")

    return value

def get_arch(vmx):
    '''Detect what architecture the vmware image is'''
    arch = "i686"

    # very crude
    guestOS = get_vmx_value(vmx, "guestOS")
    if re.search(r'-64', guestOS):
        arch = "x86_64"
    return arch

def get_memory(vmx):
    '''Detect how much memory the vmware image uses'''
    memsize = get_vmx_value(vmx, "memsize")
    memory = int(memsize) * 1024
    return str(memory)

def get_vcpunr(vmx):
    '''Detect number of vcpus'''
    try:
        vcpunr = get_vmx_value(vmx, "numvcpus")
    except:
        return '1'
    return vcpunr

def get_new_uuid():
    '''Generate a new uuid'''
    (rc, out) = cmd(['uuidgen'])
    if rc != 0:
        raise V2LError("'uuidgen' exited with error: " + out)
    return out.strip().decode()

def get_disk(dir, vmx):
    '''Detect the disk vmware image uses'''
    scsi_disk = ""
    ide_disk = ""
    disk = ""
    try:
         scsi_disk = get_vmx_value(vmx, "scsi0:0.fileName")
    except:
         pass
    try:
         ide_disk = get_vmx_value(vmx, "ide0:0.fileName")
    except:
         pass

    if scsi_disk != "" and ide_disk != "":
        # found two disks, default to scsi for now
        if re.search(r'.vmdk$', scsi_disk):
            disk = scsi_disk
        elif re.search(r'.vmdk$', ide_disk):
            disk = ide_disk
        else:
            raise V2LError("Couldn't find vmdk disk")
    elif scsi_disk != "":
        disk = scsi_disk
    elif ide_disk != "":
        disk = ide_disk
    else:
        raise V2LError("Couldn't find any disks")

    disk = os.path.join(dir, disk)
    if not os.path.exists(disk):
        warn("'" + disk + "' does not exist")

    return disk

def get_mac(vmx, index):
    '''Detect the MAC address vmware image uses given network card index'''
    mac =  get_vmx_value(vmx, "ethernet%d.generatedAddress" %index)
    return mac

def get_network(vmx, bridge, netmodel):
    '''Detect up to 4 network cards and provide libvirt xml blocks for all of them'''

    result = ''
    networktype = 'network'
    networksource = "network='default'"
    if bridge:
        networktype = 'bridge'
        networksource = "bridge='%s'" %bridge
    if netmodel:
        netmodel = "\n      <model type='%s'/>" %netmodel

    for index in range(4):
        try:
            mac = get_mac(vmx, index)
        except V2LError:
            continue
        result += '''
    <interface type=\'''' + networktype + '''\'>
      <mac address=\'''' + mac + '''\'/>
      <source ''' + networksource + '''/>''' + netmodel + '''
    </interface>'''
    return result

def process_args():
    '''Process command line arguments'''
    usage = "%prog [options] -f FILE"
    description = '''Convert a vmware vmx file to a libvirt xml file'''
    parser = OptionParser(usage=usage, version="%prog: " + version, \
        description=description)
    parser.add_option("-q", "--qemu", action="store_true", dest="use_qemu", \
        help="use qemu instead of kvm")
    parser.add_option("-b", "--bridge", dest="bridge", \
        help="use bridged network instead of default network", metavar='INTERFACE')
    parser.add_option("-x", "--diskbus", \
        help="specify which bus to use for disk, i.e. virtio", metavar='bustype')
    parser.add_option("-n", "--netmodel", \
        help="specify which network card model to use for network cards", metavar='netmodel')
    parser.add_option("-f", "--file", dest="vmxfile", \
        help="vmware vmx file to migrate", metavar="FILE")
    parser.add_option("-d", "--disk", dest="disk", \
        help="disk destination", metavar="FILE")
    parser.add_option("-r", "--disk_driver", dest="disk_driver", \
        help="disk_driver", metavar="FILE")
    parser.add_option("-a", "--name", dest="name", \
        help="name for vm", metavar="FILE")

    (options, args) = parser.parse_args()

    if not options.vmxfile:
        parser.print_help()
        sys.exit(1)

    if not os.path.exists(options.vmxfile):
        error("'" + options.vmxfile + "' does not exist")

    return options


# Execution starts here
try:
    opts = process_args()
except:
    raise

try:
    orig = open(opts.vmxfile, 'r')
except OSError as e:
    raise V2LError(e.value)
except Exception:
    raise

vmx = orig.readlines()

domain = "kvm"
emulator = "kvm"
if opts.use_qemu:
    domain = "qemu"
    emulator = "qemu"

bridge = opts.bridge
diskbus = ''
if opts.diskbus:
    diskbus = "bus='%s'" %opts.diskbus
netmodel = ''
if opts.netmodel:
    netmodel = opts.netmodel

disk = opts.disk

# if opts.disk
# dir = os.path.abspath(os.path.dirname(opts.vmxfile))
# try:
#     disk = get_disk(dir, vmx)
# except:
#     error

# disk = disk.replace(".vmdk", "qcow2")

libvirt_xml = '''<domain type=\'''' + domain + '''\'>
  <name>''' + opts.name + '''</name>
  <uuid>''' + str(get_new_uuid()) + '''</uuid>
  <memory>''' + str(get_memory(vmx)) + '''</memory>
  <currentMemory>''' + str(get_memory(vmx)) + '''</currentMemory>
  <vcpu>''' + str(get_vcpunr(vmx)) + '''</vcpu>
  <os>
    <type arch=\'''' + get_arch(vmx) + '''\' machine='pc'>hvm</type>
    <boot dev='hd'/>
  </os>
  <features>
    <acpi/>
  </features>
  <clock offset='utc'/>
  <on_poweroff>destroy</on_poweroff>
  <on_reboot>restart</on_reboot>
  <on_crash>destroy</on_crash>
  <devices>
    <emulator>/usr/bin/''' + emulator + '''</emulator>
    <disk type='file' device='disk'>
      <driver name='qemu' type=\'''' + opts.disk_driver + '''\'/>
      <source file=\'''' + disk + '''\'/>
      <target dev='hda\' ''' + diskbus + '''/>
    </disk>''' + str(get_network(vmx,  bridge, netmodel)) + '''
    <input type='mouse' bus='ps2'/>
    <graphics type='vnc' port='-1' listen='127.0.0.1'/>
  </devices>
</domain>'''

print(libvirt_xml)

orig.close()