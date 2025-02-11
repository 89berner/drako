import lib.Common.Utils.Log as Log

import lib.Common.Recommendation.PredictionRequest as Prediction

from lib.Exploration.Agent.Base import BaseTrainingAgent, BaseTesterAgent

class GoExploreAgent(BaseTrainingAgent):
    def __init__(self, *args):
        super().__init__(*args)
        Log.logger.debug("Finished init for GoExploreAgent")

    def get_next_action_from_agent_specific(self, action_history):
        action_recommendation = Prediction.request_action(self.environment, self.target, self.environment.current_state, action_history, "COUNTER")

        return action_recommendation

class NNRecommendationTesterAgent(BaseTesterAgent):
    def __init__(self, *args):
        super().__init__(*args)
        Log.logger.debug("Finished init for NNRecommendationTesterAgent")

    def get_next_action_from_agent_specific(self, action_history):
        action_recommendation = Prediction.request_action(self.environment, self.target, self.environment.current_state, action_history, "GREEDY")

        return action_recommendation
