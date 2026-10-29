# Architecture

## Purpose

The application separates the public data pipeline from the interactive analysis. GitHub Releases are the durable data store; the Streamlit runtime uses only a digest-validated temporary cache.

## Data flow

1. A scheduled GitHub Actions workflow downloads the prior release assets.
2. `scripts/ingest.py` is a thin command-line entry point into `showdown_pipeline/`.
3. Incremental mode requests new public replay IDs and stops at known matches.
4. Enrichment mode re-fetches legacy replays and atomically upgrades each complete batch to the current record schema.
5. The parser converts each replay into two team records, including first-KO fields and explicit ambiguity markers.
6. New Parquet batches and updated manifests replace the assets on release `v1.0.0`.
7. The app checks the GitHub release API, validates changed assets, and consolidates schema-v1 and schema-v2 batches into one temporary Parquet file.
8. `showdown_app/analytics.py` runs lazy Polars queries against that consolidated file.
9. `app.py` presents linked overview, Pokémon, player, and battle views.

## Package responsibilities

- `showdown_pipeline/schema.py`: versioned team-record contract and legacy coercion.
- `showdown_pipeline/parser.py`: deterministic replay-log parsing.
- `showdown_pipeline/ingestion.py`: incremental collection and resumable enrichment.
- `scripts/`: thin command-line entry points and project checks.
- `showdown_app/config.py`: tiers, release location, and defaults.
- `showdown_app/data_source.py`: remote validation, download, digest checks, and cache preparation.
- `showdown_app/analytics.py`: metric definitions and lazy Polars queries.
- `showdown_app/pages.py`: linked dashboard page composition.
- `showdown_app/charts.py`: reusable Vega-Lite chart specifications.
- `showdown_app/ui.py`: shared styling, cards, linked tables, and team displays.
- `app.py`: application entry point and navigation.

## Schema evolution

Every team row has a `schema_version`. Version 1 is the original team-level
contract. Version 2 adds first-KO fields. The release manifest records the
schema version of each batch, allowing enrichment to resume over multiple
workflow runs.

Legacy fields are inserted as null during app-side consolidation. Null therefore
means “not parsed yet,” not “the replay had no KO.” A parsed no-KO replay has
`schema_version == 2`, `total_faints == 0`, and null `got_first_ko`.

Enrichment replaces a batch only after every replay mapped to that batch has
been fetched, parsed, and validated. Failed or interrupted batches stay unchanged
and remain eligible for a later retry.

## Cache contract

The repository's `data/` directory is ignored and is used only by the ingestion workflow. The dashboard never reads it. Runtime data lives under the operating system's temporary directory and is keyed by the current GitHub asset IDs. A changed release therefore creates a new immutable cache entry.
