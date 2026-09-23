"""Regression suite for FPL Copilot's canonical query-plan contract.

Each case asserts the validated plan, rather than an English response. This keeps
natural-language routing, defaults, and time-window semantics stable as the
assistant evolves.
"""

import unittest

from data.fpl_query_planner import plan_fpl_question


class QueryPlanContractTests(unittest.TestCase):
    def test_supported_questions_have_stable_plans(self):
        cases = (
            (
                "How has Raya performed in the last three game weeks?",
                {"intent": "player_form", "player_names": ["Raya"], "gameweeks": 3},
            ),
            (
                "What is Palmer's price, ownership, availability, and current form?",
                {"intent": "player_profile", "player_names": ["Palmer"]},
            ),
            (
                "Which team has the easiest next five fixtures?",
                {"intent": "team_fixture_horizon", "gameweeks": 5, "limit": 10},
            ),
            (
                "Give me the top 5 teams for attacking form over the last 3 gameweeks",
                {
                    "intent": "team_strength",
                    "metric": "attacking",
                    "gameweeks": 3,
                    "limit": 5,
                },
            ),
            (
                "Which teams have the best defensive form over the last three game weeks?",
                {"intent": "team_strength", "metric": "defensive", "gameweeks": 3},
            ),
            (
                "Who are the top 5 defenders this season?",
                {
                    "intent": "leaderboard",
                    "position": "DEF",
                    "metric": "defensive",
                    "limit": 5,
                },
            ),
            (
                "Give me the top 5 midfield picks under £8m for the next 3 fixtures",
                {
                    "intent": "fpl_picks",
                    "position": "MID",
                    "gameweeks": 3,
                    "form_gameweeks": 3,
                    "max_price": 8.0,
                    "limit": 5,
                },
            ),
        )

        for question, expected in cases:
            with self.subTest(question=question):
                plan = plan_fpl_question(None, None, question)
                self.assertFalse(plan["needs_clarification"])
                for field, value in expected.items():
                    self.assertEqual(plan[field], value)

    def test_every_plan_exposes_both_time_windows(self):
        plan = plan_fpl_question(
            None,
            None,
            "Give me the top 5 midfield picks under £8m for the next 3 fixtures",
        )

        self.assertEqual(plan["gameweeks"], 3)
        self.assertEqual(plan["form_gameweeks"], 3)


if __name__ == "__main__":
    unittest.main()
