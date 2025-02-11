#!/bin/bash

# first copy to home key the key needed

# https://tecadmin.net/how-to-configure-static-ip-address-on-ubuntu-22-04/
# /etc/netplan/01-netcfg.yaml
# network:
#     version: 2
#     renderer: networkd
#     ethernets:
#         eno1:
#             dhcp4: false
#             addresses:
#                 - 192.168.1.12/24
#             nameservers:
#                 addresses: [8.8.8.8, 8.8.4.4]
#             routes:
#                 - to: default
#                   via: 192.168.1.1
#         eno2:
#             dhcp4: false
#             addresses:
#                 - 192.168.1.13/24
#             nameservers:
#                 addresses: [8.8.8.8, 8.8.4.4]
#         eno3:
#           dhcp4: true
#         eno4:
#           dhcp4: true


echo "This configuration is for Ubuntu 22.04 LTS"

if [ "$EUID" -ne 0 ]
  then echo "Please run as root"
  exit
fi

echo "Changing directory to /root/drako"
cd /root/drako

. /root/drako/scripts/common/constants.env DRAKO_FOLDER_PATH VIRSH_IMAGE_FILE_LOCATION

apt-get update

apt-get install -y apt-transport-https ca-certificates curl gnupg-agent software-properties-common gcc-multilib cmake openvpn net-tools \
htop screen iotop glances nmap traceroute graphviz libgraphviz-dev pkg-config hwinfo jq linux-headers-$(uname -r) wondershaper python3-pip mysql-client awscli vim nano

curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"

apt-get install -y docker-ce docker-ce-cli containerd.io unzip

apt install -y qemu-kvm virt-manager libvirt-daemon-system virtinst libvirt-clients bridge-utils libguestfs-tools genisoimage libosinfo-bin nocache nfs-common cron p7zip-full unrar

# apt-get install mysql-server-8.0
# cp $DRAKO_FOLDER_PATH/scripts/city/mysqld.cnf /etc/mysql/mysql.conf.d/mysqld.cnf
# cat scripts/city/configure_mysql.sql | mysql

systemctl enable --now libvirtd
systemctl start libvirtd

# optional
# usermod -aG libvirt $USER
# usermod -aG kvm $USER

pip3 install -r $DRAKO_FOLDER_PATH/services/agent-base/resources/requirements.txt
pip3 install boto3

echo "Create /share folders"
mkdir -p /share/networks
mkdir -p /share/mysql
mkdir -p /share/notebooks
mkdir -p /share/logs

echo "SWAP"
fallocate -l 50G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile       none    swap    sw      0       0' >> /etc/fstab

echo "Mount folder"
/bin/bash $DRAKO_FOLDER_PATH/scripts/city/mount_nas.sh

echo "Add to cron"
echo '* * * * * /bin/bash $DRAKO_FOLDER_PATH/scripts/city/mount_nas.sh 2>&1 >> /var/log/mount_nas.log' > /var/spool/cron/crontabs/root

echo "Now download base images"

cd $VIRSH_IMAGE_FILE_LOCATION
wget https://releases.ubuntu.com/22.04/ubuntu-22.04.1-live-server-amd64.iso

echo "CONFIGURE AWS"
aws configure
