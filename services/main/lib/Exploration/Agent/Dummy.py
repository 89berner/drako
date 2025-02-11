from lib.Exploration.Agent.Base import BaseAgent

class DummyAgent(BaseAgent):
    def __init__(self, environment, options):
        if "target" in options:
            self.target = options["target"]
        else:
            raise ValueError("A target must be defined for this agent")

        BaseAgent.__init__(self, environment)

    def get_next_action_from_agent_specific(self, action_history):
        raise NotImplementedError("Not implemented!")

    def get_target(self):
        return self.target, self.target

    def set_target(self, target):
        self.target = target

    # TO AVOID LOOKING UP DB CONFIG FOR THIS
    def should_we_finish_episode(self):
        return False, "DUMMY"
