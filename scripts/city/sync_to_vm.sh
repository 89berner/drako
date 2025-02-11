#!/bin/bash

VM_NAME=$1

if [ -z "$VM_NAME" ]; then
	VM_NAME=$1
fi

IP_ADDR=$(virsh domifaddr $VM_NAME --source=agent|grep enp1s0|grep ipv4|awk '{print $4}'|cut -d '/' -f 1)

echo "Syincing to IP $IP_ADDR"

DRAKO_FOLDER_PATH="/root/drako"

/usr/bin/rsync -e"ssh -oUserKnownHostsFile=/dev/null -oStrictHostKeyChecking=no -p 22 -i $DRAKO_FOLDER_PATH/.keys/id_rsa" -avz --delete --exclude-from=$DRAKO_FOLDER_PATH/.rsyncexclude $DRAKO_FOLDER_PATH root@$IP_ADDR:/root/