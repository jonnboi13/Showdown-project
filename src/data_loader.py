import zipfile
import io
import requests
from pathlib import Path

def ensure_format_data(format_tier: str):
    base_dir = Path(__file__).parent.parent
    format_dir = base_dir / "data" / "raw_batches" / format_tier
    manifest_dir = base_dir / "data" / "manifests"
    manifest_file = manifest_dir / f"{format_tier}_manifest.json" # adjust name if yours is slightly different

    # 1. Ensure format zip is downloaded & extracted if missing
    if not format_dir.exists() or not any(format_dir.iterdir()):
        print(f"Data for {format_tier} not found locally. Downloading from GitHub Release...")
        
        repo = "jonathanoliphant/your-repo-name"  # Update with your actual repo
        tag = "v1.0.0"
        download_url = f"https://github.com/{repo}/releases/download/{tag}/{format_tier}_batches.zip"
        
        response = requests.get(download_url)
        if response.status_code == 200:
            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                z.extractall(format_dir.parent)
            print(f"Successfully downloaded and extracted {format_tier} batches!")
        else:
            print(f"Failed to download {format_tier} dataset. Status code: {response.status_code}")

    # 2. Ensure manifest file is downloaded if missing
    if not manifest_file.exists():
        manifest_dir.mkdir(parents=True, exist_ok=True)
        print(f"Manifest for {format_tier} not found locally. Downloading from GitHub Release...")
        
        repo = "jonathanoliphant/your-repo-name"  # Update with your actual repo
        tag = "v1.0.0"
        manifest_url = f"https://github.com/{repo}/releases/download/{tag}/{format_tier}_manifest.json"
        
        m_response = requests.get(manifest_url)
        if m_response.status_code == 200:
            with open(manifest_file, "wb") as f:
                f.write(m_response.content)
            print(f"Successfully downloaded manifest for {format_tier}!")
        else:
            print(f"Failed to download manifest. Status code: {m_response.status_code}")

def ensure_data_ledgers_and_parquets():
    # Helper wrapper to trigger checks across all tiers on startup
    for tier in ["gen9ou", "gen9uu", "gen9ubers"]:
        ensure_format_data(tier)