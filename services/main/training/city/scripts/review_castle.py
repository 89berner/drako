import sys
import argparse

sys.path.append("/root/drako/services/main/")
from lib.Common.Training.Learner import get_current_training_training_game_ids, get_training_state_max_transition_id, get_training_states

from lib.Training.Trainer.Common import generate_castle_db_name, generate_castle_name
from lib.Common.Utils import Constants
import lib.Common.Utils as Utils

from lib.Common.Utils.Db import Db
import lib.Common.Utils.Log as Log

argparser = argparse.ArgumentParser(description='Use Review Castle from command line')
argparser.add_argument('--db_name', dest='db_name', required=True, type=str, help='database name')

def get_step_totals(connection):
    results = connection.query("select prev_game_type, count(*) as amount FROM step group by prev_game_type")
    
    step_totals_map = {}
    for res in results:
        step_totals_map[res['prev_game_type']] = res['amount']

    return step_totals_map

def get_goals_map(connection):
    print("Getting goals map")
    results = connection.query("select prev_game_type, action_source, count(*) as amount FROM step group by prev_game_type, action_source ORDER BY prev_game_type, count(*) DESC")

    step_totals_map = get_step_totals(connection)

    goals_map = {}
    for res in results:
        prev_game_type = res['prev_game_type']
        if prev_game_type not in goals_map:
            goals_map[prev_game_type] = {}

        percentage = int(res['amount'] / step_totals_map[prev_game_type] * 100)
        goals_map[prev_game_type][res['action_source']] = f"{res['amount']} ({percentage}%)"
    
    return goals_map

def get_session_map_per_type(connection, session_str):
    # select prev_game_type ,action_name, action_parameters from step where reward_reasons LIKE '%" + session_str + "%' GROUP BY prev_game_type, action_name, action_parameters

    results = connection.query("select prev_game_type ,action_name, count(*) as amount from step where reward_reasons LIKE '%" + session_str + "%' group by prev_game_type, action_name")
    sessions_map = {}

    for res in results:
        if res['prev_game_type'] not in sessions_map:
            sessions_map[res['prev_game_type']] = {}
        sessions_map[res['prev_game_type']][res['action_name']] = res['amount']

    return sessions_map

def get_sessions_map(connection):
    print("Getting sessions map")
    sessions_per_user_map = {
        "regular_user": get_session_map_per_type(connection, Constants.REWARD_FOR_REGULAR_USER_SESSION_KEY),
        "super_user":   get_session_map_per_type(connection, Constants.REWARD_FOR_SUPER_USER_SESSION_KEY),
    }

    sessions_map = {}
    for game_type in Constants.GAME_TYPES:
        sessions_map[game_type] = {}
        for user_type in sessions_per_user_map:
            if game_type in sessions_per_user_map[user_type]:
                sessions_map[game_type][user_type] = sessions_per_user_map[user_type][game_type]
    
    return sessions_map

# def get_steps_per_minute(total_steps, start_date, end_date):


def get_state_hash_map(connection, training_id):
    print("Getting state hash map")
    current_training_game_ids = get_current_training_training_game_ids(connection, training_id)

    state_hash_map = {}
    for game_type in current_training_game_ids:
        if game_type not in state_hash_map:
            state_hash_map[game_type] = {}

        training_game_id = current_training_game_ids[game_type]['training_game_id']
        transition_id   = get_training_state_max_transition_id(connection, training_game_id, Constants.GLOBAL_TARGET)
        training_states = get_training_states(connection, training_game_id, Constants.GLOBAL_TARGET, transition_id)

        state_hash_map[game_type]['total_states'] = len(training_states)

    return state_hash_map

def get_action_distribution_map(connection):
    print("Getting action distribution map")
    results = connection.query("select prev_game_type,action_name,count(*) amount from step group by prev_game_type,action_name ORDER BY count(*) ASC")
    action_distribution_map = {}

    for res in results:
        prev_game_type = res['prev_game_type']
        amount_key     = res['amount']

        if prev_game_type not in action_distribution_map:
            action_distribution_map[prev_game_type] = {}

        if amount_key >= 5 and amount_key < 10:
            amount_key = "5-9"
        elif amount_key >= 10 and amount_key < 50:
            amount_key = "10-49"
        elif amount_key >= 50:
            amount_key = ">50"

        if amount_key not in action_distribution_map[prev_game_type]:
            action_distribution_map[prev_game_type][amount_key] = 0

        action_distribution_map[prev_game_type][amount_key] += 1

    return action_distribution_map

def get_steps_per_hour_map(connection, training_id, reward_reason = None):
    stmt = """
        SELECT prev_game_type, CONCAT(DATE(created_at), " ", HOUR(created_at), ":00:00") as date, count(*) as amount 
        FROM step WHERE training_id=%s AND error is NULL 
    """

    if reward_reason is not None:
        stmt += f" AND reward_reasons LIKE \"%{reward_reason}%\""

    stmt += """
        GROUP BY prev_game_type, CONCAT(DATE(created_at), " ", HOUR(created_at), ":00:00")
        ORDER BY prev_game_type, DATE(created_at), HOUR(created_at)
    """

    results = connection.query(stmt, (training_id, ))
    steps_per_hour_map = {}

    for res in results:
        prev_game_type = res['prev_game_type']
        if prev_game_type not in steps_per_hour_map:
            steps_per_hour_map[prev_game_type] = {}

        date = res['date']
        steps_per_hour_map[prev_game_type][date] = res['amount']

    return steps_per_hour_map

def build_steps_per_hour_map(connection, training_id):
    print("Getting build_steps_per_hour_map")
    all_steps_per_hour_map = get_steps_per_hour_map(connection, training_id)
    regular_steps_per_hour_map = get_steps_per_hour_map(connection, training_id, Constants.REWARD_FOR_REGULAR_USER_SESSION_KEY)
    super_steps_per_hour_map = get_steps_per_hour_map(connection, training_id, Constants.REWARD_FOR_SUPER_USER_SESSION_KEY)

    steps_per_hour_map = {}
    for game_type in all_steps_per_hour_map:
        if game_type not in steps_per_hour_map:
            steps_per_hour_map[game_type] = {}

        for date in all_steps_per_hour_map[game_type]:
            amount_of_regular_sessions = 0
            if game_type in regular_steps_per_hour_map and date in regular_steps_per_hour_map[game_type]:
                amount_of_regular_sessions = regular_steps_per_hour_map[game_type][date]

            amount_of_super_sessions = 0
            if game_type in super_steps_per_hour_map and date in super_steps_per_hour_map[game_type]:
                amount_of_super_sessions = super_steps_per_hour_map[game_type][date]

            val = f"Total steps:{all_steps_per_hour_map[game_type][date]} Regular sessions:{amount_of_regular_sessions} Super Sessions:{amount_of_super_sessions}"
            steps_per_hour_map[game_type][date] = val

    return steps_per_hour_map

def review_training(connection, db_name, training):
    print(f"Reviewing training {training['training_id']}")
    goals_map               = get_goals_map(connection)
    action_distribution_map = get_action_distribution_map(connection)

    state_hash_map     = get_state_hash_map(connection, training['training_id'])
    steps_per_hour_map = build_steps_per_hour_map(connection, training['training_id'])

    # cleanup jsons
    try:
        training['trainer_config'] = Utils.json_loads(training['trainer_config'])
    except:
        print("Can't parse => %s" % training['trainer_config'])


    sessions_map = get_sessions_map(connection)

    avg_steps_per_min_map = {}
    training_targets = []
    training_targets_results = connection.query("select * from training_target")
    for training_target in training_targets_results:
        training_target['extra'] = Utils.json_loads(training_target['extra'])
        training_target_clean = {
            "amount_of_agents":       training_target['amount_of_agents'],
            "taget":                  training_target['extra']['TARGET'],
            "total_steps":            training_target['total_steps'],
            "total_actions_used":     training_target['total_actions_used'],
            "total_episodes":         training_target['total_episodes'],
            "total_regular_sessions": training_target['total_regular_sessions'],
            "total_super_sessions":   training_target['total_super_sessions'],
            "total_resets":           training_target['total_resets'],
            "finish_reason":          training_target['finish_reason'],
            "started_at":             training_target['started_at'],
            "ended_at":               training_target['ended_at'],
        }
        training_targets.append(training_target_clean)
        target     = training_target['extra']['TARGET']['ip']
        target_str = f"{target} ({training_target['started_at']} <=> {training_target['ended_at']})"
        avg_steps_per_min_map[target_str] = training_target['avg_steps_per_min']

    training_clean = {
        "learner_family": training['learner_family'],
        "trainer_config": training['trainer_config'],
        "training_id":    training['training_id'],
    }

    # steps_per_minute = get_steps_per_minute(training_target_clean['total_steps'], training_target['started_at'], training_target['ended_at'])

    game_data = {}
    for game_type in Constants.GAME_TYPES:
        if game_type not in game_data:
            game_data[game_type] = {}

        if game_type in sessions_map:
            game_data[game_type]['sessions_map'] = sessions_map[game_type]

        if game_type in goals_map:
            game_data[game_type]['action_sources'] = goals_map[game_type]

        if game_type in action_distribution_map:
            game_data[game_type]['times_each_action_ran'] = action_distribution_map[game_type]

        if game_type in state_hash_map:
            game_data[game_type]['state_hash_map'] = state_hash_map[game_type]

        if game_type in steps_per_hour_map:
            game_data[game_type]['steps_per_hour_map'] = steps_per_hour_map[game_type]

    data = {
        "database_name":           db_name,
        "training":                training_clean,
        "training_targets":        training_targets,
        # "sessions_map":            sessions_map,
        # "goals_map":               goals_map,
        # "action_distribution_map": action_distribution_map,
        # "state_hash_map":          state_hash_map,
        # "steps_per_hour_map":      steps_per_hour_map,
        "game_data":               game_data,
        "avg_steps_per_min":       avg_steps_per_min_map,
    }

    data_json = Utils.dump_json_pretty(data, replace_new_line=False, sort_keys=False)
    print(data_json)

def main(args):
    connection = Db(db_host=Constants.DRAGON_STAGING_DB_IP, db_name=args.db_name, db_password=Constants.DRAGON_DB_PWD)

    trainings = connection.query("select * from training")
    for training in trainings:
        review_training(connection, args.db_name, training)

    connection.close()

if __name__ == '__main__':
    # SETTING UP LOGGER
    args = argparser.parse_args()
    main(args)
