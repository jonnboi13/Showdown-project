# Pokémon Showdown Meta Lab

[![Streamlit App](https://img.shields.io/badge/Streamlit-Live%20App-7F56D9?style=for-the-badge&logo=streamlit&logoColor=white)](https://showdown-projectgit-mbetkr9fi9vhup2xqbggbq.streamlit.app)

A senior data-science project that turns public Pokémon Showdown replays into a connected analysis of team selection, player results, metagame change, and individual battles.

The dashboard is written for both competitive players and people who do not know Pokémon. Terms are defined in plain language, headline findings link to their underlying evidence, and uncertainty is shown beside observed win rates.

## The problem

Pokémon Showdown publishes individual replay logs, but a single replay does not reveal broader patterns. Answering questions such as “Which choices are common?”, “Which results are supported by enough data?”, or “How did usage change this week?” requires a repeatable ingestion pipeline, a consistent data model, and analysis that remains traceable to individual records.

## What the project does

- Collects new public replays for three Generation 9 singles formats.
- Parses each battle into two team-level records.
- Captures first-KO timing and outcome fields while explicitly marking same-turn double KOs and no-KO finishes.
- Stores compressed Parquet batches and a match-to-file manifest in GitHub Releases.
- Validates release asset IDs and SHA-256 digests before analysis.
- Consolidates remote batches into a temporary runtime cache for faster Polars queries.
- Connects overview findings to Pokémon profiles, player profiles, battle details, and original replays.
- Reports sample sizes and Wilson 95% intervals so small-sample results are visible.

## Verified data result

On October 21, 2026, the GitHub Release manifests listed **88,067 battles**:

- 73,311 Gen 9 OU battles
- 6,614 Gen 9 UU battles
- 8,142 Gen 9 Ubers battles

A normal battle produces two team records, so this release represents about 176,000 player-team observations before rating filters. The validated archives contained 88,066 unique battles: the OU archive was one battle short of its manifest, an integrity gap the app discloses instead of hiding. The dashboard reads the current release metadata at runtime; these counts will grow as ingestion continues.

## Dashboard structure

- **Overview:** computed findings, usage patterns, outcome uncertainty, recent usage change, rating distribution, and battle length.
- **First KO study:** data readiness, the primary association estimate, uncertainty, subgroup comparisons, exclusions, and linked source battles.
- **Pokémon:** a filterable comparison table and linked profiles with daily trends, common teammates, and source battles.
- **Players:** activity and outcome comparisons with linked team choices and battle history.
- **Battles:** searchable replay records with linked players, linked Pokémon, both rosters, and the original Showdown replay.
- **About the data:** definitions, pipeline architecture, source status, and limitations.

## Data source design

GitHub Releases are the dashboard's source of truth. The app does not read a repository-local `data/` directory.

At runtime it:

1. Requests metadata for release `v1.0.0`.
2. Selects the current archive and manifest asset IDs for the chosen format.
3. Reuses a temporary cache only when those IDs match the current release.
4. Downloads changed assets and validates available SHA-256 digests.
5. Compares manifest and Parquet match counts and reports any small discrepancy.
6. Consolidates many small Parquet batches into one temporary file.

This keeps the deployed app current without committing generated data to Git.

## Repository structure

```text
showdown_app/
  analytics.py       metric definitions and Polars queries
  charts.py          reusable interactive chart definitions
  config.py          tiers, release location, and defaults
  data_source.py     GitHub validation, downloads, and cache preparation
  pages.py           linked dashboard page renderers
  services.py        cached query and profile services
  ui.py              shared Streamlit presentation components
showdown_pipeline/
  schema.py          versioned team-record data contract
  parser.py          deterministic replay and first-KO parsing
  ingestion.py       incremental collection and resumable enrichment
scripts/
  ingest.py          thin pipeline command-line entry point
  parse_replay.py    compatibility imports for older callers
  check_project.py   compilation, unit, and optional app checks
tests/               parser and analytics tests
docs/                architecture and data dictionary
.github/workflows/   scheduled ingestion and release publishing
app.py               Streamlit entry point and linked pages
```

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py
```

The first visit to each format downloads and validates its current release assets. Later runs reuse the matching temporary cache after checking GitHub release metadata.

## Checks

Run the fast deterministic checks:

```bash
python scripts/check_project.py
```

Include a full Streamlit smoke test against the current remote data:

```bash
python scripts/check_project.py --with-app
```

## Data pipeline

Collect new replays using the current schema:

```bash
python -m scripts.ingest --mode incremental
```

Upgrade a limited number of existing batches with first-KO data:

```bash
python -m scripts.ingest \
  --tier gen9ou \
  --mode enrich \
  --max-enrichment-batches 10
```

Enrichment is resumable and atomic. The manifest records each completed batch,
and a legacy batch is replaced only when every mapped replay has been fetched,
parsed, and validated. The GitHub Actions workflow exposes the same modes for
manual runs. Its daily schedule collects new replays, while each push to `main`
runs both incremental collection and up to ten historical enrichment batches per
tier. The resulting Parquet archives and manifests are published as GitHub Release
assets rather than committed to the branch.

## Metric definitions

- **Usage rate:** a Pokémon's appearances divided by filtered team records.
- **Observed win rate:** wins divided by appearances in this replay sample.
- **95% interval:** Wilson score interval for observed win rate.
- **Usage change:** latest seven-day usage minus the preceding seven-day usage.
- **First-KO win rate:** share of eligible matches won by the side whose opponent fainted first.

See [the first-KO analysis plan](docs/FIRST_KO_ANALYSIS.md),
[data dictionary](docs/DATA_DICTIONARY.md), and
[architecture notes](docs/ARCHITECTURE.md) for details.

## Limitations

Public replays are not a random sample of every battle. Results are descriptive, not causal: player skill, teammates, matchups, and replay-selection behavior can influence both Pokémon selection and outcomes. Public account names also may not correspond one-to-one with people.
