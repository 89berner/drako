#!/bin/bash

echo "Killing ssh sessions..."
pkill ssh

echo "Opening ssh to PARROT on port 8765"
ssh -N -i .keys/id_rsa -L 8765:localhost:8765 ubuntu@web.prod.drako.ai &
sleep 1
echo "You can connect now to PARROT with ssh -i .keys/id_rsa root@localhost -p 8765"

echo "Opening ssh to CASTLE on port 8766"
ssh -N -i .keys/id_rsa -L 8766:localhost:8766 ubuntu@web.prod.drako.ai &
sleep 1
echo "You can connect now to CASTLE with ssh -i .keys/id_rsa root@localhost -p 8766"

echo "Waiting for 10 seconds to have parrot link working"
sleep 10
echo "Opening now connection for Parrot Mysql"
ssh -N -i .keys/id_rsa -L 3306:192.168.2.10:3306 root@localhost -p 8765 &
sleep 1
echo "Now you can connect locally to 3306"


ssh -N -i .keys/id_rsa -L 443:localhost:443 192.168.122.238 &