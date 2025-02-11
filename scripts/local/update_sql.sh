#!/bin/bash

set -x

#DB_HOST="192.168.1.12"
DB_HOST="127.0.0.1"

mysqldump -h $DB_HOST -P6612 -uroot -pgsmpom3943odhasoi13 --no-data --ignore-table=dragon.training_config --ignore-table=dragon.agent_config dragon | sed 's/ AUTO_INCREMENT=[0-9]*//g' > resources/dragon_prod_latest.sql
mysqldump -h $DB_HOST -P6612 -uroot -pgsmpom3943odhasoi13 dragon training_config agent_config | sed 's/ AUTO_INCREMENT=[0-9]*//g' >> resources/dragon_prod_latest.sql

mysqldump -h $DB_HOST -P6612 -uroot -pgsmpom3943odhasoi13 recon target setting | sed 's/ AUTO_INCREMENT=[0-9]*//g' > resources/recon_latest.sql
mysqldump -h $DB_HOST -P6612 -uroot -pgsmpom3943odhasoi13 --no-data --ignore-table=recon.target --ignore-table=recon.setting recon | sed 's/ AUTO_INCREMENT=[0-9]*//g' >> resources/recon_latest.sql