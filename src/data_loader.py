import os
import json
import urllib.request
import streamlit as st

RELEASE_URL = "https://github.com/jonnboi13/Showdown-project/releases/download/v1.0.0"

@st.cache_resource
def ensure_data_ledgers_and_parquets():
    data_dir = "data"
    manifest_dir = os.path.join(data_dir, "manifests")
    batch_dir = os.path.join(data_dir, "raw_batches", "gen9ou")
    
    os.makedirs(manifest_dir, exist_ok=True)
    os.makedirs(batch_dir, exist_ok=True)
    
    # 1. Check if manifest exists locally; if not, download it from GitHub
    manifest_filename = "gen9ou_manifest.json"
    manifest_path = os.path.join(manifest_dir, manifest_filename)
    
    if not os.path.exists(manifest_path):
        try:
            with st.spinner("Downloading manifest from GitHub..."):
                urllib.request.urlretrieve(f"{RELEASE_URL}/{manifest_filename}", manifest_path)
        except Exception as e:
            st.error(f"Failed to download manifest: {e}")
            return

    # 2. Parse the manifest to discover required parquet files dynamically
    with open(manifest_path, "r") as f:
        manifest_data = json.load(f)
    
    file_mappings = manifest_data.get("file_mappings", {})
    required_parquets = list(set(file_mappings.values()))
    
    # 3. Download any parquet files that aren't already in the local raw_batches directory
    missing_parquets = [p for p in required_parquets if not os.path.exists(os.path.join(batch_dir, p))]
    
    if missing_parquets:
        with st.spinner("Downloading missing dataset partitions from GitHub..."):
            for filename in missing_parquets:
                file_url = f"{RELEASE_URL}/{filename}"
                dest_path = os.path.join(batch_dir, filename)
                try:
                    urllib.request.urlretrieve(file_url, dest_path)
                except Exception as e:
                    st.error(f"Failed to download {filename}: {e}")