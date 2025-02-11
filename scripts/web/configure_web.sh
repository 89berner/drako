#!/bin/bash

set -e
set +x

echo "This configuration is for Ubuntu 22.04 LTS"

if [ "$EUID" -ne 0 ]
  then echo "Please run as root"
  exit
fi

apt-get update

apt-get install -y apt-transport-https ca-certificates curl gnupg-agent software-properties-common gcc-multilib cmake net-tools \
htop screen iotop glances nmap traceroute pkg-config hwinfo jq linux-headers-$(uname -r)  python3-pip mysql-client awscli

curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"

apt-get install -y docker-ce docker-ce-cli containerd.io

echo "Create /share folders"
mkdir -p /share/networks
mkdir -p /share/logs
chown -R ubuntu:ubuntu /share

hostname web

