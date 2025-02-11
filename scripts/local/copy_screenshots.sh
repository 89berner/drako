#!/bin/bash

rm -f resources/screenshots/*; scp -i .keys/id_rsa 'root@192.168.2.10:/root/drako/services/lawliet/screenshots/*' resources/screenshots
