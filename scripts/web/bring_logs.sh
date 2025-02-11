#!/bin/bash

# ENV CONSTANTS
KEYS_FOLDER_PATH="/root/.ssh/"
# ! ENV CONSTANTS

LOGS_FOLDER_PATH="/share/logs"
LOGS_COMPRESSED_FILE="logs.tar.gz"

FOLDER_PATH="/tmp/logs-retrieved"
echo "Deleting logs.."
rm -rf /$FOLDER_PATH/*

PARROT_DEST="127.0.0.1"
PARROT_PORT="8765"

CASTLE_DEST="127.0.0.1"
CASTLE_PORT="8766"

echo "Bringing to folder logs from parrot trainer"
mkdir -p $FOLDER_PATH/parrot/
ssh    -i $KEYS_FOLDER_PATH/id_rsa root@$PARROT_DEST "tar -cvzf $LOGS_COMPRESSED_FILE $LOGS_FOLDER_PATH/*"
echo "Bringing the compressed file locally"
scp -r -i $KEYS_FOLDER_PATH/id_rsa -p $PARROT_PORT root@$PARROT_DEST:/tmp/$LOGS_COMPRESSED_FILE $FOLDER_PATH/parrot/

echo "Bringing to folder logs from castle agents"
mkdir -p $FOLDER_PATH/castle/
# First compress the logs
ssh    -i $KEYS_FOLDER_PATH/id_rsa -p $CASTLE_PORT root@$CASTLE_DEST "tar -cvzf /tmp/$LOGS_COMPRESSED_FILE $LOGS_FOLDER_PATH/*"
echo "Bringing the compressed file locally"
scp -r -i $KEYS_FOLDER_PATH/id_rsa -p $CASTLE_PORT root@$CASTLE_DEST:/tmp/$LOGS_COMPRESSED_FILE $FOLDER_PATH/castle/