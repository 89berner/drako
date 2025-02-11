#!/bin/bash

# mkdir -p /data/city_mysql
# if ! mountpoint /data/city_mysql > /dev/null; then
#     echo "Mounting"
#     mount 192.168.1.11:/volume2/Ephemeral/city_mysql /data/city_mysql
# fi

mkdir -p /data/recon_elasticsearch
if ! mountpoint /data/recon_elasticsearch > /dev/null; then
    echo "Mounting"
    mount 192.168.1.11:/volume2/Ephemeral/recon_elasticsearch /data/recon_elasticsearch
fi

mkdir -p /data/city_images
if ! mountpoint /data/city_images > /dev/null; then
    echo "Mounting"
    mount 192.168.1.11:/volume2/Ephemeral/city_images /data/city_images
fi

8UAJr9GoDuke5uLwBawgMCaL5QYytP3D93LgCAAxysgwdAW8AXX19SChyEgDiAUdDxY3JZjXzsOP48L+WwNwAKitLw+QMMQE6Ow+WCcVzXYC4AgBZnK05MlKTs3MTinOws2r/kTkjI8B52PnZuf2Pj+DicjwogQAGg2s8B+AEAeAZ8hAAWwMhSUZGWclFiRABnIF7YTS2gQAGgJTzE5/RMWosfyc7drwCoi4O7v64Orv/dX+sAPMUAEFt/6113Wf0D8Od5KXVhAAADdBqAe8855XMv4PEJQE7LANjfnssBlNtyCEC2I4EDoNPh52Pnt/fcxrlzfXNnAP