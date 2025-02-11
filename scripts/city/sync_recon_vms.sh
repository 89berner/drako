#!/bin/bash

# declare -a RECON_VMS=("recon-golden-image" "recon_1")
declare -a RECON_VMS=("recon")

while true; do
    sleep 1;
    for vm_name in "${RECON_VMS[@]}"
    do
        /root/drako/scripts/city/sync_to_vm.sh $vm_name
    done
done