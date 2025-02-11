#!/bin/bash

set -e
set +x

echo "Changing directory to /root/drako"
cd /root/drako

. /root/drako/scripts/common/constants.env DRAKO_FOLDER_PATH

echo "This configuration is for Ubuntu 22.04 LTS"

if [ "$EUID" -ne 0 ]
  then echo "Please run as root"
  exit
fi

apt-get update

apt-get install -y apt-transport-https ca-certificates curl gnupg-agent software-properties-common openvpn net-tools \
htop screen iotop glances nmap traceroute pkg-config hwinfo jq linux-headers-$(uname -r) wondershaper python3-pip mysql-client awscli vim nano tcpdump inetutils-ping
# gcc-multilib cmake

curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"

apt-get install -y docker-ce docker-ce-cli containerd.io

# add-apt-repository ppa:deadsnakes/ppa

# apt-get install -y python3.7 python3.7-dev python3-pip

# read

# rm /usr/bin/python3 2>/dev/null
# ln -s  /usr/bin/python3.7 /usr/bin/python3

# rm /usr/bin/python 2>/dev/null
# ln -s  /usr/bin/python3.7 /usr/bin/python

# sudo apt remove python3-apt
# sudo apt autoremove
# sudo apt autoclean
# sudo apt install python3-apt

# apt-get install -y software-properties-common

# echo "Configure pymetasploit"
# git clone https://github.com/DanMcInerney/pymetasploit3.git && cd pymetasploit3 && sudo pip3 install .

pip3 install -r $DRAKO_FOLDER_PATH/services/agent-base/resources/requirements.txt
pip3 install boto3

echo "Create /share folders"
mkdir -p /share/networks
mkdir -p /share/mysql
mkdir -p /share/notebooks
mkdir -p /share/logs

# https://www.fosstechnix.com/how-to-install-mysql-5-7-on-ubuntu-20-04-lts/
# wget https://dev.mysql.com/get/mysql-apt-config_0.8.12-1_all.deb
# dpkg -i mysql-apt-config_0.8.12-1_all.deb 
#pick ubuntu bionic

# apt install -y mysql-server mysql-client


# apt-get update
# apt-cache policy mysql-server
# apt install -f mysql-client=5.7.32-1ubuntu18.04
# apt install -f mysql-community-server=5.7.32-1ubuntu18.04

# cp $DRAKO_FOLDER_PATH/resources/parrot/mysqld.cnf /etc/mysql/mysql.conf.d/mysqld.cnf

# INSTALLING NVIDIA CONTAINER TOOLKIT
# https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html#install-guide
# distribution=$(. /etc/os-release;echo $ID$VERSION_ID) \
#    && curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add - \
#    && curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
# apt-get update
# apt-get install -y nvidia-docker2 nvidia-utils-470
# systemctl restart docker

# Maybe sudo apt install -y nvidia-driver-460-server?

# echo "Install TERRAFORM"
# curl -fsSL https://apt.releases.hashicorp.com/gpg | sudo apt-key add -
# apt-add-repository "deb [arch=amd64] https://apt.releases.hashicorp.com $(lsb_release -cs) main"
# apt-get update && sudo apt-get install terraform npm

# npm install -g sass pug pug-cli

# cd /tmp/; curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && unzip awscliv2.zip && ./aws/install

# echo "CONFIGURE MYSQL DISK"
# mv /var/lib/mysql/* /data/mysql/

# echo "Now run!"
# cat scripts/parrot/configure_mysql.sql | mysql

# cp scripts/parrot/mysqld.cnf /etc/mysql/mysql.conf.d/mysqld.cnf

# service mysql restart

# cat resources/dragon_prod_latest.sql |mysql dragon;

# test mysql access with mysql -h 54.75.106.40 -u root -pgsmpom3943odhasoi13

# echo "SWAP"
# fallocate -l 10G /swapfile #120G
# chmod 600 /swapfile
# mkswap /swapfile
# swapon /swapfile

# echo '/swapfile       none    swap    sw      0       0' >> /etc/fstab

# echo "CONFIGURE AWS"
# aws configure

# echo "Now in mysql run: SET GLOBAL sql_mode=(SELECT REPLACE(@@sql_mode,'ONLY_FULL_GROUP_BY',''));"
# read