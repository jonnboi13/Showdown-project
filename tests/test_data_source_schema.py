import tempfile
import unittest
from pathlib import Path

import polars as pl

from showdown_app.data_source import _consolidate_parquet
from showdown_pipeline.schema import coerce_team_records


class DataSourceSchemaTests(unittest.TestCase):
    def test_consolidates_legacy_and_enriched_batches(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            legacy = pl.DataFrame({
                "match_id": ["old", "old"],
                "format": ["gen9ou", "gen9ou"],
                "rating": pl.Series([1500, 1500], dtype=pl.Int32),
                "player": ["A", "B"],
                "won": [True, False],
                "turns": pl.Series([10, 10], dtype=pl.Int32),
                "pokemon": [["Pikachu"], ["Raichu"]],
                "uploadtime": pl.Series([1, 1], dtype=pl.Int32),
            })
            enriched = coerce_team_records(pl.DataFrame({
                "schema_version": [2, 2],
                "match_id": ["new", "new"],
                "format": ["gen9ou", "gen9ou"],
                "rating": [1600, 1600],
                "player": ["C", "D"],
                "won": [True, False],
                "turns": [12, 12],
                "pokemon": [["Pikachu"], ["Raichu"]],
                "uploadtime": [2, 2],
                "first_ko_turn": [3, 3],
                "first_ko_player": ["C", "C"],
                "first_ko_victim": ["Raichu", "Raichu"],
                "first_ko_tied": [False, False],
                "got_first_ko": [True, False],
                "total_faints": [2, 2],
            }))
            legacy.write_parquet(root / "legacy.parquet")
            enriched.write_parquet(root / "enriched.parquet")
            destination = root / "consolidated.parquet"

            records, matches = _consolidate_parquet(root, destination)
            result = pl.read_parquet(destination).sort("match_id")

            self.assertEqual(records, 4)
            self.assertEqual(matches, 2)
            self.assertEqual(result["schema_version"].to_list(), [2, 2, 1, 1])
            self.assertEqual(result.schema["turns"], pl.Int64)
            self.assertEqual(result.schema["uploadtime"], pl.Int64)
            legacy_rows = result.filter(pl.col("match_id") == "old")
            self.assertEqual(legacy_rows["got_first_ko"].to_list(), [None, None])


if __name__ == "__main__":
    unittest.main()
