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

    from data.db import search_fpl_players


@unittest.skipUnless(_DB_AVAILABLE, "requires the application's optional runtime packages")
class PlayerSearchTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
