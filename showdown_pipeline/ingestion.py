"""Incremental ingestion and resumable schema enrichment for replay batches."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import polars as pl
import requests

from showdown_app.config import TIERS
from showdown_pipeline.parser import fetch_and_parse_replay
from showdown_pipeline.schema import RECORD_SCHEMA_VERSION, coerce_team_records


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = PROJECT_ROOT / "data"


def manifest_path(tier: str) -> Path:
    directory = DATA_ROOT / "manifests"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{tier}_manifest.json"


def load_manifest(tier: str) -> dict:
    path = manifest_path(tier)
    if path.exists():
        with path.open("r", encoding="utf-8") as source:
            manifest = json.load(source)
    else:
        manifest = {
            "total_matches": 0,
            "oldest_timestamp": None,
            "file_mappings": {},
        }

    manifest.setdefault("manifest_schema_version", 2)
    manifest.setdefault("record_schema_version", 1)
    manifest.setdefault("batch_schema_versions", {})
    return manifest


def save_manifest(tier: str, manifest: dict) -> None:
    manifest["manifest_schema_version"] = 2
    manifest["record_schema_version"] = RECORD_SCHEMA_VERSION
    manifest["last_updated"] = int(time.time())
    manifest["total_matches"] = len(manifest["file_mappings"])
    destination = manifest_path(tier)
    temporary_path = destination.with_suffix(".pending.json")
    try:
        temporary_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary_path.replace(destination)
    finally:
        temporary_path.unlink(missing_ok=True)


def fetch_match_ids(
    tier: str,
    before: int | None,
    session: requests.Session,
) -> tuple[list[str], int | None]:
    params = {"format": tier}
    if before:
        params["before"] = str(before)
    response = session.get(
        "https://replay.pokemonshowdown.com/search.json",
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    matches = response.json()
    if not matches:
        return [], None
    return [match["id"] for match in matches], matches[-1]["uploadtime"]


def _atomic_write_parquet(frame: pl.DataFrame, destination: Path) -> None:
    temporary_path = destination.with_suffix(".pending.parquet")
    try:
        frame.write_parquet(temporary_path, compression="zstd")
        temporary_path.replace(destination)
    finally:
        temporary_path.unlink(missing_ok=True)


def save_batch(
    tier: str,
    frames: list[pl.DataFrame],
    match_ids: list[str],
    manifest: dict,
) -> None:
    batch_directory = DATA_ROOT / "raw_batches" / tier
    batch_directory.mkdir(parents=True, exist_ok=True)
    file_name = f"{tier}_batch_{time.time_ns()}.parquet"
    file_path = batch_directory / file_name
    combined = coerce_team_records(pl.concat(frames, how="vertical_relaxed"))
    _atomic_write_parquet(combined, file_path)

    for match_id in match_ids:
        manifest["file_mappings"][match_id] = file_name
    manifest["batch_schema_versions"][file_name] = RECORD_SCHEMA_VERSION
    batch_oldest = combined.select(pl.col("uploadtime").min()).item()
    current_oldest = manifest.get("oldest_timestamp")
    if current_oldest is None or batch_oldest < current_oldest:
        manifest["oldest_timestamp"] = int(batch_oldest)
    save_manifest(tier, manifest)


def ingest_tier(
    tier: str,
    max_pages: int = 100,
    request_delay: float = 0.2,
) -> int:
    manifest = load_manifest(tier)
    mappings = manifest["file_mappings"]
    session = requests.Session()
    before: int | None = None
    ingested = 0

    print(f"[{tier}] starting with {len(mappings):,} matches")
    for page in range(1, max_pages + 1):
        match_ids, oldest_in_page = fetch_match_ids(tier, before, session)
        if not match_ids:
            break

        new_ids = [match_id for match_id in match_ids if match_id not in mappings]
        if not new_ids:
            print(f"[{tier}] reached known data on page {page}")
            break

        frames: list[pl.DataFrame] = []
        saved_ids: list[str] = []
        for match_id in new_ids:
            try:
                frames.append(fetch_and_parse_replay(match_id, session))
                saved_ids.append(match_id)
            except (requests.RequestException, KeyError, ValueError) as exc:
                print(f"[{tier}] skipped {match_id}: {exc}")
            time.sleep(request_delay)

        if frames:
            save_batch(tier, frames, saved_ids, manifest)
            ingested += len(saved_ids)
            print(f"[{tier}] page {page}: saved {len(saved_ids):,}")

        if len(new_ids) < len(match_ids):
            break
        before = oldest_in_page
        if before is None:
            break

    print(f"[{tier}] incremental complete: {ingested:,} new matches")
    return ingested


def _matches_for_batch(manifest: dict, file_name: str) -> list[str]:
    return sorted(
        match_id
        for match_id, mapped_file in manifest["file_mappings"].items()
        if mapped_file == file_name
    )


def enrich_existing_batches(
    tier: str,
    max_batches: int = 10,
    request_delay: float = 0.2,
) -> int:
    """Re-fetch legacy batches and replace them atomically with schema-v2 rows.

    Progress is persisted per batch in the manifest. A batch is replaced only
    when every mapped replay was fetched and parsed successfully, so interrupted
    or partial runs cannot silently create a mixed or incomplete batch.
    """
    manifest = load_manifest(tier)
    batch_versions = manifest["batch_schema_versions"]
    batch_directory = DATA_ROOT / "raw_batches" / tier
    all_batches = sorted(set(manifest["file_mappings"].values()))
    pending_batches = [
        file_name
        for file_name in all_batches
        if int(batch_versions.get(file_name, 1)) < RECORD_SCHEMA_VERSION
    ]
    selected_batches = pending_batches[:max_batches]
    session = requests.Session()
    completed = 0

    print(
        f"[{tier}] enrichment: {len(pending_batches):,} legacy batches pending; "
        f"processing up to {max_batches:,}"
    )
    for position, file_name in enumerate(selected_batches, start=1):
        match_ids = _matches_for_batch(manifest, file_name)
        file_path = batch_directory / file_name
        if not match_ids or not file_path.exists():
            print(f"[{tier}] cannot enrich {file_name}: batch or mappings missing")
            continue

        frames: list[pl.DataFrame] = []
        failed: list[str] = []
        for match_id in match_ids:
            try:
                frames.append(fetch_and_parse_replay(match_id, session))
            except (requests.RequestException, KeyError, ValueError) as exc:
                failed.append(match_id)
                print(f"[{tier}] enrichment fetch failed for {match_id}: {exc}")
            time.sleep(request_delay)

        if failed:
            print(
                f"[{tier}] kept {file_name} unchanged because "
                f"{len(failed):,} replay(s) failed"
            )
            continue

        combined = coerce_team_records(pl.concat(frames, how="vertical_relaxed"))
        actual_ids = set(combined.get_column("match_id").unique())
        if actual_ids != set(match_ids) or combined.height != len(match_ids) * 2:
            print(f"[{tier}] kept {file_name} unchanged: match validation failed")
            continue

        _atomic_write_parquet(combined, file_path)
        batch_versions[file_name] = RECORD_SCHEMA_VERSION
        save_manifest(tier, manifest)
        completed += 1
        print(
            f"[{tier}] enriched batch {position}/{len(selected_batches)}: "
            f"{file_name} ({len(match_ids):,} matches)"
        )

    print(f"[{tier}] enrichment complete: {completed:,} batches upgraded")
    return completed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tier",
        choices=[*TIERS, "all"],
        default="all",
    )
    parser.add_argument(
        "--mode",
        choices=["incremental", "enrich", "both"],
        default="incremental",
        help="Ingest new replays, upgrade legacy batches, or do both.",
    )
    parser.add_argument("--max-pages", type=int, default=100)
    parser.add_argument("--max-enrichment-batches", type=int, default=10)
    parser.add_argument("--request-delay", type=float, default=0.2)
    arguments = parser.parse_args()
    selected_tiers = list(TIERS) if arguments.tier == "all" else [arguments.tier]

    for tier in selected_tiers:
        if arguments.mode in {"enrich", "both"}:
            enrich_existing_batches(
                tier,
                max_batches=arguments.max_enrichment_batches,
                request_delay=arguments.request_delay,
            )
        if arguments.mode in {"incremental", "both"}:
            ingest_tier(
                tier,
                max_pages=arguments.max_pages,
                request_delay=arguments.request_delay,
            )
