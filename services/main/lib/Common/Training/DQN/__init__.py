import operator
import torch.nn as nn
import torch
import json

from collections import OrderedDict

import numpy
import lib.Common.Exploration.Actions    as Actions
import lib.Common.Utils.Log as Log

import lib.Common.Utils as Utils

# NETWORK
class DQN(nn.Module):
    def __init__(self, obs_size, n_actions, hidden_size=5000):
        # hidden_size = int(obs_size * 1.5)#
        hidden_size = int(obs_size / 3) * 2 + n_actions

        hidden_sizes = [hidden_size, hidden_size]

        super(DQN, self).__init__()
        self.net = nn.Sequential(
            nn.Linear(obs_size, hidden_sizes[0]),
            nn.ReLU(), #Sigmoid
            nn.Linear(hidden_sizes[0], hidden_sizes[1]),
            nn.ReLU(), #Sigmoid
            nn.Linear(hidden_sizes[1], n_actions)
        )

    def forward(self, x):
        return self.net(x.float())


# Note: written for parallel processing with gpus
# In arguments, we pass our batch as a tuple of arrays (repacked by the sample() method in the experience buffer), 
# our network that we are training, and the target network, which is periodically synced with the trained one.
def calculate_loss(batch, training_network, target_network, device, gamma, double=False, additional_logging=False):
    # Log.logger.debug("Will now calculate loss for normal buffer")
    states, _, _, actions, rewards, dones, next_states, batch_indices, batch_weights = batch

    # The preceding code is simple and straightforward: we wrap individual NumPy arrays with batch data
    # in PyTorch tensors and copy them to GPU if the CUDA device was specified in arguments.

    # states_v      = torch.tensor(numpy.array(states, copy=False)).to(device)
    # next_states_v = torch.tensor(numpy.array(next_states, copy=False)).to(device)
    same_operation = False
    # if same_operation:

    states_v      = torch.tensor(states,      device=device, dtype=torch.uint8)  #).to(device)
    actions_v     = torch.tensor(actions,     device=device, dtype=torch.int64) #).to(device)
    rewards_v     = torch.tensor(rewards,     device=device, dtype=torch.int16) #).to(device)
    # Log.logger.debug("Created tensors and moved them to device")

    # Below we pass observations to the first model and extract the specific Q-values 
    # for the taken actions using the gather() tensor operation. The first argument to the gather() call 
    # is a dimension index that we want to perform gathering on (in our case, 
    # it is equal to 1, which corresponds to actions).
    # The second argument is a tensor of indices of elements to be chosen.
    # Extra unsqueeze() and squeeze() calls are required to compute the index argument for the gather functions, 
    # and to get rid of the extra dimensions that we created, respectively.
    state_action_values = training_network(states_v).gather(1, actions_v.unsqueeze(-1)).squeeze(-1)
    # Log.logger.debug("Got state_action_values")

    # CALCULATE THEM IN THE NN
    next_state_values = calculate_next_states_values(training_network, target_network, next_states, dones, device, double)

    # =======> STEP 6
    # we calculate the Bellman approximation value.
    # Y = R + max Q(s,a)
    expected_state_action_values = rewards_v + (next_state_values * gamma)
    # and the mean squared error loss
    # LOSS = (Q(s,a) - Y)^2
    # =======> STEP 7

    if additional_logging:
        Log.logger.debug(f"expected_state_action_values:{expected_state_action_values} = {rewards_v} + ({next_state_values} * {gamma})")
        Log.logger.debug(f"Will get the loss between {state_action_values} AND {expected_state_action_values}")

    loss = nn.MSELoss()(state_action_values, expected_state_action_values)
    # loss = F.smooth_l1_loss(state_action_values, expected_state_action_values.unsqueeze(1))


    # Log.logger.debug("Calculated loss with F: %s" % loss)

    return state_action_values, rewards_v, expected_state_action_values, actions, loss, next_state_values

def calculate_next_states_values(training_network, target_network, next_states, dones, device, double):
    done_mask = torch.BoolTensor(dones).to(device)

    with torch.no_grad():
        next_states_v = torch.tensor(numpy.array(next_states, copy=False)).to(device)

        # Now we apply the target network to our next state observations and calculate the maximum Q-value
        # along the same action dimension, 1. Function max() returns both maximum values and indices of those values
        # (so it calculates both max and argmax), which is very convenient.
        # However, in this case, we are interested only in values, so we take the first entry of the result.
        if double:
            next_state_acts   = training_network(next_states_v).max(1)[1]
            next_state_acts   = next_state_acts.unsqueeze(-1)
            # We get the value of the target network for the action we would have picked with our training network for the next action
            next_state_values = target_network(next_states_v).gather(1, next_state_acts).squeeze(-1)
        else:
            next_state_values = target_network(next_states_v).max(1)[0]

        # Here we make one simple, but very important, point: if transition in the batch is from the last step in the episode,
        # then our value of the action doesn't have a discounted reward of the next state, as there is no next state from which to gather the reward.
        # This may look minor, but it is very important in practice: without this, training will not converge.
        next_state_values[done_mask] = 0.0
        # MAKES Y = R

        # In this line, we detach the value from its computation graph to prevent gradients from flowing into the NN used
        # to calculate Q approximation for the next states.
        return next_state_values.detach()

# Note: written for parallel processing with gpus
# In arguments, we pass our batch as a tuple of arrays (repacked by the sample() method in the experience buffer), 
# our network that we are training, and the target network, which is periodically synced with the trained one.
def calculate_loss_for_priority_buffer(batch, training_network, target_network, device, gamma, state_action_done_map, double=False, additional_logging=False, boost_rewards=False, freeze_rewards=False):
    # Log.logger.debug("Will now calculate loss")
    states, prev_state_hashes, _, actions, rewards, dones, next_states, batch_indices, batch_weights = batch

    # The preceding code is simple and straightforward: we wrap individual NumPy arrays with batch data
    # in PyTorch tensors and copy them to GPU if the CUDA device was specified in arguments.
    states_v      = torch.tensor(numpy.array(states,      copy=False)).to(device)

    actions_v       = torch.tensor(actions).to(device)
    rewards_v       = torch.tensor(rewards).to(device)
    batch_weights_v = torch.tensor(batch_weights).to(device)

    # Below we pass observations to the first model and extract the specific Q-values 
    # for the taken actions using the gather() tensor operation. The first argument to the gather() call 
    # is a dimension index that we want to perform gathering on (in our case, 
    # it is equal to 1, which corresponds to actions).
    # The second argument is a tensor of indices of elements to be chosen. 
    # Extra unsqueeze() and squeeze() calls are required to compute the index argument for the gather functions, 
    # and to get rid of the extra dimensions that we created, respectively.
    state_action_values = training_network(states_v).gather(1, actions_v.unsqueeze(-1)).squeeze(-1)

    # CALCULATE THEM IN THE NN
    next_state_values = calculate_next_states_values(training_network, target_network, next_states, dones, device, double)

    expected_state_action_values = rewards_v + (next_state_values * gamma)

    l = (state_action_values - expected_state_action_values) ** 2

    if additional_logging:
        Log.logger.debug(f"expected_state_action_values:{expected_state_action_values} = {rewards_v} + ({next_state_values} * {gamma})")
        Log.logger.debug(f"loss:{l} = (state_action_values:{state_action_values} - {expected_state_action_values}) ** 2")

    # Log.logger.debug(l)
    # Log.logger.debug(batch_weights_v)
    losses_v = batch_weights_v * l
    # Log.logger.debug(losses_v)

    # A small value is added to every loss to handle the situation of zero loss value, which will lead to zero priority for an entry in the replay buffer.
    sample_prios = (losses_v + 1e-5).data.cpu().numpy()
    # Log.logger.debug(sample_prios)

    # TODO: TEC-478
    # Add to priorities based on whether there is a reward or not
    if boost_rewards:
        Log.logger.debug(sample_prios)
        for idx, (sample_prio, done) in enumerate(zip(sample_prios, dones)):
            Log.logger.debug([sample_prio, done])
            if done:
                sample_prios[idx] = sample_prio*2 #squared means it only trains on it
                Log.logger.debug(f"Sample_prio went from {sample_prio} to {sample_prios[idx]}")
        Log.logger.debug(sample_prios)

    # TODO: THIS MEANS WE TRAIN ONLY ONCE WITH A NEW EXPERIENCE THAT HAS A 0 REWARD FOR A PREVIOUSLY REWARDING STATE
    # TODO: IMPROVING CHANCES FOR BETTER REWARDING STATES BUT NOT GETTING INTO A COMPETITION BETWEEN REWARDING AND NON REWARDING STATES
    # TODO: IF NOT WE NEED TO MOVE THIS TO THE REPLAY BUFFER SAMPLE METHOD
    if freeze_rewards:
        AMOUNT_TO_FREEZE_STATE = 20 #TODO: MOVE TO CONSTANT
        Log.logger.debug(sample_prios)
        for idx, (prev_state_hash, action, done, sample_prio) in enumerate(zip(prev_state_hashes, actions, dones, sample_prios)):
            state_action_tuple = (prev_state_hash, action)
            if done:
                if state_action_tuple not in state_action_done_map:
                    state_action_done_map[state_action_tuple] = 0
                state_action_done_map[state_action_tuple] += 1
            else:
                if state_action_tuple in state_action_done_map and state_action_done_map[state_action_tuple] > AMOUNT_TO_FREEZE_STATE:
                    sample_prios[idx] = 0
                    Log.logger.debug(f"Sample_prio went from {sample_prio} to {sample_prios[idx]} since its freezed")
                    Log.logger.debug(f"state_action_done_map: {state_action_done_map}")
        Log.logger.debug(sample_prios)

    # loss = nn.MSELoss()(state_action_values, expected_state_action_values)

    return state_action_values, rewards_v, expected_state_action_values, actions, losses_v.mean(), next_state_values, sample_prios


def create_q_vals_values_dict(q_vals_values, all_actions):
    # Log.logger.debug([q_vals_values, all_actions])
    # Log.logger.debug([len(q_vals_values[0]), len(all_actions)])

    q_vals_values_dict = {}
    idx = 0
    # Log.logger.debug(q_vals_values)
    try:
        for q_value in q_vals_values.tolist():
            q_vals_values_dict[all_actions[idx]] = q_value
            idx += 1
    except:
        raise ValueError("Error trying to go through qvalues: %s of len %d with all_actions %s of len %d" % (q_vals_values, len(q_vals_values), all_actions, len(all_actions)))

    return q_vals_values_dict

def create_q_vals_values_list(q_vals_values):
    q_vals_values_list = []
    for q_value in q_vals_values.tolist():
        q_vals_values_list.append(q_value)

    return q_vals_values_list


def log_q_vals_and_get_top_actions(all_actions, q_vals_values, amount_of_actions):  # state_observation,
    # Log.logger.debug([all_actions, q_vals_values])

    q_vals_values_dict  = create_q_vals_values_dict(q_vals_values, all_actions)
    top_qvalues         = list(OrderedDict(sorted(q_vals_values_dict.items(), key=operator.itemgetter(1), reverse=True)))
    top_limited_qvalues = OrderedDict(sorted(q_vals_values_dict.items(), key=operator.itemgetter(1), reverse=True)[:amount_of_actions])

    top_limited_qvalues_sorted = Utils.dump_json_sorted_by_values(top_limited_qvalues)
    # state_hash            = utils.get_hash_of_list(state_observation)
    # Log.logger.debug("FOR STATE %s => %s" % (state_hash, top_limited_qvalues_sorted))

    return top_qvalues, top_limited_qvalues, top_limited_qvalues_sorted


# db_nmap; set dst_ip 10.10.10.3; set mode top_100; set DELAY_TO_OBSERVE 1; run;
# auxiliary/fuzzers/ssh/ssh_kexinit_corrupt; set RHOSTS 10.10.10.3; set DELAY_TO_OBSERVE 1; run;

def get_q_vals_values_from_network(observation, network, device):
    # prepare the observation
    state_array = observation #numpy.array([observation], copy=False)
    state_values = torch.tensor(state_array, device=device)
    # get all q values for observation
    q_vals_values = network(state_values)

    return q_vals_values


def softmax(x, temperature=0.5):
    x = numpy.array(x)
    np_exp = numpy.exp(x / temperature)
    sum_np_exp = sum(numpy.exp(x / temperature))

    return list(np_exp / sum_np_exp)


def ratio(x):
    x = x / sum(x)

    return x


def normalize(x):
    x = numpy.array(x)
    normalized = (x - min(x)) / (max(x) - min(x))

    return list(normalized)


def pick_action_name_from_nn_softmax(actions_to_use, q_vals_values):
    normalized_q_values = normalize(q_vals_values)

    softmax_q_values       = softmax(normalized_q_values)
    softmax_q_values_dict  = dict(zip(actions_to_use, softmax_q_values))
    softmax_all_qvalues    = dict(sorted(softmax_q_values_dict.items(), key=operator.itemgetter(1), reverse=True))
    softmax_top_20_qvalues = dict(sorted(softmax_q_values_dict.items(), key=operator.itemgetter(1), reverse=True)[:20])
    picked_action_name_softmax     = numpy.random.choice(actions_to_use, p=softmax_q_values)
    picked_action_name_softmax_idx = tuple(softmax_all_qvalues.keys()).index(picked_action_name_softmax)

    ratio_q_values        = ratio(normalized_q_values)
    ratio_q_values_dict   = dict(zip(actions_to_use, ratio_q_values))
    ratio_all_qvalues     = dict(sorted(ratio_q_values_dict.items(), key=operator.itemgetter(1), reverse=True))
    ratio_top_20_qvalues  = dict(sorted(ratio_q_values_dict.items(), key=operator.itemgetter(1), reverse=True)[:20])
    picked_action_name_ratio     = numpy.random.choice(actions_to_use, p=ratio_q_values)
    picked_action_name_ratio_idx = tuple(ratio_all_qvalues.keys()).index(picked_action_name_ratio)

    return picked_action_name_softmax, picked_action_name_softmax_idx, softmax_top_20_qvalues, picked_action_name_ratio, picked_action_name_ratio_idx, ratio_top_20_qvalues

def pick_action_name_from_nn_sequencial(actions_to_use, observation, training_network, device, action_history):
    q_vals_values                 = get_q_vals_values_from_network(observation, training_network, device)
    top_q_vals, _, top_20_qvalues = log_q_vals_and_get_top_actions(actions_to_use, q_vals_values, amount_of_actions=20)

    action_name_picked = "EXCEPTION"

    # Log.logger.debug(action_history)

    unique_actions_used = {}
    for action in action_history:
        # Log.logger.debug(action)
        unique_actions_used[action['action_name_picked']] = 1
    if len(actions_to_use) == len(unique_actions_used):
        action_history.clear()
        Log.logger.debug("Cleaning actions history buffer since we reach the max")

    counter = 0
    while counter < len(top_q_vals):
        action_source = "DQN_%d" % counter
        action_name_picked = top_q_vals[counter]

        # Here we check if it makes sense to pick exactly the same action
        # For now we only check if the action name was already looked at
        # In the future we need to check for parameters to some sane limit
        # action_names_from_history = [item[1] for item in action_history]
        if action_name_picked not in unique_actions_used:
            break
        else:
            pass
            # Log.logger.warn("Had to pick up a different action name since %s was already used in our history" % action_name_picked)

        counter += 1

    q_vals_values_list = create_q_vals_values_list(q_vals_values)
    picked_action_name_softmax, picked_action_name_softmax_idx, softmax_top_20_qvalues, picked_action_name_ratio, picked_action_name_ratio_idx, ratio_top_20_qvalues = pick_action_name_from_nn_softmax(actions_to_use, q_vals_values_list)
    action_extra = {
        "top_20_q_vals": top_20_qvalues,
        # "softmax": {
        #     "picked_action_name_softmax":     picked_action_name_softmax,
        #     "picked_action_name_softmax_idx": picked_action_name_softmax_idx,
        #     "softmax_top_20_qvalues":         softmax_top_20_qvalues,
        # },
        # "ratio": {
        #     "picked_action_name_ratio":     picked_action_name_ratio,
        #     "picked_action_name_ratio_idx": picked_action_name_ratio_idx,
        #     "ratio_top_20_qvalues":         ratio_top_20_qvalues,
        # }
    }

    return action_source, action_name_picked, action_extra

def get_random_actions(game_type, seed, number_of_actions_space):
    blacklisted_actions = [
        "post/multi/general/close",
        "auxiliary/fuzzers/dns/dns_fuzzer",
        "auxiliary/fuzzers/ftp/ftp_pre_post",
        "auxiliary/fuzzers/http/http_form_field",
        "auxiliary/fuzzers/http/http_get_uri_long",
        "auxiliary/fuzzers/http/http_get_uri_strings",
        "auxiliary/fuzzers/ntp/ntp_protocol_fuzzer",
        "auxiliary/fuzzers/smb/smb2_negotiate_corrupt",
        "auxiliary/fuzzers/smb/smb_create_pipe",
        "auxiliary/fuzzers/smb/smb_create_pipe_corrupt",
        "auxiliary/fuzzers/smb/smb_negotiate_corrupt",
        "auxiliary/fuzzers/smb/smb_ntlm1_login_corrupt",
        "auxiliary/fuzzers/smb/smb_tree_connect",
        "auxiliary/fuzzers/smb/smb_tree_connect_corrupt",
        "auxiliary/fuzzers/smtp/smtp_fuzzer",
        "auxiliary/fuzzers/ssh/ssh_kexinit_corrupt",
        "auxiliary/fuzzers/ssh/ssh_version_15",
        "auxiliary/fuzzers/ssh/ssh_version_2",
        "auxiliary/fuzzers/ssh/ssh_version_corrupt",
        "auxiliary/fuzzers/tds/tds_login_corrupt",
        "auxiliary/fuzzers/tds/tds_login_username",
        "auxiliary/scanner/portscan/xmas", # leads to wrong port scans that detect closed ports as open
    ]

    actions_to_use = []

    # amount_of_actions_to_get =  self.number_of_actions_space
    amount_of_actions_to_get = number_of_actions_space - len(actions_to_use)
    random_actions           = Actions.client.get_seeded_random_actions(game_type, seed, amount_of_actions_to_get)
    for action in sorted(random_actions):
        if action not in actions_to_use and action not in blacklisted_actions: # Don't add a prioritised action
            actions_to_use.append(action)

    return actions_to_use