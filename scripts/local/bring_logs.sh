#!/bin/bash

# ENV CONSTANTS
DRAKO_FOLDER_PATH="/Users/juanberner/Raen/projects/drako"

# ! ENV CONSTANTS

LOGS_FOLDER_PATH="/share/logs"
LOGS_COMPRESSED_FILE="logs.tar.gz"

FOLDER=logs-$RANDOM
FOLDER_PATH="/tmp/$FOLDER"

echo "Deleting logs.."
rm -rf /tmp/logs*

echo "Bringing to folder logs from parrot trainer"
mkdir -p $FOLDER_PATH/parrot/
ssh -i $DRAKO_FOLDER_PATH/.keys/id_rsa root@192.168.2.10 "tar -cvzf /tmp/$LOGS_COMPRESSED_FILE $LOGS_FOLDER_PATH/*"
echo "Bringing the compressed file locally"
scp -r -i $DRAKO_FOLDER_PATH/.keys/id_rsa root@192.168.2.10:/tmp/$LOGS_COMPRESSED_FILE $FOLDER_PATH/parrot/
echo "Now extracting"
cd $FOLDER_PATH/parrot; tar -xvzf $FOLDER_PATH/parrot/$LOGS_COMPRESSED_FILE; mv $FOLDER_PATH/parrot/share/logs/* $FOLDER_PATH/parrot/; rmdir /share/logs; rmdir /share/;

echo "Bringing to folder logs from castle agents"
mkdir -p $FOLDER_PATH/castle/
# First compress the logs
ssh    -i $DRAKO_FOLDER_PATH/.keys/id_rsa root@192.168.2.11 "tar -cvzf /tmp/$LOGS_COMPRESSED_FILE $LOGS_FOLDER_PATH/*"
echo "Bringing the compressed file locally"
scp -r -i $DRAKO_FOLDER_PATH/.keys/id_rsa root@192.168.2.11:/tmp/$LOGS_COMPRESSED_FILE $FOLDER_PATH/castle/
echo "Now extracting"
cd $FOLDER_PATH/castle; tar -xvzf $FOLDER_PATH/castle/$LOGS_COMPRESSED_FILE; mv $FOLDER_PATH/castle/share/logs/* $FOLDER_PATH/castle/; rmdir /share/logs; rmdir /share/;

echo "Now open logs!"
subl -n -a $FOLDER_PATH