#!/bin/bash

# https://serverfault.com/questions/1027069/cant-start-domain-cloned-with-virt-clone
. /root/drako/scripts/common/constants.env VIRSH_IMAGE_FILE_LOCATION VIRSH_CONFIG_FILE_LOCATION

set -e

NAME=$1
if [ -z "$NAME" ]; then
	echo "You need to define a name!"
    exit 1
fi

MEMORY=$2
if [ -z "$MEMORY" ]; then
	echo "You need to define an amount of memory in GB!"
    exit 1
fi

CORES=$3
if [ -z "$CORES" ]; then
	echo "You need to define an amount of cores!"
    exit 1
fi

VM_NAME=$(echo $NAME | tr '[:upper:]' '[:lower:]')
CONFIG_FILE=$VIRSH_CONFIG_FILE_LOCATION/$VM_NAME.xml

echo "Will create a new clone VM $VM_NAME"

# nocache cp -a $VIRSH_IMAGE_FILE_LOCATION/orchestrator-golden-image.img  $VIRSH_IMAGE_FILE_LOCATION/$VM_NAME.img
dd if=$VIRSH_IMAGE_FILE_LOCATION/orchestrator-golden-image.img of=$VIRSH_IMAGE_FILE_LOCATION/$VM_NAME.img bs=4M iflag=direct oflag=direct
cp -a $VIRSH_CONFIG_FILE_LOCATION/orchestrator-golden-image.xml $CONFIG_FILE

echo "Creating new MAC ADDRESS, UUID"
NEW_MAC_ADDRESS_1=$(printf '52:54:00:%02X:%02X:%02X\n' $[RANDOM%256] $[RANDOM%256] $[RANDOM%256])
NEW_MAC_ADDRESS_2=$(printf '52:54:00:%02X:%02X:%02X\n' $[RANDOM%256] $[RANDOM%256] $[RANDOM%256])
NEW_UUID=$(cat /proc/sys/kernel/random/uuid)
echo "NEW_MAC_ADDRESS_1=$NEW_MAC_ADDRESS_1"
echo "NEW_MAC_ADDRESS_2=$NEW_MAC_ADDRESS_2"
echo "NEW_UUID =$NEW_UUID"
echo "VM_NAME  =$VM_NAME"

OLD_MAC_ADDRESS_1="52:54:00:5f:ca:40"
OLD_MAC_ADDRESS_2="52:54:00:66:a5:e6"
OLD_UUID="dc71bdbe-397d-42bb-9cb7-2328d0cafc25"
OLD_NAME="orchestrator-golden-image"

sed -i "s/$OLD_MAC_ADDRESS_1/$NEW_MAC_ADDRESS_1/g" $CONFIG_FILE
sed -i "s/$OLD_MAC_ADDRESS_2/$NEW_MAC_ADDRESS_2/g" $CONFIG_FILE
sed -i "s/$OLD_UUID/$NEW_UUID/g" $CONFIG_FILE
sed -i "s/$OLD_NAME/$VM_NAME/g" $CONFIG_FILE
sed -i "s/>16<\/vcpu>/>$CORES<\/vcpu>/g" $CONFIG_FILE

virsh define $CONFIG_FILE

virsh setmaxmem $VM_NAME "$MEMORY"G --config
virsh setmem    $VM_NAME "$MEMORY"G --config