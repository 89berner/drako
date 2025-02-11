#!/bin/bash

set -x

SOURCE_PORT=$1
PORT=$2
IP=$3
TARGET_HOST=$4

echo "$(date) -> $PORT:$TARGET_HOST"
if pgrep -f "$PORT:$TARGET_HOST"; then
	echo "SSH Tunnel already created, will exit"
else
	echo "Will create a tunnel on port $PORT"
	ssh -o StrictHostKeyChecking=no -i /root/drako/.keys/id_rsa -R :$PORT:$TARGET_HOST:$SOURCE_PORT root@$IP -f -N
	echo "Tunnel created!"
fi