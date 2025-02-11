import numpy
import collections
from itertools import islice
import lib.Common.Utils.Log as Log
import lib.Common.Utils as Utils

# Experience = collections.namedtuple('Experience',
#                                     field_names=['prev_state', 'prev_state_hash', 'action_idx', 'action_name', 'reward',
#                                                  'new_state', 'new_state_hash', 'target', 'prev_state_json', 'new_state_json'])
#

class Experience(collections.namedtuple("Experience", ['prev_game_type', 'prev_state', 'prev_state_hash', 'action_idx', 'action_name', 'reward',
                                                'new_game_type', 'new_state', 'new_state_hash', 'target', 'prev_state_json', 'new_state_json', 'goal_reached'])):
    __slots__ = ()
    def __str__(self):
        return f"Experience(prev_sh={self.prev_state_hash} action={self.action_name} reward={self.reward} new_sh={self.new_state_hash} gr={self.goal_reached})"

class ExperienceBuffer:
    def __init__(self, capacity):
        self.capacity = capacity
        self.trained_actions   = {}
        self.observation_cache = {}

    def __len__(self):
        return len(self.buffer)

    def __str__(self):
        return str(self.buffer)

    def get_observation_from_cache(self, state, state_json, game_type):
        if state_json not in self.observation_cache:
            self.observation_cache[state_json] = state.get_transform_state_to_observation(game_type)
        return self.observation_cache[state_json]

    def save_trained_action(self, training_entry):
        """
            This method should increment the map that specifies how many times per state an action was used for training
        :param training_entry:
        :return:
        """
        # STORE THE TRAINED ACTIONS MAP
        action_name = training_entry.action_name
        prev_state_hash = training_entry.prev_state_hash

        if prev_state_hash not in self.trained_actions:
            self.trained_actions[prev_state_hash] = {}
        if action_name not in self.trained_actions[prev_state_hash]:
            self.trained_actions[prev_state_hash][action_name] = 0
        self.trained_actions[prev_state_hash][action_name] += 1

    def get_trained_action(self, state_hash, action_name):
        if state_hash in self.trained_actions and action_name in self.trained_actions[state_hash]:
            return self.trained_actions[state_hash][action_name]
        else:
            return 0


class PrioritizedExperienceBuffer(ExperienceBuffer):
    def __init__(self, capacity, amount_of_simulated_steps = 0):
        ExperienceBuffer.__init__(self, capacity)

        self.buffer = []
        self.pos    = 0
        self.priorities = numpy.zeros((capacity,), dtype=numpy.float32)

        self.PROB_ALPHA = 0.6  # probability used for prioritisation
        self.BETA_START = 0.4
        self.BETA_FRAMES = 100000 * (amount_of_simulated_steps + 1)
        self.beta = self.BETA_START  # used for ...
        self.MAX_BETA = 0.9 # was 1.0

    # The method update_beta needs to be called periodically to increase beta according to schedule.
    def update_beta(self, idx):
        v = self.BETA_START + idx * (1.0 - self.BETA_START) / self.BETA_FRAMES
        self.beta = min(self.MAX_BETA, v)
        if idx % 100 == 0:
            Log.logger.debug(f"Now beta is {self.beta}")
        return self.beta

    def append(self, experience):
        if self.buffer:
            max_prio = self.priorities.max()
        else:
            max_prio = 1.0

        # When our buffer hasn't reached the maximum capacity, we just need to append a new transition to the buffer.
        if len(self.buffer) < self.capacity:
            self.buffer.append(experience)
        else:
            # If the buffer is already full, we need to overwrite the oldest transition, which is tracked by the pos class field,
            self.buffer[self.pos] = experience
        self.priorities[self.pos] = max_prio

        # and adjust this position modulo buffer's size.
        self.pos = (self.pos + 1) % self.capacity

    # In the sample() method, we create a list of random indices and
    # then repack the sampled entries into NumPy arrays for more convenient loss calculation.
    def sample(self, game_type, batch_size):
        states, prev_state_hashes, new_state_hashes, actions, rewards, dones, next_states = ([] for i in range(7))

        if len(self.buffer) == self.capacity:
            prios = self.priorities
        else:
            prios = self.priorities[:self.pos]

        # In the sample method, we need to convert priorities to probabilities using our hyperparameter.
        probs = prios ** self.PROB_ALPHA
        probs /= probs.sum()

        # Then, using those probabilities, we sample our buffer to obtain a batch of samples.
        indices = numpy.random.choice(len(self.buffer), batch_size, p=probs)

        Log.logger.debug("Using indices %s for (%s,%s) => (%d,%s)" % (indices, self.buffer[indices[0]].prev_state_hash, self.buffer[indices[0]].action_name,  self.buffer[indices[0]].reward, self.buffer[indices[0]].new_state_hash))

        for idx in indices:
            state_observation = self.get_observation_from_cache(self.buffer[idx].prev_state, self.buffer[idx].prev_state_json, game_type)
            states.append(state_observation)

            next_state_observation = self.get_observation_from_cache(self.buffer[idx].new_state, self.buffer[idx].new_state_json, game_type)
            next_states.append(next_state_observation)

            reward          = self.buffer[idx].reward
            prev_state_hash = self.buffer[idx].prev_state_hash
            new_state_hash  = self.buffer[idx].new_state_hash

            actions.append(self.buffer[idx].action_idx)
            rewards.append(reward)
            dones.append(self.buffer[idx].goal_reached)
            prev_state_hashes.append(prev_state_hash)
            new_state_hashes.append(new_state_hash)

            self.save_trained_action(self.buffer[idx])

            # Log.logger.debug(f"Adding to batch action:{action_name} reward:{reward} prev_state_hash:{prev_state_hash} new_state_hash:{new_state_hash}")

        # WEIGHTS USED FOR PRIORITISED
        weights = (len(self.buffer) * probs[indices]) ** (-self.beta)
        weights /= weights.max() #THIS MAKES IT 1, ITS ONLY USEFUL WHEN YOU HAVE SEVERAL INSTANCES
        # Log.logger.debug(f"Returning weights: {weights}")

        return states, prev_state_hashes, new_state_hashes, numpy.array(actions), numpy.array(rewards, dtype=numpy.float32), numpy.array(dones,dtype=numpy.uint8), numpy.array(next_states), indices, numpy.array(weights, dtype=numpy.float32)

    # The last function of the priority replay buffer allows us to update new priorities for the processed batch.
    # It's the responsibility of the caller to use this function with the calculated losses for the batch.
    def update_priorities(self, batch_indices, batch_priorities):
        for idx, prio in zip(batch_indices, batch_priorities):
            self.priorities[idx] = prio

    def take(self, n, iterable):
        """Return first n items of the iterable as a list"""
        return list(islice(iterable, n))

    def print_priorities(self):
        priorities_list = []
        for pos in range(0, len(self.buffer)):
            priorities_list.append({
                "prev_state":  self.buffer[pos].prev_state_hash,
                "action_name": self.buffer[pos].action_name,
                "priority":    float(self.priorities[pos]),
                "reward":      float(self.buffer[pos].reward)
            })
        sorted_priorities_list = sorted(priorities_list, key=lambda k: k['priority'], reverse=True)

        priorities_sorted_array = []
        for action_data in sorted_priorities_list:
            action_name = action_data['action_name']
            priority    = action_data['priority']
            reward      = action_data['reward']
            prev_state  = action_data['prev_state']
            priorities_sorted_array.append(f"({prev_state},{action_name},{reward}) => {priority}")

        Log.logger.debug("Priorities list:")
        Log.logger.debug("\n".join(priorities_sorted_array))

        # Now lets print only particular priorities
        for prio in priorities_sorted_array:
            for important_action in ["auxiliary/scanner/portscan/ack", "auxiliary/scanner/portscan/syn", "exploit/multi/samba/usermap_script"]:
                if important_action in prio:
                    Log.logger.debug(prio)

# Most of the experience replay buffer code is quite straightforward:
# it basically exploits the capability of the deque class to maintain the given number of entries in the buffer.
class NormalExperienceBuffer(ExperienceBuffer):
    def __init__(self, capacity):
        ExperienceBuffer.__init__(self, capacity)

        self.buffer = collections.deque(maxlen=capacity)
        self.trained_actions = {}

    def append(self, experience):
        self.buffer.append(experience)
        # Log.logger.debug("Appending %s" % experience.action_name)

    # In the sample() method, we create a list of random indices and
    # then repack the sampled entries into NumPy arrays for more convenient loss calculation.
    def sample(self, game_type, batch_size):  # observation_cache
        states, prev_state_hashes, new_state_hashes, actions, rewards, dones, next_states = ([] for i in range(7))

        if batch_size > len(self.buffer):
            batch_size = len(self.buffer)
            Log.logger.warn("The batch size requested cannot be larger than the buffer size! The batch size is now the buffer size")

        # if batch_size > 1:  # we just get the latest one, no need for randomness => Removed for now
        indices = numpy.random.choice(len(self.buffer), batch_size, replace=False)
        # else:
        #     indices = [len(self.buffer) - 1]

        for idx in indices:
            state_observation = self.get_observation_from_cache(self.buffer[idx].prev_state, self.buffer[idx].prev_state_json, game_type)
            states.append(state_observation)

            next_state_observation = self.get_observation_from_cache(self.buffer[idx].new_state, self.buffer[idx].new_state_json, game_type)
            next_states.append(next_state_observation)

            reward          = self.buffer[idx].reward
            new_state_hash  = self.buffer[idx].new_state_hash
            prev_state_hash = self.buffer[idx].prev_state_hash

            actions.append(self.buffer[idx].action_idx)
            rewards.append(reward)
            dones.append(self.buffer[idx].goal_reached)

            prev_state_hashes.append(prev_state_hash)
            new_state_hashes.append(new_state_hash)

            self.save_trained_action(self.buffer[idx])

            # Log.logger.debug(f"Adding to batch action:{action_name} reward:{reward} prev_sh:{prev_state_hash} new_sh:{new_state_hash}")

        batch = states, prev_state_hashes, new_state_hashes, numpy.array(actions), numpy.array(rewards, dtype=numpy.float32), numpy.array(dones,dtype=numpy.uint8), next_states, indices, None

        return batch
