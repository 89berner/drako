#!/bin/bash

. scripts/common/constants.env AWS_PARROT_PROXY PARROT_PORT_FOR_SSH_AND_SYNC PARROT_IP

#rm -f resources/graphs/*; 
scp -r -C -i .keys/id_rsa -P$PARROT_PORT_FOR_SSH_AND_SYNC root@$PARROT_IP:'/root/drako/resources/graphs/*' resources/graphs
#rsync -avz -e "ssh -i .keys/id_rsa" root@192.168.178.10:/tmp/graphs/ /Users/jberner/Raen/projects/drako/resources/graphs/
