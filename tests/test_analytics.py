import tempfile
import unittest
from pathlib import Path

import polars as pl

from showdown_app.analytics import compute_meta_summary, compute_pokemon_stats


class AnalyticsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.dataset_path = Path(self.temporary_directory.name) / "dataset.parquet"
        pl.DataFrame([
            {
                "match_id": "m1",
                "format": "gen9ou",
                "rating": 1600,
                "player": "Alice",
                "won": True,
                "turns": 20,
                "pokemon": ["Great Tusk, M", "Kingambit, F", "Alomomola, L99"],
                "uploadtime": 1_700_000_000,
            },
            {
                "match_id": "m1",
                "format": "gen9ou",
                "rating": 1580,
                "player": "Bob",
                "won": False,
                "turns": 20,
                "pokemon": ["Dragapult, M", "Kingambit, M"],
                "uploadtime": 1_700_000_000,
            },
            {
                "match_id": "m2",
                "format": "gen9ou",
                "rating": 1700,
                "player": "Carol",
                "won": True,
                "turns": 30,
                "pokemon": ["Great Tusk, F", "Dragapult, F", "Alomomola"],
                "uploadtime": 1_700_086_400,
            },
            {
                "match_id": "m2",
                "format": "gen9ou",
                "rating": 1680,
                "player": "Dave",
                "won": False,
                "turns": 30,
                "pokemon": ["Kingambit, M", "Gholdengo"],
                "uploadtime": 1_700_086_400,
            },
        ]).write_parquet(self.dataset_path)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_summary_counts_matches_and_team_records_separately(self) -> None:
        summary = compute_meta_summary(self.dataset_path, min_rating=1500)
        self.assertEqual(summary["total_matches"], 2)
        self.assertEqual(summary["team_records"], 4)
        self.assertEqual(summary["unique_players"], 4)
        self.assertEqual(summary["median_turns"], 25)

    def test_pokemon_names_are_normalized_before_aggregation(self) -> None:
        stats = compute_pokemon_stats(self.dataset_path, min_rating=1500)
        great_tusk = stats.filter(pl.col("pokemon") == "Great Tusk")
        self.assertEqual(great_tusk.height, 1)
        self.assertEqual(great_tusk["appearances"][0], 2)
        self.assertAlmostEqual(great_tusk["win_rate"][0], 1.0)
        alomomola = stats.filter(pl.col("pokemon") == "Alomomola")
        self.assertEqual(alomomola.height, 1)
        self.assertEqual(alomomola["appearances"][0], 2)


if __name__ == "__main__":
    unittest.main()
