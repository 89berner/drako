# python learner.py --log-level=0 --script-name=script.txt

import argparse
import time
import traceback

import lib.Common.Utils.Constants    as Constants
from lib.Training.Learner.Builder import build_learner
import lib.Common.Utils.Log as Log
import lib.Common.Exploration.Actions as Actions
import lib.Common.Utils as Utils

argparser = argparse.ArgumentParser(description='Use Learner from command line')
argparser.add_argument('--profile',                    dest='profile',                    type=str,            help='profile for learner', choices=('EXPLORE', 'TRAIN', 'EXPLORE_AND_TRAIN', "BENCHMARK"), required=True)
argparser.add_argument('--log-level',                  dest='log_level',                  type=str,            help='specify the log level', default=0, choices=("0", "1", "2", "3"))
argparser.add_argument('--learner_name',               dest='learner_name',               type=str,            help='learner to use')
argparser.add_argument('--game_type',                  dest='game_type',                  type=str,            help='game_type to focus learning on')
argparser.add_argument('--training_id',                dest='training_id',                type=int,            help='optional training id to use',     required=True)
argparser.add_argument('--load_main_training',         dest='load_main_training',         type=Utils.str2bool, help='should we load from the main training instead of building a new NN', default=False,)
argparser.add_argument('--continue_from_latest_point', dest='continue_from_latest_point', type=Utils.str2bool, help='continue from latest point',             default=True)
argparser.add_argument('--force_cpu',                  dest='force_cpu',                  type=Utils.str2bool, help='force the usage of cpu instead of cuda', default=False,)

def main(args):
    learner_name               = args.learner_name
    game_type                  = args.game_type
    training_id                = args.training_id
    load_main_training         = args.load_main_training
    log_level                  = args.log_level
    profile                    = args.profile
    continue_from_latest_point = args.continue_from_latest_point
    force_cpu                  = args.force_cpu

    log_filename = f"{Constants.LOGS_FOLDER_PATH}/{training_id}/{learner_name}_{game_type}.log"

    Log.initialize_log(log_level, log_filename)
    Log.logger.info(f"Starting with log level: {log_level} and load_main_training {load_main_training}")
    Log.add_info_large_ascii(game_type)

    # LEARNER DEPEND ON ACTIONS BEING INITIALIZED
    Actions.initialize()
    Actions.client.load_metasploit_actions()

    # INITIALIZE LEARNER
    learner = build_learner(game_type, learner_name, training_id, load_main_training, profile, continue_from_latest_point, force_cpu=force_cpu)

    counter = 0
    while counter < 10:
        counter += 1
        try:
            Log.logger.info("(%d/10) Starting learn process" % counter)

            finished = learner.learn()
            if finished:
                break
        except:
            Log.logger.error("[-] ERROR: %s. Will end this iteration of learner." % traceback.format_exc().strip())
            time.sleep(60)

        Log.logger.info("(%d/10) Finished learn process" % counter)

    learner.staging_connection.close()
    learner.prod_connection.close()

if __name__ == '__main__':
    # SETTING UP LOGGER
    args = argparser.parse_args()

    main(args)
