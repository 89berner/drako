#!/bin/bash

echo "Will now start syncing every time we write into the folder"

DRAKO_FOLDER_PATH="/Users/juanberner/repos/drako"

# SHARED CONSTANTS
. $DRAKO_FOLDER_PATH/scripts/common/constants.env CITY_SSH_PORT CITY_IP TUNNEL_SSH

CITY_AWS_SSH_PORT=12223

fswatch -o . | while read f
do
    date;
    echo "Syncing CITY"
    rsync -e"ssh -p $CITY_SSH_PORT -i $DRAKO_FOLDER_PATH/.keys/id_rsa" -avz --delete --exclude-from=$DRAKO_FOLDER_PATH/.rsyncexclude $DRAKO_FOLDER_PATH root@$CITY_IP:/root/
done