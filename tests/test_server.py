"""Tests for Codenames server game logic."""
import random
import sys
import os
import unittest

# Allow importing server from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server


class TestNewGame(unittest.TestCase):
    def test_structure(self):
        """new_game() returns a valid game state with 25 cards and correct fields."""
        server.WORDS = [f"WORD{i}" for i in range(30)]
        server.game = server.new_game()
        state = server.game

        self.assertIn("cards"
        self.assertEqual(len(state["cards"]), 25)
        self.assertIn(state["turn"], ("red", "blue"))
        self.assertEqual(state["phase"], "hint")
        self.assertFalse(state["game_over"])
        self.assertIsNone(state["winner"])
        self.assertEqual(state["hint"], {"word": "", "count": 0})
        self.assertEqual(state["guesses"], 0)
        self.assertEqual(state["votes"], {})
        self.assertEqual(state["chat"], [])

        for card in state["cards"]:
            self.assertIn("word", card)
            self.assertIn("role", card)
            self.assertIn("revealed", card)
            self.assertIn(card["role"], ("red", "blue", "neutral", "bomb"))
            self.assertFalse(card["revealed"])

    def test_card_counts(self):
        """new_game() has correct count of red, blue, neutral, bomb for each starting turn."""
        random.seed(42)
        server.WORDS = [f"W{i}" for i in range(25)]

        for _ in range(20):
            state = server.new_game()
            roles = [c["role"] for c in state["cards"]]
            self.assertIn(roles.count("red"), (8, 9))
            self.assertIn(roles.count("blue"), (8, 9))
            self.assertEqual(roles.count("neutral"), 7)
            self.assertEqual(roles.count("bomb"), 1)
            self.assertEqual(len(roles), 25)

    def test_all_words_from_pool_no_duplicates(self):
        """Each card has a word from the WORDS pool and no duplicate words on the board."""
        server.WORDS = [f"W{i}" for i in range(25)]
        server.game = server.new_game()
        words_on_board = [c["word"] for c in server.game["cards"]]
        self.assertEqual(len(words_on_board), len(set(words_on_board)))
        for w in words_on_board:
            self.assertIn(w, server.WORDS)


class TestBuildVotes(unittest.TestCase):
    def test_empty(self):
        """build_votes_for_broadcast() returns empty dict when no votes."""
        server.votes_by_index = {}
        result = server.build_votes_for_broadcast()
        self.assertEqual(result, {})

    def test_with_votes(self):
        """build_votes_for_broadcast() maps card index to list of roles."""
        server.roles_by_id = {0: "red_agent", 1: "red_agent"}
        server.votes_by_index = {3: {0, 1}}
        result = server.build_votes_for_broadcast()
        self.assertIn("3", result)
        self.assertEqual(set(result["3"]), {"red_agent"})


class TestBuildTeams(unittest.TestCase):
    def test_empty(self):
        """build_teams_for_broadcast() returns empty teams when no players."""
        server.roles_by_id = {}
        server.names_by_id = {}
        result = server.build_teams_for_broadcast()
        self.assertEqual(result["red"], [])
        self.assertEqual(result["blue"], [])

    def test_with_players(self):
        """build_teams_for_broadcast() splits players by team and marks spymasters."""
        server.roles_by_id = {
            0: "red_spymaster",
            1: "red_agent",
            2: "blue_spymaster",
            3: "blue_agent",
        }
        server.names_by_id = {0: "Alice", 1: "Bob", 2: "Carol", 3: "Dave"}
        result = server.build_teams_for_broadcast()
        self.assertEqual(len(result["red"]), 2)
        self.assertEqual(len(result["blue"]), 2)
        red_names = [p["name"] for p in result["red"]]
        blue_names = [p["name"] for p in result["blue"]]
        self.assertIn("Alice", red_names)
        self.assertIn("Bob", red_names)
        self.assertIn("Carol", blue_names)
        self.assertIn("Dave", blue_names)
        spymasters_red = [p for p in result["red"] if p["is_spymaster"]]
        spymasters_blue = [p for p in result["blue"] if p["is_spymaster"]]
        self.assertEqual(len(spymasters_red), 1)
        self.assertEqual(len(spymasters_blue), 1)
        self.assertEqual(spymasters_red[0]["name"], "Alice")
        self.assertEqual(spymasters_blue[0]["name"], "Carol")


class TestEndTurn(unittest.TestCase):
    def test_switches_turn_and_resets_phase(self):
        """end_turn() flips turn, sets phase to hint, clears votes and hint."""
        server.WORDS = [f"W{i}" for i in range(25)]
        server.game = server.new_game()
        server.game["turn"] = "red"
        server.game["phase"] = "guessing"
        server.game["hint"] = {"word": "TEST", "count": 2}
        server.votes_by_index = {0: {1, 2}}

        server.end_turn()

        self.assertEqual(server.game["turn"], "blue")
        self.assertEqual(server.game["phase"], "hint")
        self.assertEqual(server.game["hint"], {"word": "", "count": 0})
        self.assertEqual(server.votes_by_index, {})


if __name__ == "__main__":
    unittest.main()
