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
    )


@unittest.skipUnless(
    _FORMATTERS_AVAILABLE, "requires the application's optional runtime packages"
)
class PlayerAnswerFormatTests(unittest.TestCase):
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
                    }
                ]
            }
        )

        self.assertIn("**Mohamed Salah** — MID, Liverpool", answer)
        self.assertIn("**Season points:** 45", answer)
        self.assertIn("**Availability:** Available", answer)

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
                        "season_defensive_contribution_per_90": 4.1,
                    },
                ]
            }
        )

        self.assertIn("**Player comparison**", answer)
        self.assertIn("2 clean sheets", answer)
        self.assertIn("defensive contribution per 90", answer)
        self.assertNotIn("Attacking output", answer)


if __name__ == "__main__":
    unittest.main()
