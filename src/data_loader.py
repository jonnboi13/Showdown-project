import zipfile
import io
import requests
from pathlib import Path

def ensure_format_data(format_tier: str):
    format_dir = Path(__file__).parent.parent / "data" / "raw_batches" / format_tier

    if not format_dir.exists() or not any(format_dir.iterdir()):
        print(f"Data for {format_tier} not found locally. Downloading from GitHub Release...")

        repo = "jonnboi13/Showdown-project"
        tag = "v1.0.0"
        download_url = f"https://github.com/{repo}/releases/download/{tag}/{format_tier}_batches.zip"

        response = requests.get(download_url)
        if response.status_code == 200:
            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                z.extractall(format_dir.parent)
            print(f"Successfully downloaded and extracted {format_tier} batches!")
        else:
            print(f"Failed to download {format_tier} dataset. Status code: {response.status_code}")