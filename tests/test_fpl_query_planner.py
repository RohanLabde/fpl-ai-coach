"""Unit checks for FPL Copilot query-plan validation."""

import unittest

from data.fpl_intents import route_fpl_question
from data.fpl_query_planner import (
    normalise_question_text,
    normalise_query_plan,
    plan_fpl_question,
)


class FplQueryPlanTests(unittest.TestCase):
    def test_question_normalization_preserves_player_name_and_normalizes_window(self):
        plan = plan_fpl_question(
            None,
            None,
            "How has Raya performed in the last three game weeks?",
        )

        self.assertEqual(plan["intent"], "player_form")
        self.assertEqual(plan["player_names"], ["Raya"])
        self.assertEqual(plan["gameweeks"], 3)
        self.assertEqual(
            normalise_question_text("Last three game weeks"),
            "Last 3 gameweeks",
        )

    def test_common_deterministic_routes_share_the_query_plan_contract(self):
        cases = [
            ("Which team has the easiest next five fixtures?", "team_fixture_horizon"),
            ("Top 5 defenders this season", "leaderboard"),
            (
                "Give me the top 5 midfield picks under £8m for the next 3 fixtures",
                "fpl_picks",
            ),
        ]
        for question, intent in cases:
            with self.subTest(question=question):
                plan = plan_fpl_question(None, None, question)
                self.assertEqual(plan["intent"], intent)
                self.assertFalse(plan["needs_clarification"])

    def test_explicit_player_form_question_bypasses_model_planner(self):
        questions = (
            "How has Raya performed over the last 3 gameweeks?",
            "How has Raya performed in the last 3 game weeks?",
        )
        for question in questions:
            with self.subTest(question=question):
                plan = plan_fpl_question(None, None, question)

                self.assertEqual(plan["intent"], "player_form")
                self.assertEqual(plan["player_names"], ["Raya"])
                self.assertEqual(plan["gameweeks"], 3)
                self.assertFalse(plan["needs_clarification"])

    def test_match_window_is_not_treated_as_a_gameweek_window(self):
        plan = plan_fpl_question(
            None,
            None,
            "How has Saka performed in the last 5 matches?",
        )

        self.assertEqual(plan["intent"], "player_form")
        self.assertEqual(plan["player_names"], ["Saka"])
        self.assertEqual(plan["gameweeks"], 5)
        self.assertEqual(plan["form_window"], "matches")

    def test_possessive_profile_question_bypasses_model_planner(self):
        plan = plan_fpl_question(
            None,
            None,
            "What is Palmer's price, ownership, availability, and current form?",
        )

        self.assertEqual(plan["intent"], "player_profile")
        self.assertEqual(plan["player_names"], ["Palmer"])
        self.assertFalse(plan["needs_clarification"])

    def test_position_without_metric_uses_fpl_points(self):
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

        self.assertEqual(plan["metric"], "points")
        self.assertEqual(plan["scope"], "fpl_points")

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

    def test_spaced_gameweek_window_is_preserved_for_team_form(self):
        plan = route_fpl_question(
            "Which teams have the best defensive form over the last 3 game weeks?"
        )
        self.assertEqual(plan["intent"], "team_strength")
        self.assertEqual(plan["arguments"]["metric"], "defensive")
        self.assertEqual(plan["arguments"]["gameweeks"], 3)

    def test_team_attack_ranking_preserves_limit_and_window(self):
        plan = route_fpl_question(
            "Give me the top 5 teams for attacking form over the last 3 gameweeks"
        )
        self.assertEqual(plan["intent"], "team_strength")
        self.assertEqual(plan["arguments"]["metric"], "attacking")
        self.assertEqual(plan["arguments"]["limit"], 5)
        self.assertEqual(plan["arguments"]["gameweeks"], 3)

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
