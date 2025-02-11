from lib.Training.Learner.DQN import DQN, DoubleDQN, PrioDQN, PrioDoubleDQN, PlannerDQN, PlannerDoubleDQN, PlannerPrioDQN, PlannerPrioDoubleDQN

def build_learner(game_type, learner_name, training_id, load_main_training, profile, continue_from_latest_point, params_to_override=None, benchmark_id=None, force_cpu=False, staging_connection = None):
    if learner_name == "DQN":
        return DQN(game_type, training_id, load_main_training, profile, continue_from_latest_point, params_to_override, benchmark_id, force_cpu, staging_connection)
    elif learner_name == "DoubleDQN":
        return DoubleDQN(game_type, training_id, load_main_training, profile, continue_from_latest_point, params_to_override, benchmark_id, force_cpu, staging_connection)
    elif learner_name == "PrioDQN":
        return PrioDQN(game_type, training_id, load_main_training, profile,continue_from_latest_point, params_to_override, benchmark_id, force_cpu, staging_connection)
    elif learner_name == "PrioDoubleDQN":
        return PrioDoubleDQN(game_type, training_id, load_main_training, profile,continue_from_latest_point, params_to_override, benchmark_id, force_cpu, staging_connection)
    elif learner_name == "PlannerDQN":
        return PlannerDQN(game_type, training_id, load_main_training, profile,continue_from_latest_point, params_to_override, benchmark_id, force_cpu, staging_connection)
    elif learner_name == "PlannerDoubleDQN":
        return PlannerDoubleDQN(game_type, training_id, load_main_training, profile,continue_from_latest_point, params_to_override, benchmark_id, force_cpu, staging_connection)
    elif learner_name == "PlannerPrioDQN":
        return PlannerPrioDQN(game_type, training_id, load_main_training, profile,continue_from_latest_point, params_to_override, benchmark_id, force_cpu, staging_connection)
    elif learner_name == "PlannerPrioDoubleDQN":
        return PlannerPrioDoubleDQN(game_type, training_id, load_main_training, profile,continue_from_latest_point, params_to_override, benchmark_id, force_cpu, staging_connection)
    else:
        raise ValueError(f"I don't know how to create the learner {learner_name}")