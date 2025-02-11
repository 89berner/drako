import argparse
import sys
sys.path.append("/root/drako/services/main/")

from lib.Common.Utils.Db import Db

import lib.Common.Utils.Constants  as Constants
import lib.Common.Utils.Log        as Log
import lib.Training.Trainer.Common as Common

argparser = argparse.ArgumentParser(description='Use migrate_training.py to migrate a training to production')
argparser.add_argument('--training_id', dest='training_id', type=int, help='specify training_game_id to delete from PROD DB', required=True)
args = argparser.parse_args()

Log.initialize_log("2")

# def get_training_game_ids_for_training_id(training_id):
#     stmt = "SELECT training_game_id FROM training_game WHERE training_id=%s"
#     results = connection.query(stmt, (training_id,))
#     current_training_ids = []
#     for result in results:
#         current_training_ids.append(result['training_game_id'])
#
#     return current_training_ids

prod_connection = Db(db_host=Constants.DRAGON_PROD_DNS, db_name=Constants.DRAGON_PROD_DB_NAME, db_password=Constants.DRAGON_DB_PWD)

Log.logger.warning(f"Will start deleting from PROD training {args.training_id}")
Common.delete_all_instances_of_training_in_prod(prod_connection, args.training_id)

prod_connection.close()

