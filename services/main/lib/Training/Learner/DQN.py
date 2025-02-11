import lib.Common.Utils.Log as Log
import lib.Common.Training.DQN as CommonDQN
import lib.Training.Learner.ExperienceBuffer as ExperienceBuffer

from lib.Training.Learner import BaseLearner

import numpy

#########################################
################# <BASE> ################
#########################################

class BaseDQN(BaseLearner):
    def __init__(self, *args):
        # print(*args)
        self.learner_family = "DQN"
        super().__init__(*args)

        # DEFAULTS
        self.loss_arr = []

    def setup_network(self):
        # Set the number of actions to use since the only guarantee is after getting the list
        number_of_actions_space = len(self.actions_to_use)
        Log.logger.debug(f"Overriding loaded actions with {number_of_actions_space} actions to use")

        self.training_network = CommonDQN.DQN(self.observation_shape_size, number_of_actions_space).to(self.device)
        self.target_network   = CommonDQN.DQN(self.observation_shape_size, number_of_actions_space).to(self.device)

    def train_network_from_sample(self):
        batch = self.experience_buffer.sample(self.game_type, self.BATCH_SIZE)
        # Log.logger.debug(f"Collected batch")

        # Extra check around additional logging, we want to enable it also if we picked an action interesting to us
        self.ADDITIONAL_LOGGING = self.LoggerHelper.check_batch_for_additional_logging(self.target, batch, self.ADDITIONAL_LOGGING)

        self.optimizer.zero_grad()  # This function initializes all gradients of all parameters to zero.

        state_action_values, loss_t = self.calculate_loss(batch)

        # Log.logger.debug(loss_t)
        # Log.logger.debug("Will now go backwards!")
        loss_t.backward()
        self.optimizer.step()

        self.loss_arr.append(loss_t.item()) # Append all losses

        # Log.logger.debug("Finished optimizer step!")
        return batch, state_action_values

    def train_network(self, new_experience = None):
        # Log.logger.debug("Will now train: %s" % str(new_experience))
        trained = False
        if len(self.experience_buffer) >= self.REPLAY_START_SIZE or len(self.experience_buffer) == self.BUFFER_SIZE:
            trained = True

            # Log.logger.debug("Checking if we need to sync the networks")
            if self.train_counter % self.SYNC_TARGET_STEPS == 0:
                Log.logger.info("Syncing the networks!")
                self.target_network.load_state_dict(self.training_network.state_dict())

            self.ADDITIONAL_LOGGING = self.train_counter % self.AMOUNT_OF_STEPS_PER_EXTRA_LOGGING == 0

            batch, state_action_values = self.train_network_from_sample()

            self.LoggerHelper.log_train_network_results(batch, state_action_values, self.ADDITIONAL_LOGGING, self.target, new_experience)
        else:
            Log.logger.debug("Buffer size of %d is smaller than the REPLAY_START_SIZE" % len(self.experience_buffer))

        self.ADDITIONAL_LOGGING = False # Reset it

        self.train_counter += 1

        return trained

    def calculate_loss(self, batch):
        # We also want a feature to select if we use or not the target network
        if self.USE_TRAINING_NETWORK_AS_TARGET:
            target_network = self.training_network
        else:
            target_network = self.target_network

        return self.calculate_loss_specific(batch, target_network)

    def calculate_loss_specific(self, batch, target_network):
        raise NotImplementedError("You need to implement a calculate_loss_specific method!")

#########################################
################# </BASE> ###############
#########################################

#########################################
############### <BUFFER> ################
#########################################

class DQNNormalBuffer:
    def calculate_loss_specific(self, batch, target_network):
        state_action_values, rewards_v, expected_state_action_values, actions, loss_t, next_state_values = CommonDQN.calculate_loss(
                    batch, self.training_network, target_network, device=self.device, gamma=self.DQN_GAMMA,
                    additional_logging=self.ADDITIONAL_LOGGING)

        return state_action_values, loss_t

    def init_experience_buffer(self):
        self.experience_buffer = ExperienceBuffer.NormalExperienceBuffer(self.BUFFER_SIZE)

class DQNDoubleNormalBuffer:
    def calculate_loss_specific(self, batch, target_network):
        state_action_values, rewards_v, expected_state_action_values, actions, loss_t, next_state_values = CommonDQN.calculate_loss(
                    batch, self.training_network, target_network, device=self.device, gamma=self.DQN_GAMMA,
                    double=True,
                    additional_logging=self.ADDITIONAL_LOGGING)

        return state_action_values, loss_t

    def init_experience_buffer(self):
        self.experience_buffer = ExperienceBuffer.NormalExperienceBuffer(self.BUFFER_SIZE)

class DQNPrioBuffer:
    def __init__(self, *args):
        self.state_action_done_map = {}
        super().__init__(*args)

    def calculate_loss_specific(self, batch, target_network):
        state_action_values, rewards_v, expected_state_action_values, actions, loss_t, next_state_values, sample_prios = CommonDQN.calculate_loss_for_priority_buffer(
            batch, self.training_network, target_network, device=self.device, gamma=self.DQN_GAMMA, state_action_done_map=self.state_action_done_map,
            additional_logging=self.ADDITIONAL_LOGGING, boost_rewards=self.BOOST_REWARDS, freeze_rewards=self.FREEZE_REWARDS)

        _, _, _, _, _, _, _, batch_indices, _ = batch
        # Log.logger.debug("Updating buffer priorities")
        # They are passed to the buffer.update_priorities function to reprioritize items that we have sampled.
        self.experience_buffer.update_priorities(batch_indices, sample_prios)
        # We call the update_beta method of the buffer to change the beta parameter according to schedule.
        self.experience_buffer.update_beta(self.train_counter)

        # Log.logger.debug([self.train_counter, self.STEPS_PER_PRIORITIES_PRINT, self.train_counter % self.STEPS_PER_PRIORITIES_PRINT])
        if self.train_counter % self.STEPS_PER_PRIORITIES_PRINT == 0:
            self.experience_buffer.print_priorities()

        return state_action_values, loss_t

    def init_experience_buffer(self):
        self.experience_buffer = ExperienceBuffer.PrioritizedExperienceBuffer(self.BUFFER_SIZE, self.AMOUNT_OF_SIMULATED_TRAINING_STEPS)

class DQNDoublePrioBuffer:
    def __init__(self, *args):
        self.state_action_done_map = {}
        super().__init__(*args)

    def calculate_loss_specific(self, batch, target_network):
        state_action_values, rewards_v, expected_state_action_values, actions, loss_t, next_state_values, sample_prios = CommonDQN.calculate_loss_for_priority_buffer(
            batch, self.training_network, target_network, device=self.device, gamma=self.DQN_GAMMA, state_action_done_map=self.state_action_done_map,
            double=True,
            additional_logging=self.ADDITIONAL_LOGGING, boost_rewards=self.BOOST_REWARDS, freeze_rewards=self.FREEZE_REWARDS)

        _, _, _, _, _, _, _, batch_indices, _ = batch
        # Log.logger.debug("Updating buffer priorities")
        # They are passed to the buffer.update_priorities function to reprioritize items that we have sampled.
        self.experience_buffer.update_priorities(batch_indices, sample_prios)
        # We call the update_beta method of the buffer to change the beta parameter according to schedule.
        self.experience_buffer.update_beta(self.train_counter)

        # Log.logger.debug([self.train_counter, self.STEPS_PER_PRIORITIES_PRINT, self.train_counter % self.STEPS_PER_PRIORITIES_PRINT])
        if self.train_counter % self.STEPS_PER_PRIORITIES_PRINT == 0:
            self.experience_buffer.print_priorities()

        return state_action_values, loss_t

    def init_experience_buffer(self):
        self.experience_buffer = ExperienceBuffer.PrioritizedExperienceBuffer(self.BUFFER_SIZE, self.AMOUNT_OF_SIMULATED_TRAINING_STEPS)

#########################################
############### </BUFFER> ###############
#########################################

#########################################
################ <PLANNER> ##############
#########################################

class DQNPlanner:
    def pos_training_hook(self):
        if len(self.loss_arr) > 0:
            mean_loss = numpy.mean(self.loss_arr)
            if numpy.random.random() > 0.9:
                Log.logger.debug(f"(1/10) Mean loss: {mean_loss}")

        for counter in range(self.AMOUNT_OF_SIMULATED_TRAINING_STEPS):
            Log.logger.debug(f"Running simulated step {counter + 1}")
            self.train_network()

# The following DQN is a normal dqn with a non prioritised buffer
class PlannerDQN(DQNNormalBuffer, DQNPlanner, BaseDQN):
    def __init__(self, *args):
        self.learner_name = "PlannerDQN"
        super().__init__(*args)

class PlannerDoubleDQN(DQNDoubleNormalBuffer, DQNPlanner, BaseDQN):
    def __init__(self, *args):
        self.learner_name = "PlannerDoubleDQN"
        super().__init__(*args)

class PlannerPrioDQN(DQNPrioBuffer, DQNPlanner, BaseDQN):
    def __init__(self, *args):
        self.learner_name = "PlannerPrioDQN"
        super().__init__(*args)

class PlannerPrioDoubleDQN(DQNDoublePrioBuffer, DQNPlanner, BaseDQN):
    def __init__(self, *args):
        self.learner_name = "PlannerPrioDoubleDQN"
        super().__init__(*args)

#########################################
############### </PLANNER> ##############
#########################################

#########################################
################# <SIMPLE> ##############
#########################################

# The following DQN is a normal dqn with a non prioritised buffer
class DQN(DQNNormalBuffer, BaseDQN):
    def __init__(self, *args):
        self.learner_name = "DQN"
        super().__init__(*args)

class DoubleDQN(DQNDoubleNormalBuffer, BaseDQN):
    def __init__(self, *args):
        self.learner_name = "DoubleDQN"
        super().__init__(*args)

class PrioDQN(DQNPrioBuffer, BaseDQN):
    def __init__(self, *args):
        self.learner_name = "PrioDQN"
        super().__init__(*args)

class PrioDoubleDQN(DQNDoublePrioBuffer, BaseDQN):
    def __init__(self, *args):
        self.learner_name = "PrioDoubleDQN"
        super().__init__(*args)

#########################################
############## </SIMPLE> ################
#########################################