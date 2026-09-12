import json
from pathlib import Path
import polars as pl

def get_tier_lazyframe(format_tier: str) -> pl.LazyFrame:
    """
    Loads all verified batch files for a given tier into a Polars LazyFrame 
    using the manifest ledger as the absolute source of truth.
    """
    manifest_path = Path(__file__).parent.parent / "data" / "manifests" / f"{format_tier}_manifest.json"
    
    if not manifest_path.exists():
        raise FileNotFoundError(f"No manifest found for tier: {format_tier}")
        
    with open(manifest_path, "r") as f:
        manifest = json.loadf if hasattr(json, 'loadf') else json.load(f) # standard json.load
        
    # Extract unique parquet filenames from the ledger values
    batch_files = list(set(manifest["file_mappings"].values()))
    
    if not batch_files:
        raise ValueError(f"Manifest for {format_tier} contains no file mappings.")
        
    base_path = Path(__file__).parent.parent / "data" / "raw_batches" / format_tier
    file_paths = [base_path / file_name for file_name in batch_files]
    
    # Return a lazy frame scanning only the ledger-approved files
    return pl.scan_parquet(file_paths)


def compute_pokemon_stats(lf: pl.LazyFrame, min_rating: int = 0) -> pl.DataFrame:
    """
    Explodes the pokemon list, normalizes names to remove gender tags,
    filters by an optional minimum rating threshold, and aggregates stats.
    """
    total_matches_expr = lf.filter(pl.col("rating") >= min_rating).select(pl.len()).collect().item()
    
    if total_matches_expr == 0:
        return pl.DataFrame(schema={
            "pokemon": pl.Utf8, 
            "appearances": pl.Int64, 
            "wins": pl.Int64, 
            "avg_rating": pl.Float64, 
            "usage_rate_pct": pl.Float64, 
            "win_rate": pl.Float64
        })

    return (
        lf.filter(pl.col("rating") >= min_rating)
          .explode("pokemon")
          .with_columns(
              # Removes trailing ", M" or ", F" gender tags and "-*" suffixes
              pl.col("pokemon").str.replace(r"(,\s+[MF]|\-\*)$", "").alias("pokemon")
          )
          .group_by("pokemon")
          .agg([
              pl.len().alias("appearances"),
              pl.col("won").sum().alias("wins"),
              pl.col("rating").mean().alias("avg_rating")
          ])
          .with_columns([
              ((pl.col("appearances") / total_matches_expr) * 100).round(1).alias("usage_rate_pct"),
              (pl.col("wins") / pl.col("appearances")).round(2).alias("win_rate"),
              pl.col("avg_rating").round(1).alias("avg_rating")
          ])
          .sort("appearances", descending=True)
          .collect()
    )


def compute_meta_summary(lf: pl.LazyFrame, min_rating: int = 0) -> dict:
    """
    Computes high-level global statistics for the tier overview dashboard,
    respecting the minimum rating filter and handling empty sets safely.
    """
    filtered_lf = lf.filter(pl.col("rating") >= min_rating)
    total_records = filtered_lf.select(pl.len()).collect().item()
    
    if total_records == 0:
        return {
            "total_player_records": 0,
            "avg_turns": 0.0,
            "avg_rating": 0.0
        }

    summary = (
        filtered_lf
          .select([
              pl.len().alias("total_player_records"),
              pl.col("turns").mean().alias("avg_turns"),
              pl.col("rating").mean().alias("avg_rating")
          ])
          .collect()
          .row(0, named=True)
    )
    return summary


def get_filtered_matches(lf: pl.LazyFrame, player_query: str = "", min_rating: int = 0, limit: int = 50) -> pl.DataFrame:
    """
    Returns a summarized DataFrame combining both players per match_id,
    filtered by rating and optional player name, sorted by most recent upload time.
    """
    filtered = lf.filter(pl.col("rating") >= min_rating)
    
    if player_query:
        # Find match_ids where either player matches the query
        matching_ids = (
            filtered.filter(pl.col("player").str.to_lowercase().str.contains(player_query.lower()))
            .select("match_id")
            .unique()
        )
        filtered = filtered.join(matching_ids, on="match_id", how="inner")

    # Aggregate the two player rows per match_id into a single row with Player 1 vs Player 2
    return (
        filtered.group_by(["match_id", "uploadtime"])
        .agg([
            pl.col("player").sort_by("won", descending=True).first().alias("winner"),
            pl.col("player").sort_by("won", descending=False).first().alias("loser"),
            pl.col("rating").mean().alias("avg_rating"),
            pl.col("turns").first().alias("turns")
        ])
        .sort("uploadtime", descending=True)
        .limit(limit)
        .collect()
    )


def get_match_details(format_tier: str, match_id: str) -> list[dict]:
    """
    Performs an O(1) lookup of a specific match using the manifest ledger
    to identify the exact Parquet file, then filters down to the match record.
    """
    manifest_path = Path(__file__).parent.parent / "data" / "manifests" / f"{format_tier}_manifest.json"
    
    if not manifest_path.exists():
        raise FileNotFoundError(f"No manifest found for tier: {format_tier}")
        
    with open(manifest_path, "r") as f:
        manifest = json.load(f)
        
    file_mappings = manifest.get("file_mappings", {})
    if match_id not in file_mappings:
        raise KeyError(f"Match ID '{match_id}' not found in manifest ledger.")
        
    target_file = file_mappings[match_id]
    file_path = Path(__file__).parent.parent / "data" / "raw_batches" / format_tier / target_file
    
    # Scan only the single target file and filter for the specific match_id
    match_df = (
        pl.scan_parquet(file_path)
          .filter(pl.col("match_id") == match_id)
          .collect()
    )
    
    return match_df.to_dicts()