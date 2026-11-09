"""Unit checks for deterministic player profile and comparison rendering."""

import importlib.util
import unittest
from unittest.mock import patch

_FORMATTERS_AVAILABLE = (
    importlib.util.find_spec("streamlit") is not None
    and importlib.util.find_spec("pandas") is not None
)
if _FORMATTERS_AVAILABLE:
    from data.fpl_copilot import (
        _availability_summary,
        _answer_planned_question,
        _ownership_summary,
        _fallback_leaderboard_answer,
        _fallback_player_comparison_answer,
        _fallback_player_fixture_answer,
        _fallback_player_form_answer,
        _fallback_player_profile_answer,
        _comparison_matches_selected_players,
        _pending_player_followup_plan,
        _resolve_planned_player,
    )


@unittest.skipUnless(
    _FORMATTERS_AVAILABLE, "requires the application's optional runtime packages"
)
class PlayerAnswerFormatTests(unittest.TestCase):
    def test_full_name_follow_up_uses_explicit_pending_state(self):
        context = {
            "pending_player_plan": {
                "intent": "player_form",
                "player_names": ["Raya"],
                "position": None,
                "metric": None,
                "scope": "performance",
                "gameweeks": 3,
                "limit": 10,
                "max_price": None,
                "needs_clarification": False,
                "clarification": "",
            }
        }

        plan, clarification = _pending_player_followup_plan(
            "David Raya from Arsenal", context
        )

        self.assertIsNotNone(plan)
        self.assertEqual(plan["intent"], "player_form")
        self.assertEqual(plan["player_names"], ["David Raya"])
        self.assertEqual(
            clarification, {"team": "Arsenal", "player_index": 0}
        )
        self.assertFalse(plan["needs_clarification"])

    def test_team_qualifier_stays_with_the_ambiguous_comparison_player(self):
        context = {
            "pending_player_plan": {
                "intent": "compare_players",
                "player_names": ["Mbeumo", "Palmer", "Saka"],
                "position": None,
                "metric": None,
                "scope": "player_research",
                "gameweeks": 5,
                "limit": 10,
                "max_price": None,
                "needs_clarification": False,
                "clarification": "",
                "pending_player_index": 1,
            }
        }

        plan, clarification = _pending_player_followup_plan(
            "Palmer from Chelsea", context
        )

        self.assertEqual(plan["player_names"], ["Mbeumo", "Palmer", "Saka"])
        self.assertEqual(
            clarification, {"team": "Chelsea", "player_index": 1}
        )
        self.assertEqual(plan["player_team_hints"], {"1": "Chelsea"})

        follow_up_plan, follow_up_clarification = _pending_player_followup_plan(
            "Calafiori from Arsenal",
            {
                "pending_player_plan": {
                    **plan,
                    "pending_player_index": 2,
                }
            },
        )
        self.assertEqual(
            follow_up_clarification, {"team": "Arsenal", "player_index": 2}
        )
        self.assertEqual(
            follow_up_plan["player_team_hints"],
            {"1": "Chelsea", "2": "Arsenal"},
        )

    def test_typo_suggestion_requires_an_explicit_follow_up(self):
        with patch(
            "data.fpl_copilot._run_tool",
            return_value={
                "rows": [],
                "suggestions": [
                    {"player_name": "Riccardo Calafiori", "team_name": "Arsenal"}
                ],
            },
        ):
            player, _result, message = _resolve_planned_player("Califiori")

        self.assertIsNone(player)
        self.assertIn("Did you mean **Riccardo Calafiori** (Arsenal)?", message)
        self.assertIn("Reply **yes** to use that player", message)

    def test_yes_confirms_the_single_saved_suggestion(self):
        candidate = {
            "player_id": 8,
            "player_name": "Riccardo Calafiori",
            "team_name": "Arsenal",
        }
        plan, clarification = _pending_player_followup_plan(
            "yes",
            {
                "pending_player_plan": {
                    "intent": "compare_players",
                    "player_names": ["Van Hecke", "Califiori"],
                    "position": None,
                    "metric": None,
                    "scope": "recent_form",
                    "gameweeks": 4,
                    "limit": 10,
                    "max_price": None,
                    "needs_clarification": False,
                    "clarification": "",
                    "pending_player_index": 1,
                    "pending_player_candidates": {"1": [candidate]},
                }
            },
        )

        self.assertEqual(plan["player_names"][1], "Riccardo Calafiori")
        self.assertEqual(plan["resolved_players"], {"1": candidate})
        self.assertEqual(clarification, {"team": "Arsenal", "player_index": 1})

    def test_comparison_rejects_a_different_player_for_a_selected_id(self):
        expected = [{"player_id": 8, "player_name": "Riccardo Calafiori"}]
        result = {"rows": [{"player_id": 8, "player_name": "Frank Onyeka"}]}
        self.assertFalse(_comparison_matches_selected_players(expected, result))

    def test_yes_uses_the_saved_candidate_in_a_comparison(self):
        players = {
            "Van Hecke": {"player_id": 1, "player_name": "Van Hecke", "team_name": "Spurs"},
            "White": {"player_id": 2, "player_name": "White", "team_name": "Arsenal"},
            "Gvardiol": {"player_id": 4, "player_name": "Gvardiol", "team_name": "Man City"},
        }
        calafiori = {
            "player_id": 8,
            "player_name": "Riccardo Calafiori",
            "team_name": "Arsenal",
        }

        def run_tool(name, arguments):
            if name == "search_fpl_players":
                return {"rows": [players[arguments["query"]]]}
            self.assertEqual(name, "compare_fpl_players")
            self.assertEqual(arguments["player_ids"], [1, 2, 8, 4])
            return {
                "rows": [
                    players["Van Hecke"],
                    players["White"],
                    calafiori,
                    players["Gvardiol"],
                ]
            }

        state = {
            "pending_player_plan": {
                "intent": "compare_players",
                "player_names": ["Van Hecke", "White", "Califiori", "Gvardiol"],
                "position": None,
                "metric": None,
                "scope": "recent_form",
                "gameweeks": 4,
                "limit": 10,
                "max_price": None,
                "needs_clarification": False,
                "clarification": "",
                "pending_player_index": 2,
                "player_team_hints": {"1": "Arsenal"},
                "pending_player_candidates": {"2": [calafiori]},
            }
        }
        with patch("data.fpl_copilot._run_tool", side_effect=run_tool), patch(
            "data.fpl_copilot._compose_evidence_answer", return_value="comparison"
        ):
            answer, sources = _answer_planned_question(
                None, None, "yes", [{"role": "user", "content": "yes"}], state
            )

        self.assertEqual(answer, "comparison")
        self.assertEqual(sources, ["search_fpl_players", "compare_fpl_players"])

    def test_yes_in_an_older_pending_chat_does_not_replan_or_substitute(self):
        state = {
            "pending_player_plan": {
                "intent": "compare_players",
                "player_names": ["Van Hecke", "White", "Califiori", "Gvardiol"],
                "position": None,
                "metric": None,
                "scope": "recent_form",
                "gameweeks": 4,
                "limit": 10,
                "max_price": None,
                "needs_clarification": False,
                "clarification": "",
                "pending_player_index": 2,
            }
        }
        with patch("data.fpl_copilot.plan_fpl_question") as planner:
            answer, sources = _answer_planned_question(
                None, None, "yes", [{"role": "user", "content": "yes"}], state
            )

        self.assertIn("full name or team", answer)
        self.assertEqual(sources, [])
        planner.assert_not_called()
        self.assertIn("pending_player_plan", state)

    def test_recent_form_shows_official_total_and_scoring_events(self):
        answer = _fallback_player_form_answer(
            {
                "source": "completed-gameweek totals",
                "rows": [
                    {
                        "player_name": "David Raya",
                        "price": 5.5,
                        "gameweek": 4,
                        "total_points": 14,
                        "minutes": 90,
                        "starts": 1,
                        "goals_scored": 0,
                        "assists": 0,
                        "clean_sheets": 1,
                        "saves": 4,
                        "penalties_saved": 0,
                        "goals_conceded": 0,
                        "bonus": 3,
                        "bps": 38,
                        "defensive_contribution": 8,
                        "yellow_cards": 0,
                        "red_cards": 0,
                        "own_goals": 0,
                        "penalties_missed": 0,
                    }
                ],
            }
        )

        self.assertIn("| GW | Pts | Mins | Starts | Goals | Assists |", answer)
        self.assertIn("**Current price:** £5.5m.", answer)
        self.assertIn("| 4 | 14 | 90 | 1 | 0 | 0 | 1 | 4 |", answer)
        self.assertIn("| 3 | 38 | 8 | none recorded |", answer)

    def test_recent_match_form_labels_fixture_and_venue(self):
        answer = _fallback_player_form_answer(
            {
                "window": "matches",
                "rows": [
                    {
                        "player_name": "Bukayo Saka",
                        "gameweek": 5,
                        "opponent_team_name": "Man City",
                        "was_home": True,
                        "total_points": 8,
                        "minutes": 90,
                        "starts": 1,
                    }
                ],
            }
        )

        self.assertIn("| GW | Opponent | Venue | Pts | Mins | Starts |", answer)
        self.assertIn("| 5 | Man City | H | 8 | 90 | 1 |", answer)
        self.assertIn("each fixture is shown separately", answer)

    def test_recent_match_form_does_not_invent_starts(self):
        answer = _fallback_player_form_answer(
            {
                "window": "matches",
                "rows": [
                    {
                        "player_name": "Bukayo Saka",
                        "gameweek": 5,
                        "opponent_team_name": "Man City",
                        "was_home": False,
                        "total_points": 2,
                        "minutes": 80,
                        "starts": None,
                    }
                ],
            }
        )

        self.assertIn("| 5 | Man City | A | 2 | 80 | — |", answer)
        self.assertNotIn("| 5 | Man City | A | 2 | 80 | 0 |", answer)
        self.assertIn("does not supply a start flag", answer)

    def test_upcoming_fixtures_include_current_ownership(self):
        answer = _fallback_player_fixture_answer(
            {
                "rows": [
                    {
                        "player_name": "Bryan Mbeumo",
                        "team_name": "Man Utd",
                        "price": 7.9,
                        "selected_by_percent": 8.1,
                        "gameweek": 10,
                        "opponent_team_name": "Everton",
                        "venue": "home",
                        "fixture_difficulty": 2,
                    }
                ]
            }
        )

        self.assertIn("**Current selected by:** 8.1% — Differential.", answer)
        self.assertIn("**Current price:** £7.9m.", answer)
        self.assertIn("| GW | Opponent | Venue | FDR |", answer)
        self.assertIn("| 10 | Everton | H | 2 |", answer)

    def test_leaderboard_renders_comparable_players_as_a_table(self):
        answer = _fallback_leaderboard_answer(
            {"metric": "points"},
            {
                "metric": "points",
                "ranking_basis": "FPL points leaders",
                "minimum_starts": 6,
                "rows": [
                    {
                        "player_name": "David Raya",
                        "team_name": "Arsenal",
                        "position": "GKP",
                        "price": 5.5,
                        "total_points": 54,
                        "starts": 9,
                        "minutes": 810,
                        "total_clean_sheets": 6,
                        "total_saves": 18,
                        "total_bonus": 6,
                        "selected_by_percent": 47.2,
                        "status": "a",
                        "season_completed_gameweeks": 9,
                    },
                    {
                        "player_name": "James Trafford",
                        "team_name": "Leeds",
                        "position": "GKP",
                        "price": 4.5,
                        "total_points": 44,
                        "starts": 9,
                        "minutes": 810,
                        "total_clean_sheets": 3,
                        "total_saves": 33,
                        "total_bonus": 8,
                        "selected_by_percent": 6.3,
                        "status": "a",
                        "season_completed_gameweeks": 9,
                    },
                ],
            },
        )

        self.assertIn("| Rank | Player | Team | Pos | Price | FPL pts — season |", answer)
        self.assertIn("| 1 | David Raya | Arsenal | GKP | £5.5m | 54 |", answer)
        self.assertIn("| 2 | James Trafford | Leeds | GKP | £4.5m | 44 |", answer)
        self.assertIn("6.3% — Differential", answer)

    def test_defensive_leaderboard_keeps_period_points_for_comparison(self):
        answer = _fallback_leaderboard_answer(
            {"metric": "defensive"},
            {
                "metric": "defensive",
                "gameweeks": 4,
                "rows": [
                    {
                        "player_name": "Defender One",
                        "team_name": "Arsenal",
                        "position": "DEF",
                        "price": 5.5,
                        "total_points": 26,
                        "total_clean_sheets": 3,
                        "defensive_contribution_per_90": 7.4,
                        "starts": 4,
                        "selected_by_percent": 8.1,
                        "status": "a",
                        "season_completed_gameweeks": 4,
                    }
                ],
            },
        )

        self.assertIn("FPL pts — last 4 GWs", answer)
        self.assertIn("| 1 | Defender One | Arsenal | DEF | £5.5m | 26 | 3 |", answer)

    def test_availability_keeps_official_playing_chance(self):
        self.assertEqual(
            _availability_summary(
                {"status": "a", "chance_of_playing_next_round": 75}
            ),
            "Available; 75% chance of playing next round",
        )

    def test_ownership_marks_low_owned_players_as_differentials(self):
        self.assertEqual(_ownership_summary({"selected_by_percent": 8.1}), "8.1% — Differential")
        self.assertEqual(_ownership_summary({"selected_by_percent": 10}), "10%")

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
        self.assertIn("**Current selected by:** 35.4%", answer)
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
        self.assertIn("| Metric | Defender One (DEF, Arsenal) | Defender Two (DEF, Chelsea) |", answer)
        self.assertIn("| Clean sheets | 2 | 1 |", answer)
        self.assertIn("| Defensive contribution per 90 | 5.4 | 4.1 |", answer)
        self.assertIn("| Bonus | 3 | 1 |", answer)
        self.assertNotIn("Attacking output", answer)

    def test_comparison_table_keeps_actual_attacking_output_and_window(self):
        answer = _fallback_player_comparison_answer(
            {
                "recent_gameweeks": 4,
                "rows": [
                    {
                        "player_name": "Mbeumo",
                        "team_name": "Man Utd",
                        "position": "MID",
                        "price": 7.9,
                        "status": "a",
                        "season_points": 19,
                        "season_starts": 4,
                        "season_minutes": 360,
                        "season_goals": 2,
                        "season_assists": 0,
                        "season_bonus": 2,
                        "season_bps": 80,
                        "season_xgi": 1.6,
                        "season_xgi_per_90": 0.4,
                        "selected_by_percent": 8.1,
                    },
                    {
                        "player_name": "Rice",
                        "team_name": "Arsenal",
                        "position": "MID",
                        "price": 7.4,
                        "status": "a",
                        "season_points": 27,
                        "season_starts": 4,
                        "season_minutes": 349,
                        "season_goals": 0,
                        "season_assists": 3,
                        "season_bonus": 7,
                        "season_bps": 112,
                        "season_xgi": 1.6,
                        "season_xgi_per_90": 0.4,
                        "selected_by_percent": 18.2,
                    },
                ],
            }
        )

        self.assertIn("performance totals cover the last 4 finalized gameweeks", answer)
        self.assertIn("| Goals | 2 | 0 |", answer)
        self.assertIn("| Assists | 0 | 3 |", answer)
        self.assertIn("| xGI | 1.6 | 1.6 |", answer)
        self.assertIn("| Current selected by | 8.1% — Differential | 18.2% |", answer)

    def test_comparison_renders_mixed_positions_with_common_and_specific_metrics(self):
        answer = _fallback_player_comparison_answer(
            {
                "rows": [
                    {
                        "player_name": "Goalkeeper One",
                        "team_name": "Arsenal",
                        "position": "GKP",
                        "price": 5.5,
                        "status": "a",
                        "season_points": 30,
                        "season_starts": 5,
                        "season_minutes": 450,
                        "season_clean_sheets": 3,
                        "season_saves_per_90": 2.4,
                        "season_bonus": 4,
                        "season_bonus_per_90": 0.8,
                        "season_bps": 90,
                    },
                    {
                        "player_name": "Defender One",
                        "team_name": "Chelsea",
                        "position": "DEF",
                        "price": 5.0,
                        "status": "a",
                        "season_points": 28,
                        "season_starts": 5,
                        "season_minutes": 430,
                        "season_clean_sheets": 2,
                        "season_defensive_contribution_per_90": 4.6,
                        "season_bonus": 2,
                        "season_bonus_per_90": 0.4,
                        "season_bps": 70,
                    },
                    {
                        "player_name": "Midfielder One",
                        "team_name": "Liverpool",
                        "position": "MID",
                        "price": 8.0,
                        "status": "d",
                        "chance_of_playing_next_round": 75,
                        "news": "Knock being assessed",
                        "season_points": 42,
                        "season_starts": 5,
                        "season_minutes": 420,
                        "season_goals": 3,
                        "season_assists": 2,
                        "season_xgi": 4.5,
                        "season_xgi_per_90": 1.0,
                        "season_bonus": 5,
                        "season_bonus_per_90": 1.1,
                        "season_bps": 100,
                    },
                ]
            }
        )

        self.assertIn("Goalkeeper One (GKP, Arsenal)", answer)
        self.assertIn("| Saves per 90 | 2.4 | — | — |", answer)
        self.assertIn("Defender One (DEF, Chelsea)", answer)
        self.assertIn("| Defensive contribution per 90 | — | 4.6 | — |", answer)
        self.assertIn("Midfielder One (MID, Liverpool)", answer)
        self.assertIn("| Starts | 5 | 5 | 5 |", answer)
        self.assertIn("**Availability notes:** **Midfielder One**: Knock being assessed", answer)


if __name__ == "__main__":
    unittest.main()
