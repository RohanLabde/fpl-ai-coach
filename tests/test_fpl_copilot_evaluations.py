"""Regression suite for the supported FPL Copilot question contract.

These checks do not call OpenAI, Supabase, or the live FPL API. They ensure
common natural-language questions continue to map to the correct, safe data plan.
"""

import unittest

from data.fpl_intents import route_fpl_question
from data.fpl_query_planner import normalise_query_plan


class DeterministicQuestionEvaluationTests(unittest.TestCase):
    def test_common_team_questions_have_expected_data_plans(self):
        cases = [
            (
                "Which team has the easiest next 5 fixtures?",
                "team_fixture_horizon",
                "get_team_fixture_horizon",
                {"horizon": 5, "limit": 10},
            ),
            (
                "Give me the top 5 teams for attacking form over the last 3 game weeks",
                "team_strength",
                "get_team_strength_leaderboard",
                {"metric": "attacking", "gameweeks": 3, "limit": 5},
            ),
            (
                "Which teams have the best defensive form over the last 3 gameweeks?",
                "team_strength",
                "get_team_strength_leaderboard",
                {"metric": "defensive", "gameweeks": 3, "limit": 10},
            ),
        ]

        for question, intent, tool_name, expected_arguments in cases:
            with self.subTest(question=question):
                plan = route_fpl_question(question)
                self.assertIsNotNone(plan)
                self.assertEqual(plan["intent"], intent)
                self.assertEqual(plan["tool_name"], tool_name)
                for key, expected in expected_arguments.items():
                    self.assertEqual(plan["arguments"][key], expected)

    def test_position_rankings_use_position_appropriate_metrics(self):
        cases = [
            ("Who are the best FPL defenders this season?", "DEF", "defensive"),
            ("Top 5 midfielders this season", "MID", "attacking"),
            ("Best goalkeepers this season", "GKP", "goalkeeping"),
        ]

        for question, position, metric in cases:
            with self.subTest(question=question):
                plan = route_fpl_question(question)
                self.assertIsNotNone(plan)
                self.assertEqual(plan["intent"], "current_season_leaderboard")
                self.assertEqual(plan["arguments"]["position"], position)
                self.assertEqual(plan["arguments"]["metric"], metric)

    def test_structured_player_plans_preserve_required_fields(self):
        cases = [
            (
                {
                    "intent": "player_profile",
                    "player_names": ["Mohamed Salah"],
                    "position": "NONE",
                    "metric": "NONE",
                    "scope": "player_research",
                    "gameweeks": 5,
                    "limit": 10,
                    "needs_clarification": False,
                    "clarification": "",
                },
                "player_profile",
                ["Mohamed Salah"],
            ),
            (
                {
                    "intent": "player_form",
                    "player_names": ["David Raya"],
                    "position": "NONE",
                    "metric": "NONE",
                    "scope": "player_research",
                    "gameweeks": 3,
                    "limit": 10,
                    "needs_clarification": False,
                    "clarification": "",
                },
                "player_form",
                ["David Raya"],
            ),
            (
                {
                    "intent": "compare_players",
                    "player_names": ["Mohamed Salah", "Cole Palmer"],
                    "position": "NONE",
                    "metric": "NONE",
                    "scope": "player_research",
                    "gameweeks": 5,
                    "limit": 10,
                    "needs_clarification": False,
                    "clarification": "",
                },
                "compare_players",
                ["Mohamed Salah", "Cole Palmer"],
            ),
        ]

        for raw_plan, intent, names in cases:
            with self.subTest(intent=intent):
                plan = normalise_query_plan(raw_plan)
                self.assertEqual(plan["intent"], intent)
                self.assertEqual(plan["player_names"], names)
                self.assertFalse(plan["needs_clarification"])

    def test_ambiguous_comparison_cannot_run(self):
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


if __name__ == "__main__":
    unittest.main()
