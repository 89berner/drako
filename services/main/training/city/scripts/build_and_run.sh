#!/bin/bash

docker container rm -f $(docker container ls -aq --filter name=manager)
docker build -t manager -f services/main/training/city/Dockerfile.manager services/main 
docker run --name manager -p 4000:4000 -v /var/lib/libvirt/images/:/var/lib/libvirt/images/ -v /etc/libvirt/qemu/:/etc/libvirt/qemu/ -v /run/libvirt/libvirt-sock:/app/libvirt-sock -it -t manager