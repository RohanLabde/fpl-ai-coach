"""Unit checks for deterministic player profile and comparison rendering."""

import importlib.util
import unittest

_FORMATTERS_AVAILABLE = (
    importlib.util.find_spec("streamlit") is not None
    and importlib.util.find_spec("pandas") is not None
)
if _FORMATTERS_AVAILABLE:
    from data.fpl_copilot import (
        _fallback_player_comparison_answer,
        _fallback_player_profile_answer,
        _pending_player_profile_followup_plan,
    )


@unittest.skipUnless(
    _FORMATTERS_AVAILABLE, "requires the application's optional runtime packages"
)
class PlayerAnswerFormatTests(unittest.TestCase):
    def test_full_name_follow_up_completes_ambiguous_profile_request(self):
        messages = [
            {
                "role": "user",
                "content": "What is Palmer's price, ownership, availability, and current form?",
            },
            {
                "role": "assistant",
                "content": (
                    "I found several matches for Palmer. "
                    "Please specify the player's full name or team."
                ),
            },
            {"role": "user", "content": "Cole Palmer"},
        ]

        plan = _pending_player_profile_followup_plan("Cole Palmer", messages)

        self.assertIsNotNone(plan)
        self.assertEqual(plan["intent"], "player_profile")
        self.assertEqual(plan["player_names"], ["Cole Palmer"])
        self.assertFalse(plan["needs_clarification"])

    def test_profile_renders_live_fields_and_availability(self):
        answer = _fallback_player_profile_answer(
            {
                "rows": [
                    {
                        "player_name": "Mohamed Salah",
                        "team_name": "Liverpool",
                        "position": "MID",
                        "price": 12.5,
                        "total_points": 45,
                        "form": 7.2,
                        "selected_by_percent": 35.4,
                        "status": "a",
                        "chance_of_playing_next_round": 100,
                        "season_bonus": 6,
                        "season_bonus_per_90": 2.0,
                        "season_bps": 85,
                    }
                ]
            }
        )

        self.assertIn("**Mohamed Salah** — MID, Liverpool", answer)
        self.assertIn("**Season points:** 45", answer)
        self.assertIn("**Availability:** Available", answer)
        self.assertIn("**Bonus:** 6 points (2 per 90); 85 BPS", answer)

    def test_comparison_uses_defensive_not_attacking_profile_for_defenders(self):
        answer = _fallback_player_comparison_answer(
            {
                "rows": [
                    {
                        "player_name": "Defender One",
                        "team_name": "Arsenal",
                        "position": "DEF",
                        "price": 6.0,
                        "status": "a",
                        "season_points": 20,
                        "season_minutes": 270,
                        "season_clean_sheets": 2,
                        "season_bonus": 3,
                        "season_bonus_per_90": 1.0,
                        "season_bps": 60,
                        "season_defensive_contribution_per_90": 5.4,
                    },
                    {
                        "player_name": "Defender Two",
                        "team_name": "Chelsea",
                        "position": "DEF",
                        "price": 5.5,
                        "status": "a",
                        "season_points": 18,
                        "season_minutes": 250,
                        "season_clean_sheets": 1,
                        "season_bonus": 1,
                        "season_bonus_per_90": 0.4,
                        "season_bps": 48,
                        "season_defensive_contribution_per_90": 4.1,
                    },
                ]
            }
        )

        self.assertIn("**Player comparison**", answer)
        self.assertIn("2 clean sheets", answer)
        self.assertIn("defensive contribution per 90", answer)
        self.assertIn("3 bonus points (1 per 90); 60 BPS", answer)
        self.assertNotIn("Attacking output", answer)


if __name__ == "__main__":
    unittest.main()
