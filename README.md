# Pokémon Showdown Meta Dashboard

[![Streamlit App](https://img.shields.io/badge/Streamlit-Live%20App-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://showdown-projectgit-mbetkr9fi9vhup2xqbggbq.streamlit.app)

A high-performance analytics platform and web application for exploring competitive Pokémon Showdown metagame trends, battle statistics, and individual match replays. Built to process massive scale battle log data using efficient query engines and a serverless deployment architecture.

## Architecture & Design

To bypass standard Git repository size limitations without relying on complex external data warehouse services, this project implements a **GitHub Release Asset & Manifest Pipeline**:

- **Distributed Sharding:** Raw battle logs are partitioned into compressed Apache Parquet batch files (`.parquet`) organized by competitive tiers (`gen9ou`, `gen9uu`, `gen9ubers`).
- **Manifest Ledgering:** JSON manifest files track batch chunk metadata, row counts, and schema structures on-demand.
- **On-Demand Hydration:** `data_loader.py` checks local runtime storage on application boot, automatically pulling missing format `.zip` archives and lookup ledgers directly from versioned GitHub Releases (`v1.0.0`) using streaming HTTP requests.
- **Lazy Evaluation:** Powered by **Polars** lazyframes (`scan_parquet`), executing optimized relational query plans across large datasets with minimal memory overhead.

## Data Pipeline & Ingestion

The project includes an automated ingestion module (`ingest.py`) designed to interface directly with the Pokémon Showdown Replays API, maintaining an incremental data store without redundant processing:

- **Incremental Catch-Up Mode:** Dynamically queries recent matches, cross-references existing storage using local state manifests, and stops as soon as it hits a known data boundary.
- **Backfill Mode:** Utilizes watermark-based timestamp pagination (`&before=`) to step backward through historical match logs for deep dataset expansion.
- **Parquet Sharding & State Tracking:** Automatically parses raw battle logs into structured DataFrames, concatenates them into compressed `.parquet` batches, and updates a tracking JSON ledger (`_manifest.json`) mapping individual match IDs to their corresponding batch files.

<!-- ## Automated Orchestration & CI/CD

To ensure zero-touch, continuous metagame updates, the repository utilizes **GitHub Actions** (`.github/workflows/daily-ingest.yml`) to orchestrate daily EtLT runs:

- **Matrix Parallel Strategy:** Executes concurrent jobs across three competitive tiers (`gen9ou`, `gen9uu`, `gen9ubers`) using `fail-fast: false` to ensure isolated tier failures do not block the pipeline.
- **Scheduled & Manual Triggers:** Automated via a cron schedule running daily at `0 0 * * *` (midnight UTC) with `workflow_dispatch` enabled for on-demand manual execution.
- **Asset Sync & Clobbering:** Runners authenticate via `GH_TOKEN` to pull existing release archives and manifests, execute incremental updates via `src/ingest.py`, and clobber-update the release binaries on `v1.0.0`. -->

## Key Features

- **Real-Time Meta Summary:** Instantly computes overall player record counts, average battle turn lengths, and ladder rating distributions across configurable rating thresholds.
- **Tier Usage & Win Rates:** Aggregates individual Pokémon pick rates, win percentages, and appearance volumes with live text-filtering.
- **💎 Hidden Gems Finder:** Filters for niche Pokémon with high win rates and low overall usage rates using dynamic multi-variable sliders.
- **Match Inspector & Game Browser:** Deep-dive into specific player histories, view complete winner/loser team rosters, and launch directly into official Pokémon Showdown replays.

## Tech Stack

- **Data Processing & Analytics:** Polars
- **Web Framework & UI:** Streamlit
- **Data Ingestion & Packaging:** Requests, Zipfile, GitHub Releases API
<!-- - **Orchestration & CI/CD:** GitHub Actions (Matrix Strategy, GitHub CLI `gh`) -->
- **Version Control:** Git, Streamlit Cloud

## Local Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/jonnboi13/Showdown-project.git
   cd Showdown-project
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run Data Ingestion (Optional):**
   If you want to pull fresh battle logs directly from the Pokémon Showdown API and build or expand your own local Parquet shards and manifests from scratch instead of downloading them from the GitHub Release assets:
   ```bash
   python src/ingest.py
   ```
   *(By default, this runs in dynamic catch-up mode. You can modify the target tier or toggle backfill parameters directly inside `ingest.py`)*.

5. **Run the Streamlit application:**
   ```bash
   streamlit run app.py
   ```
   *(Note: If local data isn't present, the application will automatically fetch and unpack the necessary tier datasets from the GitHub Release assets on initial boot).*