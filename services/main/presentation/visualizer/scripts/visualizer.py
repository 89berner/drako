from lib.Recommendation.Graph import *

import lib.Common.Utils.Constants as Constants

from lib.Common.Utils.Db import Db
import lib.Common.Utils.Log as Log
import lib.Common.Utils as Utils

import os
import time
import argparse

argparser = argparse.ArgumentParser(description='Use Drako from command line')
argparser.add_argument('--training_id',               dest='training_id',               type=int,                  help='optional training id to use')
argparser.add_argument('--target',                    dest='target',                    type=str,                  help='target to use')
argparser.add_argument('--milestones_to_process',     dest='milestones_to_process',     type=int,   default=1,     help='number of milestones to process (necessary for gifs)')
argparser.add_argument('--max_nodes_network',         dest='max_nodes_network',         type=int,   default=20,    help='number of nodes to draw')
argparser.add_argument('--game_type',                 dest='game_type',                 type=str,   default=None,  help='game type to focus on')
argparser.add_argument('--only_winner',               dest='only_winner',               type=bool,  default=False, help='only graph the winner paths')
argparser.add_argument('--debug',                     dest='debug',                     type=bool,  default=False, help='only graph the winner paths')
argparser.add_argument('--divisor',                   dest='divisor',                   type=float, default=1,     help='divisor for graph, higher the graph is smaller')
argparser.add_argument('--hide_recommendation',       dest='hide_recommendation',       type=int,   default=0,     help='do not add recommendation to the node')
argparser.add_argument('--min_transitions_per_state', dest='min_transitions_per_state', type=int,   default=1000,  help='amount of transitions per state to avoid too many images')

def get_targets_for_training(connection, training_id):
    stmt = """
        SELECT DISTINCT target FROM training_states
        WHERE training_id=%s
        AND target!=%s
    """
    results = connection.query(stmt, (training_id, Constants.GLOBAL_TARGET))

    targets = []
    for result in results:
        targets.append(result['target'])

    return targets

def get_top_transition_ids_for_states(connection, target, training_id, game_type, options):
    ## FIRST LETS GET ALL THE TRANSITIONS IDS WE WANT FOR TRAINING OF THE NETWORK

    if target == "ALL":
        init_stmt    = "SELECT transition_id, count(*) as count FROM training_states WHERE training_id=%s AND game_type=%s GROUP BY transition_id ORDER BY transition_id DESC"
        init_results = connection.query(init_stmt, (training_id, game_type))
    else:
        init_stmt    = "SELECT transition_id, count(*) as count FROM training_states WHERE training_id=%s AND game_type=%s AND target=%s GROUP BY transition_id ORDER BY transition_id DESC"
        init_results = connection.query(init_stmt, (training_id, game_type, target))

    # print([init_stmt, init_results])

    transition_ids_map       = {}
    last_transition_id_added = 99999999999
    for res in init_results:
        transition_id = res['transition_id']
        count         = res['count']

        # Avoid printing too many states that don't change much
        if transition_id > last_transition_id_added - options['min_transitions_per_state']:
            continue

        if count not in transition_ids_map:
            transition_ids_map[count] = transition_id
            last_transition_id_added  = transition_id

        if len(transition_ids_map) == options['milestones_to_process']:
            break

    transition_ids = list(transition_ids_map.values())#[:states_to_process]
    print("[%s] Got the following %s transition_ids" % (game_type, transition_ids))

    return transition_ids

def get_closest_transition_id(connection, training_id, game_type, transition_id):
    # print("Getting the closest transition_id for the one provided %s" % transition_id)
    query_stmt = """
        SELECT max(transition_id) as max_transition_id FROM training_states WHERE training_id=%s AND game_type=%s AND transition_id<%s
    """
    results = connection.query(query_stmt, (training_id, game_type, transition_id))
    # print(query_stmt)
    # print([training_id, game_type, transition_id])
    # print(results)
    if len(results) > 0:
        return results[0]['max_transition_id']
    else:
        return None

def get_amount_of_actions_to_use(connection, training_id):
    # print("Will request the amount of actions to use..")
    main_stmt = """
        SELECT game_type, actions_to_use 
        FROM   training_game
        WHERE  training_id=%s
    """
    results = connection.query(main_stmt, (training_id,))

    amount_of_actions_to_use = {}
    for result in results:
        game_type      = result['game_type']
        actions_to_use = result['actions_to_use']
        amount_of_actions_to_use[game_type] = len(Utils.json_loads(actions_to_use))

    return amount_of_actions_to_use


def get_hashes_counts_and_percentages(connection, training_id, transition_id, target):
    amount_of_actions_to_use_map = get_amount_of_actions_to_use(connection, training_id)

    state_hashes_counts      = {}
    state_hashes_percentages = {}

    # DEPENDING TO WETHER WE TARGET ONE OR ALL BOXES
    if target == "ALL":
        main_stmt="""
           SELECT prev_state_hash, prev_game_type, count(*) as amount
           FROM step
           JOIN episode ON episode.episode_id=step.episode_id
           WHERE step.training_id=%s AND step.transition_id < %s AND episode.trainable=1
           GROUP BY prev_state_hash, prev_game_type
           ORDER BY prev_game_type DESC, amount DESC
       """
        results = connection.query(main_stmt, (training_id, transition_id))
    else:
        main_stmt="""
            SELECT prev_state_hash, prev_game_type, count(*) as amount
            FROM step
            JOIN episode ON episode.episode_id=step.episode_id
            WHERE step.training_id=%s AND step.transition_id < %s AND episode.trainable=1 AND episode.target=%s
            GROUP BY prev_state_hash, prev_game_type
            ORDER BY prev_game_type DESC, amount DESC
        """
        results=connection.query(main_stmt, (training_id, transition_id, target))
    Log.logger.debug("Got %d results from query at get_hashes_counts_and_percentages" % len(results))

    for result in results:
        state_hash = result['prev_state_hash']
        game_type  = result['prev_game_type']
        amount     = result['amount']

        if game_type not in state_hashes_counts:
            state_hashes_counts[game_type]      = {}
            state_hashes_percentages[game_type] = {}

        state_hashes_counts[game_type][state_hash]      = amount
        state_hashes_percentages[game_type][state_hash] = amount / amount_of_actions_to_use_map[game_type]

    return state_hashes_counts, state_hashes_percentages

def get_training_milestones(connection, training_id, target, game_type, options):
    Log.logger.info("First lets download all the state information")

    training_milestones_arr = []
    if game_type == "NETWORK" or game_type == "PRIVESC":
        ## FIRST LETS GET ALL THE TRANSITIONS IDS WE WANT FOR TRAINING OF THE NETWORK
        transition_ids = get_top_transition_ids_for_states(connection, target, training_id, game_type, options)

        for transition_id in transition_ids:
            print("Will query for results of transition_id %s" % transition_id)

            state_hashes_counts, state_hashes_percentages = get_hashes_counts_and_percentages(connection, training_id, transition_id, target)
            training_milestone = TrainingMilestone([], state_hashes_counts, state_hashes_percentages)
            get_results(connection, training_id, transition_id, game_type, target, training_milestone)
            #format_results(training_milestone)

            training_milestones_arr.append(training_milestone)
    elif game_type == "ALL":
        ## FIRST LETS GET ALL THE TRANSITIONS IDS WE WANT FOR TRAINING OF THE NETWORK
        network_transition_ids = get_top_transition_ids_for_states(connection, target, training_id, 'NETWORK', options)
        for network_transition_id in network_transition_ids:
            Log.logger.debug("Processing network id %s" % network_transition_id)
            state_hashes_counts, state_hashes_percentages = get_hashes_counts_and_percentages(connection, training_id, network_transition_id, target)
            Log.logger.debug("Loaded counts and percentages")
            training_milestone = TrainingMilestone([], state_hashes_counts, state_hashes_percentages)
            get_results(connection, training_id, network_transition_id, 'NETWORK', target, training_milestone)
            Log.logger.debug("Loaded training_milestones")

            privesc_transition_id = get_closest_transition_id(connection, training_id, 'PRIVESC', network_transition_id)
            if privesc_transition_id is not None:
                Log.logger.debug("Found %d as the closest transition_id" % privesc_transition_id)
                get_results(connection, training_id, privesc_transition_id, 'PRIVESC', target, training_milestone)
                # all_results.extend(privesc_results)

            training_milestones_arr.append(training_milestone)
    Log.logger.info("Finished getting training milestones")


    return training_milestones_arr

# state_dict, state_json = format_state_hash(node.state, state_hash, node.game_type, target, node.top_dqn, options)
#             state_dict, state_json = format_state_hash(node, training_milestone, target, options)
# def format_state_hash(state_hash_json, state_hash, game_type, target_type, top_dqn, options):

def create_milestone_plot_for_game_type(target, game_type, training_milestone, options, small_nodes):
    print("=" * 50)
    print("Will create a graph for game_type %s and target %s" % (game_type, target))

    if len(training_milestone.states_information):
        state_hash_to_node, state_json_to_hash = create_node_hashes_map(game_type, training_milestone, target, options, small_nodes)

        # print(state_map)

        G, pos, final_edge_labels = create_graph_and_pos(state_hash_to_node, options)
        if G is None:
            return

        G = reduce_amount_of_nodes(G, final_edge_labels, game_type, state_hash_to_node, state_json_to_hash, options) #20

        # NOW WE CHECK IF WE HAVE ALREADY PROCESSED A SIMILAR STATE TO AVOID PRINTING IT AGAIN
        amount_of_nodes = len(G.nodes())
        # if amount_of_nodes in processed_states:
        #     print("No new information in this graph, will skip it!")
        #     return None
        # else:
        #     processed_states[amount_of_nodes] = 1

        print("Creating plot for %d nodes" % amount_of_nodes)

        node_colors, node_sizes = [], []
        all_node_sizes = 0
        for node in G:
            if small_nodes: # We need more text space
                if options['hide_recommendation']:
                    node_size=len(node) * 1400  # 325
                else:
                    node_size=len(node) * 700  # 325
            else:
                node_size = len(node) * 325#325
            if node_size < 40000:
                node_size = 40000
            # print("%s => %s" % (node, node_size))

            if node == "SESSION" or node == Constants.GRAPH_KEY_STATE_SUPER_SESSION:
                node_colors.append('red')
                node_sizes.append(node_size * 2)
            elif node == "START":
                node_colors.append('blue')
                node_sizes.append(node_size * 2)
            else:
                node_dict = Utils.json_loads(node)
                if 'coverage' in node_dict and int(node_dict['coverage']) >= 1:
                    node_colors.append('green')
                else:
                    node_colors.append('pink')
                node_sizes.append(node_size)

            all_node_sizes += node_size

        print(all_node_sizes)
        if all_node_sizes > 1638720:
            all_node_sizes = 9638720
            print("Node sizes reduced to %d" % all_node_sizes)

        divisor = 35000 * options['divisor']

        # class PlotInformation:
        #     all_node_sizes: int
        #     divisor:        int
        #     node_sizes:     list
        #     node_colors:    list
        #     Graph:          typing.Any
        fig_size = all_node_sizes / divisor
        if fig_size > 8000: #10000
            fig_size = 8000

        plot = PlotInformation(fig_size, node_sizes, node_colors, final_edge_labels, G, pos)

        return plot
    else:
        print("No information available to create a graph for target %s and game_type %s" % (target, game_type))

def create_plots(training_milestones_arr, target, game_type, options, small_nodes):
    plots_created = []
    for training_milestone in training_milestones_arr:
        plot = create_milestone_plot_for_game_type(target, game_type, training_milestone, options, small_nodes)
        if plot is not None:
            plots_created.append(plot)

        if len(plots_created) >= options['milestones_to_process']:
            break

    plots_created.reverse()

    return plots_created

def save_milestone_graph(connection, options, target_to_override=None):
    training_id        = options['training_id']
    target             = options['target']
    game_type_to_focus = options['game_type']

    if target_to_override is not None:
        target = target_to_override

    print("=" * 50)
    print("=" * 50)
    print("=" * 50)

    print("Will create a graph for training %d" % training_id)

    for game_type in ["NETWORK", "PRIVESC", "ALL"]:
        if game_type_to_focus is not None and game_type != game_type_to_focus:
            print("Skipping game_type %s" % game_type)
            continue

        training_milestones_arr = get_training_milestones(connection, training_id, target, game_type, options)

        small_plots_created = create_plots(training_milestones_arr, target, game_type, options, small_nodes=True)
        save_plots(small_plots_created, game_type, target, options, plots_are_small=True)

        plots_created = create_plots(training_milestones_arr, target, game_type, options, small_nodes=False)
        save_plots(plots_created, game_type, target, options, plots_are_small=False)

def main(args):
    connection  = Db(db_host=Constants.DRAGON_STAGING_DB_IP, db_name=Constants.get_dragon_staging_db(), db_password=Constants.DRAGON_DB_PWD)
    training_id = args.training_id

    folder_path       = "%s/%s" % (Constants.VISUALIZER_PATH, int(time.time()) - 1602241742)
    os.system("mkdir %s" % folder_path)
    print("Folder %s was created" % folder_path)

    options = {
        "max_nodes_network":              args.max_nodes_network,
        "only_winner":                    args.only_winner,
        "training_id":                    args.training_id,
        "target":                         args.target,
        "divisor":                        args.divisor,
        "game_type":                      args.game_type,
        "debug":                          args.debug,
        "hide_recommendation":            args.hide_recommendation,
        "min_transitions_per_state":      args.min_transitions_per_state,
        'milestones_to_process':          args.milestones_to_process,
        "folder_path":                    folder_path,
        'amount_of_orphan_nodes_to_skip': min(1, int(args.max_nodes_network / 3)),
        'graph_type':                     'directed',
    }

    # print("Cleaning tmp folder..")
    # os.system("rm /tmp/graphs/*")

    if args.target is None:
        save_milestone_graph(connection, options, Constants.GLOBAL_TARGET)
        targets = get_targets_for_training(connection, training_id, options)
        for target in targets:
            print("Selected target %s" % target)
            save_milestone_graph(connection, options)
    else:
        print("Selected target %s" % args.target)
        save_milestone_graph(connection, options)

    connection.close()

if __name__ == '__main__':
    Log.initialize_log("2")
    Log.logger.info("Starting with log level: %s" % "2")

    args        = argparser.parse_args()
    main(args)
