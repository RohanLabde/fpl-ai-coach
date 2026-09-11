"""Behaviour checks for deterministic FPL question routing."""

import unittest

from data.fpl_intents import route_fpl_question


class FplIntentRouterTests(unittest.TestCase):
    def test_attacking_midfielder_ranking_uses_fpl_defaults(self):
        plan = route_fpl_question(
            "Give me the top 10 best attacking midfielders this season"
        )

        self.assertEqual(plan["intent"], "current_season_leaderboard")
        self.assertEqual(
            plan["arguments"],
            {"metric": "attacking", "position": "MID", "limit": 10},
        )

    def test_current_season_defender_leaderboard_uses_defensive_profile(self):
        plan = route_fpl_question("Who are the best defenders this season?")

        self.assertEqual(
            plan["arguments"],
            {"metric": "defensive", "position": "DEF", "limit": 10},
        )

    def test_current_season_goalkeeper_leaderboard_uses_goalkeeping_profile(self):
        plan = route_fpl_question("Who are the best goalkeepers this season?")

        self.assertEqual(
            plan["arguments"],
            {"metric": "goalkeeping", "position": "GKP", "limit": 10},
        )

    def test_explicit_metric_and_limit_override_position_default(self):
        plan = route_fpl_question(
            "Show the top 5 defenders by goals this season"
        )

        self.assertEqual(
            plan["arguments"],
            {"metric": "goals", "position": "DEF", "limit": 5},
        )

    def test_clean_sheet_question_uses_clean_sheet_metric(self):
        plan = route_fpl_question(
            "Show the top 5 defenders by clean sheets this season"
        )

        self.assertEqual(
            plan["arguments"],
            {"metric": "clean_sheets", "position": "DEF", "limit": 5},
        )

    def test_data_coverage_question_uses_status_tool(self):
        plan = route_fpl_question("Which years of FPL data do you have?")
        self.assertEqual(plan["intent"], "data_status")
        self.assertEqual(plan["arguments"], {})

    def test_open_ended_question_uses_general_grounded_tools(self):
        self.assertIsNone(
            route_fpl_question("Is player rotation likely to affect Arsenal?")
        )


if __name__ == "__main__":
    unittest.main()
