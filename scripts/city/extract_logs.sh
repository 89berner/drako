#!/bin/bash

VM_NAME=$1

if [ -z "$VM_NAME" ]; then
	VM_NAME=$1
fi

echo "Will connect to VM $VM_NAME"

# 1) Get IP from KVM BASED ON VM MACHINE

IP_ADDR=$(virsh domifaddr $VM_NAME --source=agent|grep enp1s0|grep ipv4|awk '{print $4}'|cut -d '/' -f 1)

echo "First ensuring the backups folder is present"
FOLDER_PATH="/root/backups/$VM_NAME-$(date "+%Y_%m_%d_%H_%M")"
mkdir -p $FOLDER_PATH

echo "Creating an archive of logs inside of $IP_ADDR"

ssh root@$IP_ADDR -oUserKnownHostsFile=/dev/null -oStrictHostKeyChecking=no -i /root/drako/.keys/id_rsa "tar -cvzf /tmp/logs.tar.gz --directory /share/logs ."
scp -oUserKnownHostsFile=/dev/null -oStrictHostKeyChecking=no -i /root/drako/.keys/id_rsa root@$IP_ADDR:/tmp/logs.tar.gz $FOLDER_PATH/
echo "Now extracting the contents"
cd $FOLDER_PATH; tar -xvzf logs.tar.gz