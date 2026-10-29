import tempfile
import unittest
from pathlib import Path

import polars as pl

from showdown_app.analytics import (
    compute_first_ko_by_rating,
    compute_first_ko_by_turn,
    compute_first_ko_summary,
    get_first_ko_matches,
)
from showdown_pipeline.schema import coerce_team_records


class FirstKoAnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.dataset_path = Path(self.temporary_directory.name) / "dataset.parquet"
        records = []
        for match_id, winner, getter, first_turn in [
            ("m1", "Alice", "Alice", 4),
            ("m2", "Dave", "Carol", 14),
        ]:
            players = ("Alice", "Bob") if match_id == "m1" else ("Carol", "Dave")
            for player in players:
                rating = {"Carol": 1400, "Dave": 1800}.get(player, 1600)
                records.append({
                    "schema_version": 2,
                    "match_id": match_id,
                    "format": "gen9ou",
                    "rating": rating,
                    "player": player,
                    "won": player == winner,
                    "turns": 24,
                    "pokemon": ["Great Tusk"],
                    "uploadtime": 1_700_000_000,
                    "first_ko_turn": first_turn,
                    "first_ko_player": getter,
                    "first_ko_victim": "Dragapult",
                    "first_ko_tied": False,
                    "got_first_ko": player == getter,
                    "total_faints": 4,
                })

        for player in ("Eve", "Frank"):
            records.append({
                "schema_version": 2,
                "match_id": "m3",
                "format": "gen9ou",
                "rating": 1600,
                "player": player,
                "won": player == "Eve",
                "turns": 10,
                "pokemon": ["Kingambit"],
                "uploadtime": 1_700_000_000,
                "first_ko_turn": 10,
                "first_ko_player": None,
                "first_ko_victim": None,
                "first_ko_tied": True,
                "got_first_ko": None,
                "total_faints": 2,
            })

        coerce_team_records(pl.DataFrame(records)).write_parquet(self.dataset_path)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_summary_uses_one_first_ko_getter_per_eligible_match(self) -> None:
        summary = compute_first_ko_summary(self.dataset_path, min_rating=1500)

        self.assertEqual(summary["total_matches"], 3)
        self.assertEqual(summary["enriched_matches"], 3)
        self.assertEqual(summary["unambiguous_matches"], 2)
        self.assertEqual(summary["tied_matches"], 1)
        self.assertEqual(summary["first_ko_wins"], 1)
        self.assertAlmostEqual(summary["first_ko_win_rate"], 0.5)
        self.assertLess(summary["first_ko_win_rate_low"], 0.5)
        self.assertGreater(summary["first_ko_win_rate_high"], 0.5)
        self.assertEqual(summary["lift_over_even_pct_points"], 0.0)
        self.assertAlmostEqual(summary["coverage_pct"], 66.67)

    def test_turn_bands_preserve_first_ko_outcomes(self) -> None:
        by_turn = compute_first_ko_by_turn(self.dataset_path, min_rating=1500)

        self.assertEqual(by_turn["turn_band"].to_list(), ["Turns 1–5", "Turns 11–20"])
        self.assertEqual(by_turn["matches"].to_list(), [1, 1])
        self.assertEqual(by_turn["first_ko_win_rate"].to_list(), [1.0, 0.0])

    def test_rating_bands_use_only_the_credited_side(self) -> None:
        by_rating = compute_first_ko_by_rating(self.dataset_path, min_rating=1500)

        self.assertEqual(by_rating["rating_band"].to_list(), ["1600–1799"])
        self.assertEqual(by_rating["matches"].to_list(), [2])
        self.assertEqual(by_rating["first_ko_wins"].to_list(), [1])
        self.assertEqual(by_rating["first_ko_win_rate"].to_list(), [0.5])

    def test_evidence_rows_link_one_record_per_eligible_match(self) -> None:
        evidence = get_first_ko_matches(self.dataset_path, min_rating=1500)

        self.assertEqual(evidence.height, 2)
        self.assertEqual(set(evidence["match_id"].to_list()), {"m1", "m2"})
        self.assertEqual(
            set(evidence["first_ko_player"].to_list()), {"Alice", "Carol"}
        )
        self.assertEqual(set(evidence["first_ko_won"].to_list()), {True, False})


if __name__ == "__main__":
    unittest.main()
