sudo apt-get update && sudo apt-get upgrade

apt -y install tzdata
dpkg-reconfigure tzdata

apt update && apt -y install ca-certificates wget net-tools gnupg
wget https://as-repository.openvpn.net/as-repo-public.asc -qO /etc/apt/trusted.gpg.d/as-repository.asc
echo "deb [arch=amd64 signed-by=/etc/apt/trusted.gpg.d/as-repository.asc] http://as-repository.openvpn.net/as/debian jammy main">/etc/apt/sources.list.d/openvpn-as-repo.list
apt update && apt -y install openvpn-as

cat /usr/local/openvpn_as#/init.log to get password

tcpdump "src port 443 and tcp[tcpflags] & (tcp-syn|tcp-ack) == (tcp-syn|tcp-ack)" -n -i eth0

/msg nater register nater020323 nlsemimasked@pm.me


sysctl net.ipv4.ip_local_port_range="15000 61000"

sysctl net.ipv4.tcp_fin_timeout=30
sysctl net.ipv4.tcp_tw_reuse=1 

