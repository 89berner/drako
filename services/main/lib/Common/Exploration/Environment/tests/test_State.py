from unittest import TestCase

import lib.Common.Exploration.Environment.State as State

class TestState(TestCase):
    def test_create_state(self):
        state = State()
        self.assertIsInstance(state, State, "Should be a State instance")

    def test_deduce_game_type(self):
        state = State()
        game_type = state.deduce_game_type()
        self.assertEqual(game_type, "NETWORK")