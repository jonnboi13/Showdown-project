import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import polars as pl

from showdown_pipeline import ingestion
from showdown_pipeline.parser import parse_replay_payload


class IngestionTests(unittest.TestCase):
    def test_enrichment_replaces_batch_and_records_progress(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_root = Path(temporary_directory) / "data"
            batch_directory = data_root / "raw_batches" / "gen9ou"
            manifest_directory = data_root / "manifests"
            batch_directory.mkdir(parents=True)
            manifest_directory.mkdir(parents=True)
            file_name = "gen9ou_batch_old.parquet"
            batch_path = batch_directory / file_name
            pl.DataFrame({
                "match_id": ["gen9ou-test", "gen9ou-test"],
                "format": ["gen9ou", "gen9ou"],
                "rating": pl.Series([1600, 1600], dtype=pl.Int32),
                "player": ["Alice", "Bob"],
                "won": [True, False],
                "turns": [8, 8],
                "pokemon": [["Pikachu"], ["Raichu"]],
                "uploadtime": [1, 1],
            }).write_parquet(batch_path)
            manifest_path = manifest_directory / "gen9ou_manifest.json"
            manifest_path.write_text(json.dumps({
                "total_matches": 1,
                "oldest_timestamp": 1,
                "file_mappings": {"gen9ou-test": file_name},
            }))
            payload = {
                "format": "gen9ou",
                "rating": 1600,
                "uploadtime": 1,
                "log": "\n".join([
                    "|player|p1|Alice|",
                    "|player|p2|Bob|",
                    "|turn|3",
                    "|faint|p2a: Raichu",
                    "|turn|8",
                    "|win|Alice",
                ]),
            }

            def fake_fetch(match_id: str, session: object) -> pl.DataFrame:
                return parse_replay_payload(match_id, payload)

            with (
                patch.object(ingestion, "DATA_ROOT", data_root),
                patch.object(ingestion, "fetch_and_parse_replay", fake_fetch),
            ):
                completed = ingestion.enrich_existing_batches(
                    "gen9ou",
                    max_batches=1,
                    request_delay=0,
                )

            result = pl.read_parquet(batch_path)
            manifest = json.loads(manifest_path.read_text())
            self.assertEqual(completed, 1)
            self.assertEqual(result["schema_version"].to_list(), [2, 2])
            self.assertEqual(result["got_first_ko"].to_list(), [True, False])
            self.assertEqual(manifest["batch_schema_versions"][file_name], 2)


if __name__ == "__main__":
    unittest.main()
