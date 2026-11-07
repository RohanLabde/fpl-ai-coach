"""Regression checks for the layered FPL player lookup."""

import importlib.util
import unittest
from unittest.mock import patch


_DB_AVAILABLE = all(
    importlib.util.find_spec(package) is not None
    for package in ("streamlit", "pandas", "sqlalchemy")
)
if _DB_AVAILABLE:
    import pandas as pd

    from data.db import _normalise_player_name, search_fpl_players


@unittest.skipUnless(_DB_AVAILABLE, "requires the application's optional runtime packages")
class PlayerSearchTests(unittest.TestCase):
    def test_name_normalization_handles_accents_and_common_equivalents(self):
        self.assertEqual(_normalise_player_name("Pascal Groß"), "pascal gross")
        self.assertEqual(_normalise_player_name("Martin Ødegaard"), "martin odegaard")

    def test_current_season_fallback_uses_qualified_columns(self):
        current_row = pd.DataFrame(
            [{"player_id": 99, "player_name": "Pascal Gross", "team_name": "Brighton"}]
        )
        with patch("data.db._read_dataframe", side_effect=[pd.DataFrame(), current_row]) as reader:
            result = search_fpl_players("Gross")

        self.assertEqual(result["rows"][0]["player_name"], "Pascal Gross")
        current_query = reader.call_args_list[1].args[0]
        self.assertIn("stats.season AS latest_current_season", current_query)
        self.assertIn("stats.gameweek AS latest_current_gameweek", current_query)

    def test_historical_search_accepts_an_ascii_spelling_of_an_accented_name(self):
        historical_row = pd.DataFrame(
            [{"player_id": 99, "player_name": "Pascal Groß", "team_name": "Brighton"}]
        )
        with patch(
            "data.db._read_dataframe",
            side_effect=[pd.DataFrame(), pd.DataFrame(), historical_row],
        ) as reader:
            result = search_fpl_players("Gross")

        self.assertEqual(result["rows"][0]["player_name"], "Pascal Groß")
        historical_query = reader.call_args_list[2].args[0]
        self.assertIn("'ß', 'ss'", historical_query)
        self.assertIn("normalized_name_pattern", reader.call_args_list[2].args[1])

    def test_typo_returns_a_suggestion_without_selecting_a_player(self):
        suggestion_candidates = pd.DataFrame(
            [
                {
                    "player_id": 42,
                    "player_name": "Riccardo Calafiori",
                    "team_name": "Arsenal",
                    "position": "DEF",
                    "source_rank": 0,
                },
                {
                    "player_id": 42,
                    "player_name": "Calafiori",
                    "team_name": "Arsenal",
                    "position": "DEF",
                    "source_rank": 1,
                },
            ]
        )
        with patch(
            "data.db._read_dataframe",
            side_effect=[
                pd.DataFrame(),
                pd.DataFrame(),
                pd.DataFrame(),
                suggestion_candidates,
            ],
        ):
            result = search_fpl_players("Califiori")

        self.assertEqual(result["rows"], [])
        self.assertEqual(result["suggestions"], [
            {
                "player_id": 42,
                "player_name": "Riccardo Calafiori",
                "team_name": "Arsenal",
                "position": "DEF",
                "source_rank": 0,
            }
        ])


if __name__ == "__main__":
    unittest.main()
