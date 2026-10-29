"""GitHub Release-backed dataset access.

GitHub is the source of truth. Every new dataset load checks the release API first,
then reuses an immutable temporary cache only when its asset IDs and digests match
the current release.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import requests

from showdown_app.config import (
    CACHE_ROOT,
    RELEASE_API_URL,
    RELEASE_REPOSITORY,
    RELEASE_TAG,
    TIERS,
)
from showdown_pipeline.schema import TEAM_RECORD_SCHEMA


@dataclass(frozen=True)
class TierDataset:
    tier: str
    dataset_path: Path
    manifest_path: Path
    remote_match_count: int
    actual_match_count: int
    record_count: int
    integrity_gap: int
    release_updated_at: str
    release_url: str
    asset_id: int
    asset_digest: str | None
    cache_hit: bool


class DatasetSourceError(RuntimeError):
    """Raised when an authoritative release asset cannot be prepared safely."""


def _github_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "showdown-meta-lab",
    }
    github_token = os.getenv("GITHUB_TOKEN")
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"
    return headers


def fetch_release_metadata(session: requests.Session | None = None) -> dict:
    client = session or requests.Session()
    response = client.get(
        RELEASE_API_URL,
        headers=_github_headers(),
        timeout=30,
    )
    response.raise_for_status()
    release = response.json()
    if release.get("tag_name") != RELEASE_TAG:
        raise DatasetSourceError(
            f"Expected release {RELEASE_TAG}, received {release.get('tag_name')!r}."
        )
    return release


def _release_assets(release: dict) -> dict[str, dict]:
    return {asset["name"]: asset for asset in release.get("assets", [])}


def _expected_digest(asset: dict) -> str | None:
    digest = asset.get("digest")
    if isinstance(digest, str) and digest.startswith("sha256:"):
        return digest.removeprefix("sha256:")
    return None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download_asset(
    client: requests.Session,
    asset: dict,
    destination: Path,
) -> None:
    with client.get(
        asset["browser_download_url"],
        headers={"User-Agent": "showdown-meta-lab"},
        timeout=180,
        stream=True,
    ) as response:
        response.raise_for_status()
        with destination.open("wb") as output:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    output.write(chunk)

    expected = _expected_digest(asset)
    actual = _sha256(destination)
    if expected and actual != expected:
        raise DatasetSourceError(
            f"Digest check failed for {asset['name']}: expected {expected}, got {actual}."
        )


def _safe_extract(archive_path: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    destination_root = destination.resolve()
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            member_path = (destination / member.filename).resolve()
            if not member_path.is_relative_to(destination_root):
                raise DatasetSourceError(
                    f"Unsafe path in release archive: {member.filename}"
                )
        archive.extractall(destination)


def _manifest_match_count(manifest_path: Path) -> int:
    with manifest_path.open("r", encoding="utf-8") as source:
        manifest = json.load(source)
    mappings = manifest.get("file_mappings", {})
    if not isinstance(mappings, dict) or not mappings:
        raise DatasetSourceError("The downloaded manifest has no match mappings.")
    return len(mappings)


def _consolidate_parquet(raw_directory: Path, destination: Path) -> tuple[int, int]:
    parquet_files = sorted(raw_directory.rglob("*.parquet"))
    if not parquet_files:
        raise DatasetSourceError("The release archive contains no Parquet files.")

    normalized_batches: list[pl.LazyFrame] = []
    for parquet_file in parquet_files:
        batch = pl.scan_parquet(parquet_file)
        available_columns = set(batch.collect_schema().names())
        normalized_batches.append(batch.select([
            (
                pl.col(column).cast(dtype, strict=False)
                if column in available_columns
                else pl.lit(
                    1 if column == "schema_version" else None,
                    dtype=dtype,
                )
            ).alias(column)
            for column, dtype in TEAM_RECORD_SCHEMA.items()
        ]))

    pl.concat(normalized_batches, how="vertical").sink_parquet(
        destination,
        compression="zstd",
    )
    counts = (
        pl.scan_parquet(destination)
        .select([
            pl.len().alias("records"),
            pl.col("match_id").n_unique().alias("matches"),
        ])
        .collect()
        .row(0, named=True)
    )
    return counts["records"], counts["matches"]


def _ready_dataset(
    tier: str,
    target_directory: Path,
    release: dict,
    archive_asset: dict,
    manifest_asset: dict,
    cache_hit: bool,
) -> TierDataset:
    source_path = target_directory / "source.json"
    dataset_path = target_directory / "dataset.parquet"
    manifest_path = target_directory / "manifest.json"
    with source_path.open("r", encoding="utf-8") as source:
        metadata = json.load(source)
    return TierDataset(
        tier=tier,
        dataset_path=dataset_path,
        manifest_path=manifest_path,
        remote_match_count=metadata["remote_match_count"],
        actual_match_count=metadata["actual_match_count"],
        record_count=metadata["record_count"],
        integrity_gap=metadata["integrity_gap"],
        release_updated_at=release["updated_at"],
        release_url=release["html_url"],
        asset_id=archive_asset["id"],
        asset_digest=archive_asset.get("digest"),
        cache_hit=cache_hit,
    )


def ensure_tier_dataset(
    tier: str,
    session: requests.Session | None = None,
) -> TierDataset:
    """Validate the current GitHub release and return its selected tier dataset."""
    if tier not in TIERS:
        raise ValueError(f"Unsupported tier: {tier}")

    client = session or requests.Session()
    release = fetch_release_metadata(client)
    assets = _release_assets(release)
    archive_name = f"{tier}_batches.zip"
    manifest_name = f"{tier}_manifest.json"

    try:
        archive_asset = assets[archive_name]
        manifest_asset = assets[manifest_name]
    except KeyError as exc:
        raise DatasetSourceError(
            f"Release {RELEASE_TAG} is missing the required asset {exc.args[0]}."
        ) from exc

    cache_key = f"{archive_asset['id']}-{manifest_asset['id']}"
    tier_cache_root = CACHE_ROOT / RELEASE_TAG / tier
    target_directory = tier_cache_root / cache_key
    source_path = target_directory / "source.json"
    dataset_path = target_directory / "dataset.parquet"
    manifest_path = target_directory / "manifest.json"

    if source_path.exists() and dataset_path.exists() and manifest_path.exists():
        return _ready_dataset(
            tier,
            target_directory,
            release,
            archive_asset,
            manifest_asset,
            cache_hit=True,
        )

    tier_cache_root.mkdir(parents=True, exist_ok=True)
    staging_directory = Path(
        tempfile.mkdtemp(prefix=f".{tier}-", dir=tier_cache_root)
    )

    try:
        archive_path = staging_directory / archive_name
        staged_manifest_path = staging_directory / "manifest.json"
        raw_directory = staging_directory / "raw"
        staged_dataset_path = staging_directory / "dataset.parquet"

        _download_asset(client, archive_asset, archive_path)
        _download_asset(client, manifest_asset, staged_manifest_path)
        remote_match_count = _manifest_match_count(staged_manifest_path)
        _safe_extract(archive_path, raw_directory)
        record_count, match_count = _consolidate_parquet(
            raw_directory,
            staged_dataset_path,
        )

        integrity_gap = remote_match_count - match_count
        material_gap = max(5, round(remote_match_count * 0.001))
        if abs(integrity_gap) > material_gap:
            raise DatasetSourceError(
                "Release validation failed: the manifest lists "
                f"{remote_match_count:,} matches but the Parquet archive contains "
                f"{match_count:,}; the {abs(integrity_gap):,}-match difference exceeds "
                f"the {material_gap:,}-match safety threshold."
            )

        source_metadata = {
            "repository": RELEASE_REPOSITORY,
            "release_tag": RELEASE_TAG,
            "release_updated_at": release["updated_at"],
            "release_url": release["html_url"],
            "archive_asset_id": archive_asset["id"],
            "archive_digest": archive_asset.get("digest"),
            "manifest_asset_id": manifest_asset["id"],
            "manifest_digest": manifest_asset.get("digest"),
            "remote_match_count": remote_match_count,
            "actual_match_count": match_count,
            "record_count": record_count,
            "integrity_gap": integrity_gap,
            "prepared_at": datetime.now(UTC).isoformat(),
        }
        (staging_directory / "source.json").write_text(
            json.dumps(source_metadata, indent=2),
            encoding="utf-8",
        )

        archive_path.unlink()
        shutil.rmtree(raw_directory)
        try:
            os.replace(staging_directory, target_directory)
        except OSError:
            if not target_directory.exists():
                raise
            shutil.rmtree(staging_directory, ignore_errors=True)

        for old_cache in tier_cache_root.iterdir():
            if old_cache.is_dir() and old_cache != target_directory:
                shutil.rmtree(old_cache, ignore_errors=True)
    except Exception:
        shutil.rmtree(staging_directory, ignore_errors=True)
        raise

    return _ready_dataset(
        tier,
        target_directory,
        release,
        archive_asset,
        manifest_asset,
        cache_hit=False,
    )


def dataset_metadata(dataset: TierDataset) -> dict:
    """Return serializable source metadata for status panels and diagnostics."""
    return asdict(dataset)
