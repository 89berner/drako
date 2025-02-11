#!/bin/bash

# SHARED CONSTANTS
. /Users/juanberner/repos/drako/scripts/common/constants.env TUNNEL_SSH

sudo ssh -i .keys/id_rsa -L 5000:127.0.0.1:5000 root@$TUNNEL_SSH -N -f
sudo ssh -i .keys/id_rsa -L 5001:127.0.0.1:5000 root@$TUNNEL_SSH -N -f
sudo ssh -i .keys/id_rsa -L 8080:127.0.0.1:8080 root@$TUNNEL_SSH -N -f
sudo ssh -i .keys/id_rsa -L 3306:127.0.0.1:3306 root@$TUNNEL_SSH -N -f
sudo ssh -i .keys/id_rsa -L 6612:127.0.0.1:6612 root@$TUNNEL_SSH -N -f
sudo ssh -i .keys/id_rsa -L 3000:127.0.0.1:3000 root@$TUNNEL_SSH -N -f
sudo ssh -i .keys/id_rsa -L 5601:127.0.0.1:5601 root@$TUNNEL_SSH -N -f
# sudo ssh -i .keys/id_rsa -L 9200:127.0.0.1:9200 root@$TUNNEL_SSH -N -f
