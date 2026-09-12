import json
import time
from pathlib import Path
import polars as pl
import requests
from parse import parse_match


def get_manifest_path(format_tier: str) -> Path:
    manifest_dir = Path(__file__).parent.parent / "data" / "manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    return manifest_dir / f"{format_tier}_manifest.json"


def load_manifest(format_tier: str) -> dict:
    manifest_path = get_manifest_path(format_tier)
    if manifest_path.exists():
        with open(manifest_path, "r") as f:
            return json.load(f)
    return {
        "total_matches": 0,
        "oldest_timestamp": None,
        "file_mappings": {}
    }


def save_manifest(format_tier: str, manifest_data: dict):
    manifest_path = get_manifest_path(format_tier)
    manifest_data["last_updated"] = int(time.time())
    with open(manifest_path, "w") as f:
        json.dump(manifest_data, f, indent=2)


def fetch_match_ids(format_tier: str, before: int = None):
    url = f"https://replay.pokemonshowdown.com/search.json?format={format_tier}"
    
    if before:
        url += f"&before={before}"
        
    response = requests.get(url)
    matches = response.json()

    if not matches:
        return [], None

    match_ids = [match["id"] for match in matches]
    oldest_in_batch = matches[-1]["uploadtime"]

    return match_ids, oldest_in_batch


def run_ingestion(format_tier: str, backfill: bool = False, pages: int = 1):
    path = Path(__file__).parent.parent / "data" / "raw_batches" / format_tier
    path.mkdir(parents=True, exist_ok=True)

    manifest = load_manifest(format_tier)
    file_mappings = manifest["file_mappings"]
    
    print(f"Loaded manifest: {len(file_mappings)} matches tracked. Oldest watermarked timestamp: {manifest['oldest_timestamp']}")

    if backfill:
        print(f"\n--- Starting Backfill Mode (Max pages: {pages}) ---")
        for page in range(pages):
            before_timestamp = manifest["oldest_timestamp"]
            print(f"Backfill page {page + 1} of {pages} using watermark timestamp: {before_timestamp}")

            match_ids, oldest_in_batch = fetch_match_ids(format_tier, before=before_timestamp)

            if not match_ids:
                print("No more matches found from the API. Stopping backfill.")
                break

            parsed_dfs = []
            new_batch_ids = []

            for match_id in match_ids:
                if match_id in file_mappings:
                    continue

                try:
                    df = parse_match(match_id)
                    parsed_dfs.append(df)
                    new_batch_ids.append(match_id)
                except Exception as e:
                    print(f"Error parsing match {match_id}: {e}")
                time.sleep(0.2)

            if parsed_dfs:
                timestamp = int(time.time())
                file_name = f"{format_tier}_batch_{timestamp}.parquet"
                file_path = path / file_name
                
                combined_df = pl.concat(parsed_dfs)
                combined_df.write_parquet(file_path)
                
                batch_min_time = combined_df.select(pl.col("uploadtime").min()).item()
                
                for match_id in new_batch_ids:
                    file_mappings[match_id] = file_name
                    
                manifest["total_matches"] = len(file_mappings)
                
                if manifest["oldest_timestamp"] is None or batch_min_time < manifest["oldest_timestamp"]:
                    manifest["oldest_timestamp"] = int(batch_min_time)
                    
                save_manifest(format_tier, manifest)
                print(f"Successfully saved {len(parsed_dfs)} new matches to {file_path}")
            else:
                print("No new unique matches were parsed in this batch.")

            if page < pages - 1:
                time.sleep(1)
    else:
        print(f"\n--- Starting Dynamic Catch-Up Mode ---")
        before_timestamp = None
        max_safety_pages = 100
        page = 0

        while page < max_safety_pages:
            page += 1
            print(f"Fetching recent batch page {page}...")
            match_ids, oldest_in_batch = fetch_match_ids(format_tier, before=before_timestamp)

            if not match_ids:
                print("No more matches returned from API. Catch-up complete.")
                break

            # Filter for IDs we haven't stored yet
            new_match_ids = [mid for mid in match_ids if mid not in file_mappings]

            if not new_match_ids:
                print("Reached fully known matches. Catch-up gap successfully closed!")
                break

            parsed_dfs = []
            saved_batch_ids = []

            for match_id in new_match_ids:
                try:
                    df = parse_match(match_id)
                    parsed_dfs.append(df)
                    saved_batch_ids.append(match_id)
                except Exception as e:
                    print(f"Error parsing match {match_id}: {e}")
                time.sleep(0.2)

            if parsed_dfs:
                timestamp = int(time.time())
                file_name = f"{format_tier}_batch_{timestamp}.parquet"
                file_path = path / file_name
                
                combined_df = pl.concat(parsed_dfs)
                combined_df.write_parquet(file_path)
                
                batch_min_time = combined_df.select(pl.col("uploadtime").min()).item()
                
                for match_id in saved_batch_ids:
                    file_mappings[match_id] = file_name
                    
                manifest["total_matches"] = len(file_mappings)
                
                if manifest["oldest_timestamp"] is None or batch_min_time < manifest["oldest_timestamp"]:
                    manifest["oldest_timestamp"] = int(batch_min_time)
                    
                save_manifest(format_tier, manifest)
                print(f"Successfully saved {len(parsed_dfs)} new matches to {file_path}")

            if len(new_match_ids) < len(match_ids):
                print("Overlap detected with existing database. Catch-up complete.")
                break

            before_timestamp = oldest_in_batch
            time.sleep(1)


if __name__ == "__main__":
    run_ingestion("gen9ubers", backfill=False)