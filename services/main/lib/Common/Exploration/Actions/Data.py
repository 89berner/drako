from dataclasses import dataclass

@dataclass
class ActionRecommendation:
    action_source:         str
    action_reason:         str
    action_name:           str
    action_type:           str
    action_options:        dict
    action_options_errors: dict
    action_data:           dict
    action_extra:          dict