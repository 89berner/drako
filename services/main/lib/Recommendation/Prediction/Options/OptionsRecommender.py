from numpy.random import choice
import lib.Common.Utils.Log as Log
import lib.Common.Utils as Utils

class OptionsRecommender:
    def __init__(self, connection, training_game_id, game_type):
        self.connection       = connection
        self.training_game_id = training_game_id
        self.game_type        = game_type

        self.best_options_map = self.load_best_options_map()

    def load_best_options_map(self):
        # 1) Lets get for every state in the training every action and the list of options used that led to a reward higher than 0
        stmt = """
            SELECT target, prev_state_hash, action_name, action_parameters, accumulated_reward 
            FROM step FORCE INDEX (accumulated_reward)
            JOIN training_game tg ON tg.training_id=step.training_id
            WHERE tg.training_game_id=%s AND accumulated_reward>0
            GROUP BY prev_state_hash, action_name, action_parameters
        """

        best_options_map = {}
        results = self.connection.query(stmt, (self.training_game_id,))
        for res in results:
            target            = res['target']
            state_hash        = res['prev_state_hash']
            action_name       = res['action_name']
            action_parameters = res['action_parameters']

            if target not in best_options_map:
                best_options_map[target] = {}
            if state_hash not in best_options_map[target]:
                best_options_map[target][state_hash] = {}
            if action_name not in best_options_map[target][state_hash]:
                best_options_map[target][state_hash][action_name] = []
            best_options_map[target][state_hash][action_name].append(action_parameters)

        return best_options_map

    def get_recommended_options(self, target, state_hash, action_name):
        # Log.logger.debug(self.best_options_map[target]][state_hash])
        # Log.logger.debug([target, state_hash, action_name])
        Log.logger.info("Getting recommended options for target:%s state_hash:%s action_name:%s" % (target, state_hash, action_name))
        if target in self.best_options_map and state_hash in self.best_options_map[target]:
            if action_name in self.best_options_map[target][state_hash]:
                action_options = choice(self.best_options_map[target][state_hash][action_name])
                # Log.logger.debug(action_options)
                return Utils.json_loads(action_options)

        return {}