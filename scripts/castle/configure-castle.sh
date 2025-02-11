#!/bin/bash

echo "THIS IS DEPRECATED!!!!"
exit 1

# set -e
# set +x

# echo "This configuration is for Ubuntu 22.04 LTS"

# if [ "$EUID" -ne 0 ]
#   then echo "Please run as root"
#   exit
# fi

# echo $(date) >/tmp/start

# apt-get update

# apt-get install -y python3-pip

# # sudo add-apt-repository ppa:deadsnakes/ppa

# # apt-get install -y python3.7 python3.7-dev python3-pip

# # rm /usr/bin/python3 2>/dev/null
# # ln -s  /usr/bin/python3.7 /usr/bin/python3

# # rm /usr/bin/python 2>/dev/null
# # ln -s  /usr/bin/python3.7 /usr/bin/python

# apt-get install -y apt-transport-https ca-certificates curl gnupg-agent software-properties-common gcc-multilib cmake openvpn \
# net-tools screen htop iotop glances nmap traceroute jq wondershaper linux-headers-$(uname -r) mysql-client

# curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
# add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"

# apt-get install -y docker-ce docker-ce-cli containerd.io

# echo "Configure pymetasploit"
# git clone https://github.com/DanMcInerney/pymetasploit3.git && cd pymetasploit3 && sudo pip3 install .

# pip3 install docker pyfiglet==0.8.post1 mysql-connector-python==8.0.22 requests==2.24.0 dictdiffer==0.8.1 numpy==1.23.0

# systemctl restart docker

# echo "Create /shared folder"
# mkdir -p /shared/logs

# #sudo curl -L "https://github.com/docker/compose/releases/download/1.26.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
# # sudo chmod +x /usr/local/bin/docker-compose

# # echo "Increase open files"
# # ulimit -Hn 10485760
# # ulimit -Sn 10485760

# echo '* soft nofile 1000000' >> /etc/security/limits.conf
# echo '* hard nofile 1000000' >> /etc/security/limits.conf
# echo "fs.file-max = 1000000" >> /etc/sysctl.conf
# sysctl -p

# # FOR PARROT

# pip3 install boto3

# echo "SWAP"
# fallocate -l 5G /swapfile #120G
# chmod 600 /swapfile
# mkswap /swapfile
# swapon /swapfile
# echo '/swapfile       none    swap    sw      0       0' >> /etc/fstab
# # /swapfile       none    swap    sw      0       0


# echo $(date) > /root/ready