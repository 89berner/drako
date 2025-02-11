CREATE VIEW step_reduced AS SELECT transition_id, episode_id, target, prev_state_hash, next_state_hash, prev_game_type, next_game_type, prev_state, next_state, action_name, action_source, action_parameters, session_command, accumulated_reward, processed_observation, time_spent, created_at, error FROM step;

CREATE view proof_steps AS SELECT training_id, episode_id, transition_id, target, prev_state_hash, next_state_hash, prev_game_type, next_game_type, prev_state, next_state, action_name, action_source, action_parameters, session_command, accumulated_reward, processed_observation, time_spent, created_at FROM step WHERE episode_id IN (SELECT distinct episode_id FROM step WHERE reward_reasons LIKE "%proof_contents%") ORDER BY episode_id, transition_id DESC;

CREATE view irregular_steps AS SELECT episode_id, transition_id, target, prev_state_hash, next_state_hash, prev_game_type, next_game_type, prev_state, next_state, action_name, action_source, action_parameters, session_command, accumulated_reward, processed_observation, time_spent, created_at FROM step WHERE (prev_game_type = 'PRIVESC' AND next_game_type = 'NETWORK') ORDER BY episode_id, transition_id DESC;

CREATE view running_agents AS SELECT * FROM agent WHERE running=1;

CREATE view priv_steps AS SELECT * FROM step_reduced WHERE prev_game_type="PRIVESC" ORDER BY transition_id DESC;

CREATE view error_steps AS SELECT * FROM step_reduced WHERE error IS NOT NULL;

CREATE view states_summary AS 
SELECT prev_game_type, prev_state_hash, prev_state, count(*) AS amount 
FROM step 
GROUP BY prev_state_hash
ORDER BY prev_game_type, amount DESC