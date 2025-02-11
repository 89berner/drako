#!/bin/bash

VM_NAME=$1

if [ -z "$VM_NAME" ]; then
	VM_NAME=$1
fi

echo "Will connect to VM $VM_NAME"

# 1) Get IP from KVM BASED ON VM MACHINE

IP_ADDR=$(virsh domifaddr $VM_NAME --source=agent|grep enp1s0|grep ipv4|awk '{print $4}'|cut -d '/' -f 1)
IP_ADDR_2=$(virsh domifaddr $VM_NAME |grep enp1s0|grep ipv4|awk '{print $4}'|cut -d '/' -f 1)

echo "Connecting to $IP_ADDR"
ssh -oUserKnownHostsFile=/dev/null -oStrictHostKeyChecking=no -i /root/drako/.keys/id_rsa root@$IP_ADDR

echo "Connecting to $IP_ADDR_2"
ssh -oUserKnownHostsFile=/dev/null -oStrictHostKeyChecking=no -i /root/drako/.keys/id_rsa root@$IP_ADDR_2