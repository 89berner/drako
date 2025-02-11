#!/bin/bash

OUTPOST_IP="135.181.1.101"

sudo apt-get update && sudo apt-get upgrade
apt update && apt -y install ca-certificates wget iotop net-tools gnupg nethogs tzdata glances apt-transport-https curl software-properties-common awscli mysql-client iftop snapd unzip squid apache2-utils
dpkg-reconfigure tzdata snapd

# Install docker:
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update && apt-cache policy docker-ce && sudo apt -y install docker-ce

# Kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

# MicroK8s
sudo snap install microk8s --classic
microk8s status --wait-ready
microk8s enable metrics-server dashboard dns registry

echo "Now copy the kubectl configuration to other boxes, MODIFY THE IP ADDRESS"
microk8s.kubectl config view --raw | sed "s/127\.0\.0\.1/$OUTPOST_IP/g"  > /root/.kube/config
read

## CONFIGURE MAX PODS AND SSH:
grep -q -- '--max-pods=250' /var/snap/microk8s/current/args/kubelet || echo '--max-pods=250' >> /var/snap/microk8s/current/args/kubelet

### ADD to /var/snap/microk8s/current/args/kubelet
--config=${SNAP_DATA}/args/kubelet.conf
### REPLACE IN THE SAME FILE
--feature-gates=DevicePlugins=true,NodeSwap=true

## CREATE kubelet.conf with
cat << 'EOF' > /var/snap/microk8s/current/args/kubelet.conf
apiVersion: kubelet.config.k8s.io/v1beta1
kind: KubeletConfiguration
memorySwap:
  swapBehavior: UnlimitedSwap
EOF

curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

echo "Add the following details:
XXXXX
FFFFF
eu-west-1
json"

echo "Configure AWS"
aws configure

cat << 'EOF' > pull_and_tag_image.sh
#!/bin/bash

aws ecr get-login-password --region ap-south-1 | sudo docker login --username AWS --password-stdin 320567054459.dkr.ecr.ap-south-1.amazonaws.com
docker pull 320567054459.dkr.ecr.ap-south-1.amazonaws.com/recon_x86:latest
docker tag 320567054459.dkr.ecr.ap-south-1.amazonaws.com/recon_x86:latest localhost:32000/recon_x86:latest
docker push localhost:32000/recon_x86:latest
EOF
chmod +x pull_and_tag_image.sh

cat << 'EOF' > set_sysctl.sh
#!/bin/bash
#@reboot /root/set_sysctl.sh
sysctl -w net.ipv4.ip_local_port_range="15000 61000"
sysctl -w net.ipv4.tcp_fin_timeout=30
sysctl -w net.ipv4.tcp_tw_reuse=1
sysctl -w fs.inotify.max_queued_events=163840
sysctl -w fs.inotify.max_user_instances=1280
sysctl -w fs.inotify.max_user_watches=1655360
sysctl -w fs.file-max=9223372036854775807
sysctl -w vm.swappiness=90
sysctl -w vm.watermark_scale_factor=10
EOF
chmod +x set_sysctl.sh

(crontab -l | grep -q '@reboot /root/set_sysctl.sh') || (crontab -l; echo '@reboot /root/set_sysctl.sh') | crontab -

(grep -q -- 'GatewayPorts Yes' /etc/ssh/sshd_config || echo 'GatewayPorts Yes' >> /etc/ssh/sshd_config) && (grep -q -- 'MaxStartups 1001' /etc/ssh/sshd_config || echo 'MaxStartups 1001' >> /etc/ssh/sshd_config) && (grep -q -- 'PubkeyAcceptedAlgorithms +ssh-rsa # for mole' /etc/ssh/sshd_config || echo 'PubkeyAcceptedAlgorithms +ssh-rsa # for mole' >> /etc/ssh/sshd_config)

service ssh restart
service snap.microk8s.daemon-kubelite restart

sudo fallocate -l 200G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab

### START REVERSE SHELL WITH MOLE IN CITY
# mole start remote --verbose --source 135.181.1.101:6612 --destination 192.168.1.12:6612 --server root@135.181.1.101 -vvv

#while true; do clear; ss -tn dst :443 or dst :80; sleep 1; done

# sudo nano /etc/sysctl.conf -> fs.file-max = 9223372036854775807
# cat /proc/sys/fs/file-max

# wget https://as-repository.openvpn.net/as-repo-public.asc -qO /etc/apt/trusted.gpg.d/as-repository.asc
# echo "deb [arch=amd64 signed-by=/etc/apt/trusted.gpg.d/as-repository.asc] http://as-repository.openvpn.net/as/debian jammy main">/etc/apt/sources.list.d/openvpn-as-repo.list
# apt update && apt -y install openvpn-as

# https://135.181.1.101:943/admin

# INSTALL SQUID

# default values
USERNAME="squiduser"
PASSWORD="a3A"
SQUID_CONF="/etc/squid/squid.conf"
PASSWORD_FILE="/etc/squid/passwords"

# create a new password file with the username and password
# echo "${PASSWORD}" | sudo htpasswd -c -i ${PASSWORD_FILE} ${USERNAME}
echo 'squiduser:$apr1$73LJje.' > /etc/squid/passwords

# adjust file permissions
sudo chown proxy: ${PASSWORD_FILE}

# add configuration for basic auth
sudo bash -c "cat > ${SQUID_CONF}" << EOL
http_port 3128
auth_param basic program /usr/lib/squid/basic_ncsa_auth /etc/squid/passwords
acl authenticated proxy_auth REQUIRED
http_access allow authenticated
EOL

# restart squid to apply changes
sudo systemctl restart squid

# curl -x http://135.181.1.101:3128 -U squiduser:apo http://ifconfig.co

# Login as a normal user (not admin endpoint) and download the profile
# setup in box the details of passwdhetzner for user openvpn
# openvpn
# Dy69l9O

# SETUP FIREWALL TO BLOCK 443 and 943

############################ Kubernetes #############################

# microk8s kubectl describe secret -n kube-system microk8s-dashboard-token

############### CONFIGURE FIREWALL, 

# Create tunnel ssh -i .keys/id_rsa -N -L *:10443:127.0.0.1:10443 root@135.181.1.101
