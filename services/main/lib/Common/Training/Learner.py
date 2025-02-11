import lib.Common.Utils as Utils
import lib.Common.Utils.Log as Log

def load_learner_options(connection, learner_family, learner_name, game_type=None, attributes=None):
    config = {}

    if game_type is None:
        query_stmt = "SELECT attribute,value,attribute_type FROM training_config WHERE game_type=\"SHARED\" "
    elif game_type == "ALL":
        query_stmt = "SELECT attribute,value,attribute_type FROM training_config WHERE 1=1 "
    else:
        query_stmt = "SELECT attribute,value,attribute_type FROM training_config WHERE (game_type=\"%s\" OR game_type=\"SHARED\") " % game_type
    query_stmt += "AND learner_family=%s AND (learner_name=\"*\" OR learner_name=%s)"

    if attributes is not None:
        query_stmt += " AND attribute IN ('%s')" % "','".join(attributes)
    Log.logger.debug(query_stmt, learner_family, learner_name)

    results = connection.query(query_stmt, (learner_family, learner_name))
    for result in results:
        attribute = result["attribute"]
        config[attribute] = result["value"]
        if result['attribute_type'] == "INT":
            config[attribute] = int(config[attribute])
        elif result['attribute_type'] == "FLOAT":
            config[attribute] = float(config[attribute])
        elif result['attribute_type'] == "BOOL":
            if config[attribute] == "TRUE":
                config[attribute] = True
            else:
                config[attribute] = False

    # Log.logger.debug(config)
    return config

def load_benchmark_config_options(connection, game_type, learner_family=None, learner_name=None):
    query_stmt = "SELECT attribute,value FROM training_config WHERE game_type=%s AND benchmark_attribute=1"
    if learner_family is not None:
        query_stmt += " AND learner_family=\"%s\"" % learner_family
    if learner_name is not None:
        query_stmt += " AND (learner_name=\"*\" OR learner_name=\"%s\")" % learner_name

    results    = connection.query(query_stmt, (game_type, ))

    config_options = {}
    for res in results:
        config_options[res['attribute']] = res['value']

    return config_options


def load_actions_to_use(connection, training_game_id):
    query = "SELECT actions_to_use FROM training_game WHERE training_game_id = %s"
    #Log.logger.debug(stmt)
    results = connection.query(query, (training_game_id,))
    #Log.logger.debug(results)

    if len(results) > 0 and results[0]['actions_to_use'] is not None:
        return Utils.json_loads(results[0]['actions_to_use'])
    else:
        return None

def log_or_print_warn(text):
    if Log.logger is not None:
        Log.logger.warning(text)
    else:
        print(text)

def get_main_training_ids(connection):
    stmt = "SELECT game_type, training_game_id, training_id FROM training_game WHERE main_training=1"
    results = connection.query(stmt)
    main_training_ids = {}
    for result in results:
        game_type = result['game_type']
        if game_type in main_training_ids:
            [log_or_print_warn(f"We had more than one main training for {game_type} this should not happen!") for i in range(5)]
        else:
            main_training_ids[game_type] = {
                'training_game_id': result['training_game_id'],
                'training_id':      result['training_id']
            }

    return main_training_ids

def get_current_training_training_game_ids(connection, training_id):
    stmt = "SELECT game_type, training_game_id, training_id FROM training_game WHERE training_id=%s"
    results = connection.query(stmt, (training_id,))
    current_training_ids = {}
    for result in results:
        game_type = result['game_type']
        if game_type in current_training_ids:
            [Log.logger.warning(f"We had more than one main training for {game_type} this should not happen!") for i in range(5)]
        else:
            current_training_ids[game_type] = {
                'training_game_id': result['training_game_id'],
                'training_id':      result['training_id']
            }

    return current_training_ids

def get_training_state_max_transition_id(connection, training_game_id, target):
    stmt = "SELECT max(transition_id) as max_transition_id FROM training_states WHERE training_game_id=%s AND target=%s"
    results = connection.query(stmt, (training_game_id, target))

    if len(results) > 0 and results[0]['max_transition_id'] is not None:
        return results[0]['max_transition_id']
    else:
        return None

def get_training_states(connection, training_game_id, target, transition_id):
    stmt = "SELECT * FROM training_states WHERE training_game_id=%s AND target=%s AND transition_id=%s"
    results = connection.query(stmt, (training_game_id, target, transition_id))

    return results

# def upload_actions_to_use(connection, training_id, game_type, actions_to_use):
#     update_stmt = "UPDATE training_game SET actions_to_use = %s WHERE training_id = %s AND game_type = %s"
#     data        = (utils.dump_json(actions_to_use), training_id, game_type)
#     Log.logger.debug(update_stmt)
#     connection.execute(update_stmt, data)
#
#     return True
