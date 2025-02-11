#!/bin/bash

PORT=$1

echo "$(date)"
if pgrep -f "$PORT:localhost"; then
	echo "SSH Tunnel already created, will exit"
else
	echo "Will create a tunnel on port $PORT"
	ssh -o StrictHostKeyChecking=no -i /root/drako/.keys/id_rsa -R $PORT:localhost:22 ubuntu@web.prod.drako.ai -f -N
	echo "Tunnel created!"
fi