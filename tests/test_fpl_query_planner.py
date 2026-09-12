"""Unit checks for FPL Copilot query-plan validation."""

import unittest

from data.fpl_intents import route_fpl_question
from data.fpl_query_planner import normalise_query_plan


class FplQueryPlanTests(unittest.TestCase):
    def test_defender_without_metric_uses_defensive_profile(self):
        plan = normalise_query_plan(
            {
                "intent": "leaderboard",
                "player_names": [],
                "position": "DEF",
                "metric": "NONE",
                "scope": "unknown",
                "gameweeks": 5,
                "limit": 10,
                "needs_clarification": False,
                "clarification": "",
            }
        )

        self.assertEqual(plan["metric"], "defensive")
        self.assertEqual(plan["scope"], "defensive_form")

    def test_explicit_metric_is_preserved(self):
        plan = normalise_query_plan(
            {
                "intent": "leaderboard",
                "player_names": [],
                "position": "DEF",
                "metric": "goals",
                "scope": "performance",
                "gameweeks": 5,
                "limit": 5,
                "needs_clarification": False,
                "clarification": "",
            }
        )

        self.assertEqual(plan["metric"], "goals")
        self.assertEqual(plan["limit"], 5)

    def test_team_fixture_horizon_route_uses_requested_horizon(self):
        plan = route_fpl_question("Which team has the easiest next 5 fixtures?")
        self.assertEqual(plan["intent"], "team_fixture_horizon")
        self.assertEqual(plan["arguments"]["horizon"], 5)

    def test_team_defence_route_uses_defensive_profile(self):
        plan = route_fpl_question("Which teams have the best defensive form?")
        self.assertEqual(plan["intent"], "team_strength")
        self.assertEqual(plan["arguments"]["metric"], "defensive")

    def test_compare_requires_two_explicit_names(self):
        plan = normalise_query_plan(
            {
                "intent": "compare_players",
                "player_names": ["Salah"],
                "position": "NONE",
                "metric": "NONE",
                "scope": "player_research",
                "gameweeks": 5,
                "limit": 10,
                "needs_clarification": False,
                "clarification": "",
            }
        )

        self.assertEqual(plan["intent"], "unsupported")
        self.assertTrue(plan["needs_clarification"])

    def test_bounds_and_duplicate_names_are_normalised(self):
        plan = normalise_query_plan(
            {
                "intent": "player_form",
                "player_names": ["  Raya ", "Raya", "Ignored"],
                "position": "NONE",
                "metric": "NONE",
                "scope": "player_research",
                "gameweeks": 99,
                "limit": 0,
                "needs_clarification": False,
                "clarification": "",
            }
        )

        self.assertEqual(plan["player_names"], ["Raya"])
        self.assertEqual(plan["gameweeks"], 10)
        self.assertEqual(plan["limit"], 1)


if __name__ == "__main__":
    unittest.main()
