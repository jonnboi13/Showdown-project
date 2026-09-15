import io
import requests
import zipfile
from pathlib import Path


def ensure_format_data(format_tier: str):
  base_dir = Path(__file__).parent.parent
  format_dir = base_dir / "data" / "raw_batches" / format_tier
  manifest_dir = base_dir / "data" / "manifests"
  manifest_dir.mkdir(parents=True, exist_ok=True)

  manifest_file = manifest_dir / f"{format_tier}_manifest.json"
  repo = "jonnboi13/Showdown-project"
  tag = "v1.0.0"

  # 1. Download and extract dataset zip from GitHub Release every time
  download_url = (
      f"https://github.com/{repo}/releases/download/{tag}/{format_tier}_batches.zip"
  )
  response = requests.get(download_url)
  print(f"[{format_tier}] Zip download status code: {response.status_code}")

  if response.status_code == 200:
    format_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
      z.extractall(format_dir)  # <-- Fixed: extract directly into format_dir
    print(f"[{format_tier}] Successfully extracted batches!")
  else:
    print(
        f"[{format_tier}] Failed to download dataset zip from: {download_url}"
    )

  # 2. Download corresponding manifest file from GitHub Release every time
  manifest_url = f"https://github.com/{repo}/releases/download/{tag}/{format_tier}_manifest.json"
  m_response = requests.get(manifest_url)
  print(
      f"[{format_tier}] Manifest download status code:"
      f" {m_response.status_code}"
  )

  if m_response.status_code == 200:
    with open(manifest_file, "wb") as f:
      f.write(m_response.content)
    print(f"[{format_tier}] Successfully downloaded manifest!")
  else:
    print(
        f"[{format_tier}] Failed to download manifest from: {manifest_url}"
    )

  # 2. Download corresponding manifest file from GitHub Release every time
  manifest_url = f"https://github.com/{repo}/releases/download/{tag}/{format_tier}_manifest.json"
  m_response = requests.get(manifest_url)
  print(
      f"[{format_tier}] Manifest download status code:"
      f" {m_response.status_code}"
  )

  if m_response.status_code == 200:
    with open(manifest_file, "wb") as f:
      f.write(m_response.content)
    print(f"[{format_tier}] Successfully downloaded manifest!")
  else:
    print(
        f"[{format_tier}] Failed to download manifest from: {manifest_url}"
    )


def ensure_data_ledgers_and_parquets():
  for tier in ["gen9ou", "gen9uu", "gen9ubers"]:
    ensure_format_data(tier)