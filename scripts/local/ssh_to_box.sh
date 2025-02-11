#!/bin/bash

echo "SSHing into $1"

# SHARED CONSTANTS
. /Users/juanberner/repos/drako/scripts/common/constants.env TUNNEL_SSH CITY_SSH_PORT CITY_IP CASTLE_SSH_PORT CASTLE_IP WEB_SSH_PORT WEB_DNS LEARNER_IP ML_IP

if [[ "$1" = "city" ]]; then
	ssh -i .keys/id_rsa -p $CITY_SSH_PORT root@$CITY_IP
elif [[ "$1" = "castle" ]]; then
	ssh -i .keys/id_rsa -p $CASTLE_SSH_PORT root@$CASTLE_IP
elif [[ "$1" = "web" || "$1" = "Web" || "$1" = "WEB" ]]; then
	ssh -i .keys/id_rsa -p $WEB_SSH_PORT ubuntu@$WEB_DNS
elif [[ "$1" = "learner" ]]; then
	ssh -i .keys/id_rsa -p 22 ubuntu@$LEARNER_IP
elif [[ "$1" = "tunnel" ]]; then
	ssh -i .keys/id_rsa -p 22 ubuntu@$TUNNEL_SSH
elif [[ "$1" = "bitf" ]]; then
	ssh -i .keys/id_rsa -p 22 root@88.99.249.254
elif [[ "$1" = "outpost1" ]]; then
        ssh -i .keys/id_rsa -p 22 root@94.130.206.50
elif [[ "$1" = "ml" ]]; then
	ssh -o StrictHostKeyChecking=no -i .keys/id_rsa -p 22 root@$ML_IP
elif [[ "$1" = "audio" ]]; then
	AUDIO_IP=$(aws ec2 describe-instances --filters "Name=tag:Name,Values=audio" --query 'Reservations[].Instances[?State.Name==`running`].PublicIpAddress' --output text)
	echo "AUDIO_IP IS $AUDIO_IP"
	ssh -o StrictHostKeyChecking=no -i .keys/id_rsa -p 22 root@$AUDIO_IP
elif [[ "$1" = "audio-spot" ]]; then
        AUDIO_IP=$(aws ec2 describe-instances --filters "Name=tag:Name,Values=ml-audio-spot" --query 'Reservations[].Instances[?State.Name==`running`].PublicIpAddress' --output text)
        echo "AUDIO_IP IS $AUDIO_IP"
        ssh -o StrictHostKeyChecking=no -i .keys/id_rsa -p 22 root@$AUDIO_IP
else
	echo "I dont know how to access $1"
fi
