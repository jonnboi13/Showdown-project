import os
import urllib.request
import streamlit as st

# Define your GitHub Release asset base URL
RELEASE_URL = "https://github.com/jonnboi13/Showdown-project/releases/download/v1.0.0"

# List the files your app needs (e.g., manifest and your parquet files)
FILES_TO_DOWNLOAD = [
    "manifest.json",
    "gen9ou.parquet",
    "gen9uu.parquet",
    "gen9ubers.parquet"
]

@st.cache_resource
def ensure_data_loaded():
    data_dir = "data"
    os.makedirs(data_dir, exist_ok=True)
    
    missing_files = [f for f in FILES_TO_DOWNLOAD if not os.path.exists(os.path.join(data_dir, f))]
    
    if missing_files:
        with st.spinner("Downloading required datasets from GitHub Release... This only happens on initial boot."):
            for filename in missing_files:
                file_url = f"{RELEASE_URL}/{filename}"
                dest_path = os.path.join(data_dir, filename)
                try:
                    urllib.request.urlretrieve(file_url, dest_path)
                except Exception as e:
                    st.error(f"Failed to download {filename}: {e}")