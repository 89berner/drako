#!/bin/bash

echo "Changing directory to /root/drako"
cd /root/drako

. /root/drako/scripts/common/constants.env DRAGON_PROD_DNS DRAGON_DB_PWD DRAGON_PROD_DB_NAME DRAGON_DB_PORT RECON_PROD_DB_NAME

echo "Starting at $(date)"
start=`date +%s`

# LOCK LOGIC
LOCK_FILE="/tmp/backup_db.lock"

remove_lock() {
  echo "Error, will remove the lock"
  rm $LOCK_FILE
  echo $(date)
  exit 0
}
trap "remove_lock" ERR
trap "remove_lock" INT

if test -f $LOCK_FILE; then
  echo "<<Previous script is not finished yet, will wait 5 seconds and exit.>>"
  echo $(date)
  sleep 5
  exit 0
fi

touch $LOCK_FILE # create lock
# FINISH LOCK LOGIC

TEMP_MYSQL_DUMP_FOLDER="/data/nas/backups/city-mysqldump-$(date '+%Y_%m_%d')"

echo "Dumping all the data in the LOCAL DB for $DRAGON_PROD_DNS $DRAGON_DB_PWD $DRAGON_PROD_DB_NAME at port $DRAGON_DB_PORT"
mkdir $TEMP_MYSQL_DUMP_FOLDER || true
mysqldump --hex-blob --quick --max_allowed_packet=512M --column-statistics=0 --set-gtid-purged=OFF -P$DRAGON_DB_PORT -h $DRAGON_PROD_DNS -uroot -p$DRAGON_DB_PWD $DRAGON_PROD_DB_NAME | gzip -9 -c > $TEMP_MYSQL_DUMP_FOLDER/dragon.sql.gz
mysqldump --hex-blob --quick --max_allowed_packet=512M --column-statistics=0 --set-gtid-purged=OFF -P$DRAGON_DB_PORT -h $DRAGON_PROD_DNS -uroot -p$DRAGON_DB_PWD $RECON_PROD_DB_NAME | gzip -9 -c > $TEMP_MYSQL_DUMP_FOLDER/dragon.sql.gz

end=`date +%s`
runtime_in_seconds=$((end-start))
runtime_in_minutes=$(( runtime_in_seconds / 60 ))
echo "$(date "+%Y-%m-%d %H:%M:%S") runtime: $runtime_in_minutes minutes ($runtime_in_seconds secs)"

# REMOVE LOCK
rm $LOCK_FILE
# FINISH REMOVING LOCK
