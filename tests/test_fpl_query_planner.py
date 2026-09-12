"""Unit checks for FPL Copilot query-plan validation."""

import unittest

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
