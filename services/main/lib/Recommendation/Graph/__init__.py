from mimetypes import init
import networkx as nx
import matplotlib.pyplot as plt

import traceback
import copy
from dataclasses import dataclass
import typing
import lib.Common.Utils.Log as Log
import lib.Common.Utils as Utils

import lib.Common.Utils.Constants as Constants

from lib.Common.Exploration.Environment.Session import Session

import PIL
from PIL import Image
PIL.Image.MAX_IMAGE_PIXELS = None #To avoid errors due to possible DOS

# TODO: We need a way that does not depend on hardcoding it
START_STATE_HASH = Constants.INITIAL_STATE['NETWORK']

@dataclass
class PlotInformation:
    fig_size:          int
    node_sizes:        typing.List[int]
    node_colors:       typing.List[str]
    final_edge_labels: typing.List[str]
    Graph:             typing.Any
    Pos:               typing.Any

@dataclass
class StateInformation:
    state_hash:               str
    state:                    str
    top_dqn:                  str
    next_states:              str
    game_type:                str

@dataclass
class TrainingMilestone:
    states_information:       typing.List[StateInformation]
    state_hashes_counts:      str
    state_hashes_percentages: int


def get_results(connection, training_id, transition_id, game_type, target, training_milestone):
    # print("Picked transition_id %d for game %s" % (transition_id, game_type))
    if target == "ALL":
        main_stmt = """
                SELECT state_hash, state, top_dqn, next_states, game_type
                FROM training_states 
                WHERE training_id=%s 
                AND transition_id=%s
                AND game_type=%s
        """
        data = (training_id, transition_id, game_type)
        # Log.logger.debug([main_stmt, data])
        results = connection.query(main_stmt, data)
    else:
        main_stmt = """
                SELECT state_hash, state, top_dqn, next_states, game_type
                FROM training_states 
                WHERE training_id=%s 
                AND transition_id=%s
                AND target=%s
                AND game_type=%s
        """
        data = (training_id, transition_id, target, game_type)
        # Log.logger.debug([main_stmt, data])
        results = connection.query(main_stmt, data)

    states_info_list = []
    for result in results:
        if result['state_hash'] is None:
            print(result)
        state_information = StateInformation(result['state_hash'], result['state'], result['top_dqn'], result['next_states'], result['game_type'])
        states_info_list.append(state_information)

    Log.logger.debug("Got %d states for game %s with target %s" % (len(states_info_list), game_type, target))
    training_milestone.states_information.extend(states_info_list)

# https://stackoverflow.com/questions/27973988/python-how-to-remove-all-empty-fields-in-a-nested-dict/35263074
def clean_empty(d):
    # print(d)
    if not isinstance(d, (dict, list)):
        return d
    if isinstance(d, list):
        return [v for v in (clean_empty(v) for v in d) if v]

    return {k: v for k, v in ((k, clean_empty(v)) for k, v in d.items()) if v}

def format_state_hash(training_milestone, node, target_type, options, small_nodes):
    state_hash_dict = Utils.json_loads(node.state)
    state_hash      = node.state_hash
    game_type       = node.game_type
    top_dqn         = node.top_dqn

    # state_hash_dict['game_type'] = game_type

    # Cleanup ports information when closed
    ports_to_delete   = []
    ports_that_remain = {"tcp": [], "udp": []}

    for target in state_hash_dict['hosts']:
        for protocol in state_hash_dict['hosts'][target]['ports']:
            for port in state_hash_dict['hosts'][target]['ports'][protocol]:
                if 'state' in state_hash_dict['hosts'][target]['ports'][protocol][port]['information']:
                    if state_hash_dict['hosts'][target]['ports'][protocol][port]['information']['state'] == 'closed':
                        ports_to_delete.append([target, protocol, port])
                    else:
                        ports_that_remain[protocol].append(port)

    for target, protocol, port in ports_to_delete:
        del state_hash_dict['hosts'][target]['ports'][protocol][port]

    # IMPORTANT: We are checking the game_type but that is not defined by the node but by the learner, we should just check the dict
    session_summaries = []
    if game_type == "NETWORK":
        if 'sessions' in state_hash_dict:
            for session in state_hash_dict['sessions']:
                session_summaries.append("(%s) user:%s desc:%s" % (session, state_hash_dict['sessions'][session]['username'], state_hash_dict['sessions'][session]['desc']))
            state_hash_dict['sessions'] = len(state_hash_dict['sessions'])
    elif game_type == "PRIVESC":
        for target in state_hash_dict['hosts']:
            del state_hash_dict['hosts'][target]['ports']

            if 'commands_result' in state_hash_dict['hosts'][target]:
                del state_hash_dict['hosts'][target]['commands_result']

        # print(state_hash_dict)
        if 'sessions' in state_hash_dict:
            for session in state_hash_dict['sessions']:
                session_obj = Session(state_hash_dict['sessions'][session])
                if session_obj.is_super_user_session():
                    state_hash_dict['super_session'] = 1

                del state_hash_dict['sessions'][session]['exploit_uuid']
                del state_hash_dict['sessions'][session]['session_host']
                del state_hash_dict['sessions'][session]['session_port']
                del state_hash_dict['sessions'][session]['target_host']
                del state_hash_dict['sessions'][session]['tunnel_local']
                del state_hash_dict['sessions'][session]['tunnel_peer']
                del state_hash_dict['sessions'][session]['uuid']
                del state_hash_dict['sessions'][session]['workspace']
                del state_hash_dict['sessions'][session]['info']
                del state_hash_dict['sessions'][session]['via_exploit']
                session_summaries.append("(%s) user:%s desc:%s" % (session, state_hash_dict['sessions'][session]['username'], state_hash_dict['sessions'][session]['desc']))

    else:
        raise ValueError("Unknown game_type %s" % game_type)

    if not small_nodes:
        if target_type == Constants.GLOBAL_TARGET:
            targets_to_modify = []
            for target in state_hash_dict['hosts']:
                targets_to_modify.append(target)

            for target in targets_to_modify:
                state_hash_dict['hosts']["ANY"] = state_hash_dict['hosts'][target]
                del state_hash_dict['hosts'][target]
            state_hash_dict['target'] = "ANY"

        state_hash_dict = clean_empty(state_hash_dict)

        # We don't add a redundant target info when hosts is present which already shows it
        if 'hosts' in state_hash_dict:
            del state_hash_dict['target']

        if 'jobs' in state_hash_dict:
            del state_hash_dict['jobs']

    else:
        reduced_state_hash_dict = {}
        # print(ports_that_remain)
        if len(ports_that_remain['tcp']) > 0 or len(ports_that_remain['udp']) > 0:
            reduced_state_hash_dict["ports"] = "tcp:[%s] udp:[%s]" % (",".join(ports_that_remain['tcp']), ",".join(ports_that_remain['udp']))

        if len(session_summaries) > 0:
            reduced_state_hash_dict['sessions'] = ",".join(session_summaries)

        if 'super_session' in state_hash_dict:
            reduced_state_hash_dict['super_session'] = state_hash_dict['super_session']

        state_hash_dict = reduced_state_hash_dict

    if options['hide_recommendation']:
        # print("Hiding recommendation!")
        pass
    else:
        top_dqn_dict         = Utils.json_loads(top_dqn)
        top_dqn_action_names = list(top_dqn_dict.keys())
        best_action          = top_dqn_action_names[0]
        state_hash_dict['recommendation'] = best_action

    if training_milestone.state_hashes_counts is not None and game_type in training_milestone.state_hashes_counts and state_hash in training_milestone.state_hashes_counts[game_type]:
        state_hash_dict['actions_tried'] = training_milestone.state_hashes_counts[game_type][state_hash]
        state_hash_dict['coverage']      = training_milestone.state_hashes_percentages[game_type][state_hash]
    else:
        state_hash_dict['actions_tried'] = 0

    # state_json_without_hash = utils.dump_json(state_hash_dict)
    state_hash_dict['state'] = state_hash

    ord_list = ['state', 'game_type', 'ports', 'target', 'hosts', 'sessions', 'actions_tried', 'coverage', 'recommendation', 'super_session']
    sorted_state_hash_dict = {}
    for key in ord_list:
        if key in state_hash_dict:
            sorted_state_hash_dict[key] = state_hash_dict[key]

    state_hash_json = Utils.dump_json_sorted_by_values(sorted_state_hash_dict)


    return sorted_state_hash_dict, state_hash_json #, state_json_without_hash

def create_node_hashes_map(game_type, training_milestone, target, options, small_nodes):
    state_hash_to_node = {}
    state_json_to_hash = {"START": "START", "SESSION": "SESSION", Constants.GRAPH_KEY_STATE_SUPER_SESSION: Constants.GRAPH_KEY_STATE_SUPER_SESSION}

    # Log.logger.debug(training_milestone.states_information)
    # TODO: Move all this preparation of the node to when we load it directly
    for node in training_milestone.states_information:
        state_hash       = node.state_hash
        next_states_info = Utils.json_loads(node.next_states)
        state_dict, state_json = format_state_hash(training_milestone, node, target, options, small_nodes)

        if game_type != "ALL" and node.game_type != game_type:
            print("Skipping node of game_type %s" % node['game_type'])
            continue

        state_hash_to_node[state_hash]={
            "state_json": state_json,
            "game_type": node.game_type,
            "prev_states": {},
            "next_states": next_states_info,
            "state_dict": state_dict,
        }
        state_json_to_hash[state_json] = state_hash

    # Add previous states
    # print(state_hash_to_node)
    for state_hash in state_hash_to_node:
        for next_state in state_hash_to_node[state_hash]['next_states']:
            if state_hash != next_state:
                if state_hash not in state_hash_to_node[next_state]['prev_states']:
                    state_hash_to_node[next_state]['prev_states'][state_hash] = 0
                state_hash_to_node[next_state]['prev_states'][state_hash] += 1

    return state_hash_to_node, state_json_to_hash

def get_files_from_folder(folder_name):
    import glob
    filenames = glob.glob(folder_name)
    return filenames

def get_top_action_information(action_names_map):
    """
    This gets a list of actions and times they were used to get the best one
    """
    top_action = ""
    top_action_amount = 0
    for action_name in action_names_map:
        if action_name != 'total':
            if action_names_map[action_name]['amount'] > top_action_amount:
                top_action        = action_name
                top_action_amount = action_names_map[action_name]['amount']

    return top_action, top_action_amount

def get_all_simple_paths_to_session(G):
    return list(nx.all_simple_paths(G, 'START', 'SESSION'))

def get_all_simple_paths_from_initial_state_to_key_state(G, initial_state, key_state):
    # Log.logger.debug([G, initial_state, key_state])
    # for v in G:
    #     Log.logger.debug(v)
    if not G.has_node(initial_state):
        Log.logger.warning(f"REVIEW_THIS: We don't have the initial state {initial_state}, this should never happen")
        return []

    if not G.has_node(key_state):
        Log.logger.warning(f"We don't have the key state {key_state}, we will return")
        return []

    if nx.has_path(G, initial_state, key_state):
        paths = []
        for path in nx.all_simple_paths(G, initial_state, key_state, cutoff=20):
            # Log.logger.debug(path)
            paths.append(path)
    else:
        Log.logger.debug(f"There is no path between {initial_state} to {key_state}")

    return paths

def get_shortest_paths_to_session(G):
    return list(nx.shortest_path(G, target='SESSION'))

def get_shortest_path_to_session(G, source_json):
    return list(nx.shortest_path(G, source=source_json, target='SESSION'))

def get_shortest_path_to_key_state(G, source_json, key_state):
    return list(nx.shortest_path(G, source=source_json, target=key_state))

def json_path_to_hash_path(path):
    path_list = []
    for state_json in path:
        if state_json not in ['START', 'SESSION', Constants.GRAPH_KEY_STATE_SUPER_SESSION]:
            state_dict = Utils.json_loads(state_json)
            state_hash = state_dict['state']
            path_list.append(state_hash)

    return path_list

def add_nodes_to_imporant_nodes_list(G, start_hash, end_hash, start_json, end_json, state_json_to_hash, important_node_hashes, max_nodes_network):
    all_simple_paths = list(nx.all_simple_paths(G, start_json, end_json))

    if len(all_simple_paths) > 0:
        for path in all_simple_paths:
            if len(important_node_hashes) > max_nodes_network:
                # print("Reached max of %d nodes, will not add more to important nodes list" % max_nodes_network)
                break
            # else:
                # print("Will review path: %s" % path)

            path.reverse() # lets start from the end
            for node_json in path:
                node_hash = state_json_to_hash[node_json]

                # print("Adding node => %s" % node_hash)
                important_node_hashes[node_hash] = 1
    else:
        print("No paths found between %s and %s" % (start_hash, end_hash) )

def reduce_amount_of_nodes(G, final_edge_labels, game_type, state_hash_to_node, state_json_to_hash, options):

    max_nodes_network = options['max_nodes_network']
    only_winner       = options['only_winner']

    print("=" * 50)
    # If we find a session lets just keep paths to it
    important_node_hashes = {}

    print("Starting the recursive addition of nodes")
    if game_type == "NETWORK" or game_type == "ALL":
        add_nodes_to_imporant_nodes_list(G, 'START', 'SESSION', 'START', 'SESSION', state_json_to_hash, important_node_hashes, max_nodes_network)
    elif game_type == "PRIVESC" or game_type == "ALL":
        add_nodes_to_imporant_nodes_list(G, 'SESSION', Constants.GRAPH_KEY_STATE_SUPER_SESSION, 'SESSION', Constants.GRAPH_KEY_STATE_SUPER_SESSION, state_json_to_hash, important_node_hashes, max_nodes_network)

    if options['debug']:
        print(important_node_hashes)
        print("-"*50)

    if not only_winner:
        all_paths_lengths = dict(nx.all_pairs_shortest_path_length(G))
        map_of_paths = {}
        for state_json in all_paths_lengths:
            state_hash = state_json_to_hash[state_json]
            for connected_state_json in all_paths_lengths[state_json]:
                connected_state_hash = state_json_to_hash[connected_state_json]
                length = all_paths_lengths[state_json][connected_state_json]

                if length > 1:
                    # print("%s => %s is %d" % (state_hash, connected_state_hash, length) )

                    # Populate map based on length of paths
                    if state_hash == 'START':
                        if length not in map_of_paths:
                            map_of_paths[length] = []
                        map_of_paths[length].append([state_hash, connected_state_hash])

                    if connected_state_hash in important_node_hashes:
                        pass

        # NOW PATHS WHICH ARE NOT WINNERS
        list_of_path_lengths = sorted(list(map_of_paths.keys()), reverse=True)
        for path_length in list_of_path_lengths:
            paths = map_of_paths[path_length]
            for path in paths:
                start_hash = path[0]
                end_hash   = path[1]

                if start_hash not in ('START', Constants.GRAPH_KEY_STATE_SUPER_SESSION, 'SESSION'):
                    start_json = state_hash_to_node[start_hash]['state_json']
                else:
                    start_json = start_hash

                if end_hash not in ('START', Constants.GRAPH_KEY_STATE_SUPER_SESSION, 'SESSION'):
                    end_json = state_hash_to_node[end_hash]['state_json']
                else:
                    end_json = end_hash


                # print("Trying to add nodes from %s => %s" % (start_hash, end_hash))
                add_nodes_to_imporant_nodes_list(G, start_hash, end_hash, start_json, end_json, state_json_to_hash, important_node_hashes, max_nodes_network)
                # print(important_node_hashes)

    if options['debug']:
        print("=" * 50)
        print("Important nodes now: %s" % ",".join(important_node_hashes.keys()))

    if len(G.nodes()) > max_nodes_network:
        # nodes_to_remove = []
        for node in list(G.nodes()):
            node_hash = state_json_to_hash[node]
            if node_hash not in important_node_hashes and node_hash not in ['SESSION', Constants.GRAPH_KEY_STATE_SUPER_SESSION, 'START'] and state_hash_to_node[node_hash]['game_type'] == "NETWORK":
                G.remove_node(node)

                # DELETE ANY LABELS FROM THE LIST
                for label_data in list(final_edge_labels.keys()):
                    if label_data[0] == node or label_data[1] == node:
                        del final_edge_labels[label_data]

                # node_hash = state_json_to_hash[node]
                if options['debug']:
                    print("Deleted node %s and its edges" % node_hash)

    return G

def create_graph_from_edges(edges, options):
    if options['graph_type'] == "any":
        G = nx.Graph()
    else:
        G = nx.DiGraph()
    G.add_edges_from(edges)

    pos = nx.nx_agraph.graphviz_layout(G, prog="dot")

    return G, pos

def check_for_network_prev_states(node, state_hash_to_node):
    prev_states = node['prev_states']
    for state_hash in prev_states:
        if state_hash_to_node[state_hash]['game_type'] == "NETWORK":
            return True

    return False

def create_graph_and_pos(state_hash_to_node, options):
    """
    :param state_hash_to_node: Map of each state hash to a node with different information on the state
    :param options: Several options to use to decide how to create the graph
    :return:
    """
    # VAR OF SESSION IF WE FIND IT
    # print("Now we create the data structure with AMOUNT_OF_NODES_TO_SKIP_ORPHANS:%d" % options['amount_of_nodes_to_skip'])
    tmp_edges, final_edges             = [], []
    tmp_edge_labels, final_edge_labels = {}, {}
    counter = 0
    for state_hash in state_hash_to_node:
        counter += 1
        options['debug'] and print("%d/%d (%s)" % (counter, len(state_hash_to_node), state_hash) )
        node       = state_hash_to_node[state_hash]
        state_json = node['state_json']

        for next_state_hash in node['next_states']:
            if next_state_hash != '' and state_hash != next_state_hash:  # dont add edges to yourself

                # CHECK TO AVOID ADDING TO MANY ORPHAN NODES
                if state_hash == START_STATE_HASH:  # First state
                    if len(state_hash_to_node) > 20 and len(state_hash_to_node) > options['amount_of_orphan_nodes_to_skip']:
                        if len(state_hash_to_node[next_state_hash]['next_states']) == 1 and list(state_hash_to_node[next_state_hash]['next_states'].keys())[0] == next_state_hash:  # If they only link to themselves
                            # print("Skipping orphan state %s" % next_state_hash)
                            continue

                tmp_edges       = copy.deepcopy(final_edges)
                tmp_edge_labels = copy.deepcopy(final_edge_labels)

                options['debug'] and print("Creating edge between %s and %s" % (state_hash, next_state_hash))
                next_state_json               = state_hash_to_node[next_state_hash]['state_json']
                top_action, top_action_amount = get_top_action_information(node['next_states'][next_state_hash])

                next_state_dict = state_hash_to_node[next_state_hash]['state_dict']

                # Log.logger.debug([node['game_type'], next_state_dict])

                # print(node)
                # print(state_hash_to_node[next_state_hash])
                # print([node['game_type'], state_hash_to_node[next_state_hash]['game_type']])
                if node['game_type'] == "NETWORK" and 'sessions' in next_state_dict:  # 'sessions' in next_state_dict: #state_hash_to_node[next_state_hash]['game_type'] == 'PRIVESC'
                    tmp_edges.append([state_json, 'SESSION'])
                    tmp_edge_labels[tuple([state_json, 'SESSION'])]="%s (%d)" % (top_action, top_action_amount)
                    # print([next_state_json, 'SESSION!'])
                elif node['game_type'] == "PRIVESC" and 'super_session' in next_state_dict:
                    # Log.logger.debug(f"State {state_hash} is connected to a {Constants.GRAPH_KEY_STATE_SUPER_SESSION}")
                    tmp_edges.append([state_json, Constants.GRAPH_KEY_STATE_SUPER_SESSION])
                    tmp_edge_labels[tuple([state_json, Constants.GRAPH_KEY_STATE_SUPER_SESSION])]="%s (%d)" % (
                        top_action, top_action_amount)
                else:
                    tmp_edges.append([state_json, next_state_json])
                    tmp_edge_labels[tuple([state_json, next_state_json])]="%s (%d)" % (
                        top_action, top_action_amount)

                if not options['skip_checks'] and options['graph_type'] != 'any': # When not any lets make sure it works properly when adding an edge
                    try:
                        _, _= create_graph_from_edges(tmp_edges, options)
                        # print("Now setting final_edges to tmp_edges..")
                        final_edges       = tmp_edges
                        final_edge_labels = tmp_edge_labels
                    except:
                        print(traceback.format_exc())
                        print("ERROR WILL SKIP EDGES [%s => %s]" % (state_hash, next_state_hash))  # traceback.format_exc()
                else:
                    final_edges       = tmp_edges
                    final_edge_labels = tmp_edge_labels

        if node['game_type'] == "PRIVESC":
            node_has_network_prev_state=check_for_network_prev_states(node, state_hash_to_node)
            if len(node['prev_states']) == 0 or node_has_network_prev_state:
                tmp_edges.append(['SESSION', state_json])
                # Log.logger.debug(f"State {state_hash} is connected to a SESSION")
            else:
                pass
                # Log.logger.debug(f"State {state_hash} does not start from session since it has {node['prev_states']} previous states")
        elif node['game_type'] == "NETWORK":
            if len(node['prev_states']) == 0:
                tmp_edges.append(['START', state_json])

    options['debug'] and print("Finished looping through all state hashes to node")

    if len(final_edges) == 0:
        print("No nodes to use, lets continue..")
        return None, None, None

    G, pos = create_graph_from_edges(final_edges, options)
    options['debug'] and print("Finished create_graph_from_edges")

    return G, pos, final_edge_labels

def resize_image(options, filename, size):
    from resizeimage import resizeimage

    with open(filename, 'r+b') as f:
        with Image.open(f) as image:
            cover = resizeimage.resize_cover(image, [size, size], validate=False)
            resized_filename = options['folder_path'] + "/resized_" + filename.split(options['folder_path'] + "/")[1]
            cover.save(resized_filename, image.format)

            return resized_filename

#### METHODS FOR CREATING GRAPHS

def create_gif_of_graphs(filenames, gif_filename):
    import imageio

    # gif_filename = "/tmp/graphs/%s_%s.gif" % (game_type, target)
    # print("Will create gif file %s based on %s" % (gif_filename, ",".join(filenames)))
    images = []
    for filename in filenames:
        images.append(imageio.imread(filename))
    imageio.mimsave(gif_filename, images, format='GIF', fps=1)

def create_mp4_of_graphs(filenames, mp4_filename):
    import imageio

    # mp4_filename = "/tmp/graphs/%s_%s.mp4" % (game_type, target)
    # print("Will create mp4 file %s based on %s" % (mp4_filename, ",".join(filenames)))
    images = []
    for filename in filenames:
        images.append(imageio.imread(filename))
    imageio.mimsave(mp4_filename, images, format='MP4', fps=1)

#### !!!! METHODS FOR CREATING GRAPHS !!!!

### If there are problems with creating graphs we can review this link: https://stackoverflow.com/questions/21978487/improving-python-networkx-graph-layout/21990980#21990980
def save_plots(plots_created, game_type, target, options, plots_are_small):
    import imageio

    filenames_created = []
    counter           = 0

    print("Will now process %d plots" % len(plots_created))
    for plot in plots_created:
        plt.figure(1, figsize=(20 + plot.fig_size, 20 + plot.fig_size))  # amount of nodes * 6

        nx.draw(plot.Graph, plot.Pos, edge_color='black', width=10, linewidths=2,
                node_size=plot.node_sizes, node_color=plot.node_colors, alpha=0.5,
                labels={node: node for node in plot.Graph.nodes()})
        nx.draw_networkx_edge_labels(plot.Graph, plot.Pos, edge_labels=plot.final_edge_labels, font_color='red')  # ,pos
        plt.axis('off')

        if plots_are_small:
            filename = "%s/small_%s_%s_%d.png" % (options['folder_path'], game_type, target, counter)
        else:
            filename = "%s/%s_%s_%d.png" % (options['folder_path'], game_type, target, counter)

        print("Will now save file: %s" % filename)
        plt.savefig(filename)
        plt.close()

        counter += 1
        filenames_created.append(filename)
        print("Finished processing %s" % filename)

    print("Will now resize files..")
    resized_filenames = []
    for file in filenames_created:
        print("Resizing %s" % file)
        resized_filenames.append(resize_image(options, file, 3000))

    if plots_are_small:
        gif_filename = "%s/small_%s_%s.gif" % (options['folder_path'], game_type, target)
    else:
        gif_filename = "%s/%s_%s.gif" % (options['folder_path'], game_type, target)
    create_gif_of_graphs(resized_filenames, gif_filename)

    if plots_are_small:
        mp4_filename = "%s/small_%s_%s.mp4" % (options['folder_path'], game_type, target)
    else:
        mp4_filename="%s/%s_%s.mp4" % (options['folder_path'], game_type, target)
    create_mp4_of_graphs(resized_filenames, mp4_filename)