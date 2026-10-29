"""Polars queries for the dashboard's descriptive analysis."""

from __future__ import annotations

from math import sqrt
from pathlib import Path
from urllib.parse import quote_plus

import polars as pl


Z_95 = 1.96


def scan_dataset(dataset_path: Path | str) -> pl.LazyFrame:
    return pl.scan_parquet(dataset_path)


def normalized_pokemon_element() -> pl.Expr:
    return (
        pl.element()
        .str.replace(r",.*$", "")
        .str.replace(r"\-\*$", "")
    )


def normalized_pokemon_column(column: str = "pokemon") -> pl.Expr:
    return (
        pl.col(column)
        .str.replace(r",.*$", "")
        .str.replace(r"\-\*$", "")
    )


def filtered_records(dataset_path: Path | str, min_rating: int) -> pl.LazyFrame:
    return scan_dataset(dataset_path).filter(pl.col("rating") >= min_rating)


def battle_filtered_records(
    dataset_path: Path | str,
    min_rating: int,
) -> pl.LazyFrame:
    """Keep both sides of battles whose average recorded rating meets the filter."""
    records = scan_dataset(dataset_path)
    included_matches = (
        records.group_by("match_id")
        .agg(pl.col("rating").mean().alias("match_rating"))
        .filter(pl.col("match_rating") >= min_rating)
        .select("match_id")
    )
    return records.join(included_matches, on="match_id", how="inner")


def compute_meta_summary(dataset_path: Path | str, min_rating: int = 0) -> dict:
    records = filtered_records(dataset_path, min_rating)
    matches = records.group_by("match_id").agg([
        pl.col("turns").first().alias("turns"),
        pl.col("rating").mean().alias("rating"),
        pl.col("uploadtime").first().alias("uploadtime"),
    ])
    summary = (
        matches.select([
            pl.len().alias("total_matches"),
            pl.col("turns").mean().alias("avg_turns"),
            pl.col("turns").median().alias("median_turns"),
            pl.col("rating").mean().alias("avg_rating"),
            pl.col("uploadtime").min().alias("first_upload"),
            pl.col("uploadtime").max().alias("last_upload"),
        ])
        .collect()
        .row(0, named=True)
    )
    record_summary = (
        records.select([
            pl.len().alias("team_records"),
            pl.col("player").n_unique().alias("unique_players"),
        ])
        .collect()
        .row(0, named=True)
    )
    return {**summary, **record_summary}


def compute_first_ko_summary(
    dataset_path: Path | str,
    min_rating: int = 0,
) -> dict:
    """Summarize whether the player credited with the first KO won.

    The denominator contains one row per match with an unambiguous first KO.
    Legacy rows, no-KO battles, and same-turn double KOs are reported as
    coverage categories rather than silently entering the denominator.
    """
    records = battle_filtered_records(dataset_path, min_rating)
    schema_names = set(records.collect_schema().names())
    required = {
        "schema_version",
        "first_ko_tied",
        "got_first_ko",
        "total_faints",
    }
    if not required.issubset(schema_names):
        return {
            "total_matches": records.select(
                pl.col("match_id").n_unique()
            ).collect().item(),
            "enriched_matches": 0,
            "unambiguous_matches": 0,
            "tied_matches": 0,
            "no_ko_matches": 0,
            "first_ko_wins": 0,
            "first_ko_win_rate": None,
            "first_ko_win_rate_low": None,
            "first_ko_win_rate_high": None,
            "lift_over_even_pct_points": None,
            "coverage_pct": 0.0,
        }

    match_status = records.group_by("match_id").agg([
        pl.col("schema_version").max().alias("schema_version"),
        pl.col("first_ko_tied").fill_null(False).any().alias("first_ko_tied"),
        pl.col("got_first_ko").is_not_null().any().alias("has_first_ko"),
        pl.col("total_faints").max().alias("total_faints"),
    ])
    first_ko_rows = records.filter(pl.col("got_first_ko"))

    status = match_status.select([
        pl.len().alias("total_matches"),
        (pl.col("schema_version") >= 2).sum().alias("enriched_matches"),
        pl.col("has_first_ko").sum().alias("unambiguous_matches"),
        pl.col("first_ko_tied").sum().alias("tied_matches"),
        (
            (pl.col("schema_version") >= 2)
            & (pl.col("total_faints") == 0)
        ).sum().alias("no_ko_matches"),
    ]).collect().row(0, named=True)
    outcome = first_ko_rows.select([
        pl.len().alias("first_ko_records"),
        pl.col("won").sum().alias("first_ko_wins"),
        pl.col("won").mean().alias("first_ko_win_rate"),
    ]).collect().row(0, named=True)

    total_matches = status["total_matches"]
    unambiguous = status["unambiguous_matches"]
    win_rate = outcome["first_ko_win_rate"]
    if unambiguous and win_rate is not None:
        denominator = 1 + Z_95**2 / unambiguous
        center = (
            win_rate + Z_95**2 / (2 * unambiguous)
        ) / denominator
        margin = (
            Z_95
            * sqrt(
                win_rate * (1 - win_rate) / unambiguous
                + Z_95**2 / (4 * unambiguous**2)
            )
            / denominator
        )
        interval_low = center - margin
        interval_high = center + margin
    else:
        interval_low = None
        interval_high = None

    return {
        **status,
        "first_ko_wins": outcome["first_ko_wins"],
        "first_ko_win_rate": win_rate,
        "first_ko_win_rate_low": interval_low,
        "first_ko_win_rate_high": interval_high,
        "lift_over_even_pct_points": (
            round((win_rate - 0.5) * 100, 2)
            if win_rate is not None
            else None
        ),
        "coverage_pct": (
            round(unambiguous / total_matches * 100, 2)
            if total_matches
            else 0.0
        ),
    }


def compute_first_ko_by_turn(
    dataset_path: Path | str,
    min_rating: int = 0,
) -> pl.DataFrame:
    """Return first-KO win rate by the turn on which the KO occurred."""
    records = battle_filtered_records(dataset_path, min_rating)
    schema_names = set(records.collect_schema().names())
    if not {"got_first_ko", "first_ko_turn"}.issubset(schema_names):
        return pl.DataFrame({
            "turn_band": [],
            "matches": [],
            "first_ko_wins": [],
            "first_ko_win_rate": [],
        })

    return (
        records.filter(pl.col("got_first_ko"))
        .with_columns(
            pl.when(pl.col("first_ko_turn") <= 5)
            .then(pl.lit("Turns 1–5"))
            .when(pl.col("first_ko_turn") <= 10)
            .then(pl.lit("Turns 6–10"))
            .when(pl.col("first_ko_turn") <= 20)
            .then(pl.lit("Turns 11–20"))
            .otherwise(pl.lit("Turn 21+"))
            .alias("turn_band")
        )
        .group_by("turn_band")
        .agg([
            pl.len().alias("matches"),
            pl.col("won").sum().alias("first_ko_wins"),
            pl.col("won").mean().round(4).alias("first_ko_win_rate"),
        ])
        .with_columns(
            pl.col("turn_band")
            .replace_strict({
                "Turns 1–5": 0,
                "Turns 6–10": 1,
                "Turns 11–20": 2,
                "Turn 21+": 3,
            })
            .alias("sort_order")
        )
        .sort("sort_order")
        .drop("sort_order")
        .collect()
    )


def compute_first_ko_by_rating(
    dataset_path: Path | str,
    min_rating: int = 0,
) -> pl.DataFrame:
    """Return first-KO win rate by ladder-rating band."""
    records = battle_filtered_records(dataset_path, min_rating)
    schema_names = set(records.collect_schema().names())
    if "got_first_ko" not in schema_names:
        return pl.DataFrame(schema={
            "rating_band": pl.String,
            "matches": pl.Int64,
            "first_ko_wins": pl.Int64,
            "first_ko_win_rate": pl.Float64,
        })

    match_ratings = records.group_by("match_id").agg(
        pl.col("rating").mean().alias("match_rating")
    )
    return (
        records.filter(pl.col("got_first_ko"))
        .join(match_ratings, on="match_id", how="inner")
        .with_columns(
            pl.when(pl.col("match_rating") < 1200)
            .then(pl.lit("Below 1200"))
            .when(pl.col("match_rating") < 1400)
            .then(pl.lit("1200–1399"))
            .when(pl.col("match_rating") < 1600)
            .then(pl.lit("1400–1599"))
            .when(pl.col("match_rating") < 1800)
            .then(pl.lit("1600–1799"))
            .otherwise(pl.lit("1800+"))
            .alias("rating_band")
        )
        .group_by("rating_band")
        .agg([
            pl.len().alias("matches"),
            pl.col("won").sum().alias("first_ko_wins"),
            pl.col("won").mean().round(4).alias("first_ko_win_rate"),
        ])
        .with_columns(
            pl.col("rating_band")
            .replace_strict({
                "Below 1200": 0,
                "1200–1399": 1,
                "1400–1599": 2,
                "1600–1799": 3,
                "1800+": 4,
            })
            .alias("sort_order")
        )
        .sort("sort_order")
        .drop("sort_order")
        .collect()
    )


def get_first_ko_matches(
    dataset_path: Path | str,
    min_rating: int = 0,
    limit: int = 50,
) -> pl.DataFrame:
    """Return recent eligible battles with their first-KO outcome."""
    records = battle_filtered_records(dataset_path, min_rating)
    schema_names = set(records.collect_schema().names())
    required = {
        "got_first_ko",
        "first_ko_turn",
        "first_ko_victim",
    }
    if not required.issubset(schema_names):
        return pl.DataFrame(schema={
            "match_id": pl.String,
            "played_at": pl.String,
            "first_ko_player": pl.String,
            "first_ko_won": pl.Boolean,
            "first_ko_turn": pl.Int64,
            "first_ko_victim": pl.String,
            "winner": pl.String,
            "avg_rating": pl.Float64,
            "turns": pl.Int64,
        })

    match_context = records.group_by(["match_id", "uploadtime"]).agg([
        pl.col("player").filter(pl.col("won")).first().alias("winner"),
        pl.col("rating").mean().round(0).alias("avg_rating"),
        pl.col("turns").first().alias("turns"),
    ])
    first_ko = records.filter(pl.col("got_first_ko")).select([
        "match_id",
        pl.col("player").alias("first_ko_player"),
        pl.col("won").alias("first_ko_won"),
        "first_ko_turn",
        "first_ko_victim",
    ])
    return (
        first_ko.join(match_context, on="match_id", how="inner")
        .with_columns(
            pl.from_epoch("uploadtime", time_unit="s")
            .dt.strftime("%Y-%m-%d %H:%M UTC")
            .alias("played_at")
        )
        .sort("uploadtime", descending=True)
        .limit(limit)
        .select([
            "match_id",
            "played_at",
            "first_ko_player",
            "first_ko_won",
            "first_ko_turn",
            "first_ko_victim",
            "winner",
            "avg_rating",
            "turns",
        ])
        .collect()
    )


def compute_pokemon_stats(
    dataset_path: Path | str,
    min_rating: int = 0,
) -> pl.DataFrame:
    records = filtered_records(dataset_path, min_rating)
    team_records = records.select(pl.len()).collect().item()
    if team_records == 0:
        return pl.DataFrame(schema={
            "pokemon": pl.Utf8,
            "appearances": pl.Int64,
            "wins": pl.Int64,
            "usage_rate_pct": pl.Float64,
            "win_rate": pl.Float64,
            "win_rate_low": pl.Float64,
            "win_rate_high": pl.Float64,
            "avg_rating": pl.Float64,
        })

    stats = (
        records.explode("pokemon", empty_as_null=True)
        .with_columns(normalized_pokemon_column().alias("pokemon"))
        .group_by("pokemon")
        .agg([
            pl.len().alias("appearances"),
            pl.col("won").sum().alias("wins"),
            pl.col("rating").mean().alias("avg_rating"),
        ])
        .with_columns([
            (pl.col("appearances") / team_records * 100).alias("usage_rate_pct"),
            (pl.col("wins") / pl.col("appearances")).alias("win_rate"),
        ])
        .with_columns([
            (
                (
                    pl.col("win_rate")
                    + Z_95**2 / (2 * pl.col("appearances"))
                    - Z_95
                    * (
                        (
                            pl.col("win_rate")
                            * (1 - pl.col("win_rate"))
                            / pl.col("appearances")
                            + Z_95**2 / (4 * pl.col("appearances") ** 2)
                        ).sqrt()
                    )
                )
                / (1 + Z_95**2 / pl.col("appearances"))
            ).alias("win_rate_low"),
            (
                (
                    pl.col("win_rate")
                    + Z_95**2 / (2 * pl.col("appearances"))
                    + Z_95
                    * (
                        (
                            pl.col("win_rate")
                            * (1 - pl.col("win_rate"))
                            / pl.col("appearances")
                            + Z_95**2 / (4 * pl.col("appearances") ** 2)
                        ).sqrt()
                    )
                )
                / (1 + Z_95**2 / pl.col("appearances"))
            ).alias("win_rate_high"),
            (pl.col("win_rate") - 0.5).alias("win_rate_delta"),
        ])
        .with_columns([
            pl.col("usage_rate_pct").round(2),
            pl.col("win_rate").round(4),
            pl.col("win_rate_low").round(4),
            pl.col("win_rate_high").round(4),
            pl.col("win_rate_delta").round(4),
            pl.col("avg_rating").round(1),
        ])
        .sort("appearances", descending=True)
        .collect()
    )
    return stats


def compute_key_findings(stats: pl.DataFrame, team_records: int) -> dict:
    if stats.is_empty():
        return {}
    sample_floor = max(25, round(team_records * 0.01))
    common = stats.filter(pl.col("appearances") >= sample_floor)
    if common.is_empty():
        common = stats.head(20)

    most_used = stats.row(0, named=True)
    strongest = common.sort(
        ["win_rate", "appearances"], descending=[True, True]
    ).row(0, named=True)
    most_reliable = common.sort(
        ["win_rate_low", "appearances"], descending=[True, True]
    ).row(0, named=True)
    return {
        "sample_floor": sample_floor,
        "most_used": most_used,
        "strongest_observed": strongest,
        "strongest_lower_bound": most_reliable,
    }


def compute_usage_movers(
    dataset_path: Path | str,
    min_rating: int,
    window_days: int = 7,
) -> tuple[pl.DataFrame, dict]:
    records = filtered_records(dataset_path, min_rating)
    latest_timestamp = records.select(pl.col("uploadtime").max()).collect().item()
    if latest_timestamp is None:
        return pl.DataFrame(), {}

    window_seconds = window_days * 24 * 60 * 60
    recent_start = latest_timestamp - window_seconds
    previous_start = recent_start - window_seconds

    def period_usage(start: int, end: int, prefix: str) -> pl.LazyFrame:
        period = records.filter(
            (pl.col("uploadtime") >= start) & (pl.col("uploadtime") < end)
        )
        denominator = period.select(pl.len()).collect().item()
        if denominator == 0:
            return pl.LazyFrame({
                "pokemon": [],
                f"{prefix}_appearances": [],
                f"{prefix}_usage": [],
            })
        return (
            period.explode("pokemon", empty_as_null=True)
            .with_columns(normalized_pokemon_column().alias("pokemon"))
            .group_by("pokemon")
            .agg(pl.len().alias(f"{prefix}_appearances"))
            .with_columns(
                (
                    pl.col(f"{prefix}_appearances") / denominator * 100
                ).alias(f"{prefix}_usage")
            )
        )

    previous = period_usage(previous_start, recent_start, "previous")
    recent = period_usage(recent_start, latest_timestamp + 1, "recent")
    movers = (
        previous.join(recent, on="pokemon", how="full", coalesce=True)
        .fill_null(0)
        .with_columns(
            (pl.col("recent_usage") - pl.col("previous_usage")).alias(
                "usage_change"
            )
        )
        .with_columns([
            pl.col("previous_usage").round(2),
            pl.col("recent_usage").round(2),
            pl.col("usage_change").round(2),
        ])
        .sort("usage_change", descending=True)
        .collect()
    )
    metadata = {
        "window_days": window_days,
        "previous_start": previous_start,
        "recent_start": recent_start,
        "latest_timestamp": latest_timestamp,
    }
    return movers, metadata


def compute_rating_distribution(
    dataset_path: Path | str,
    min_rating: int,
) -> pl.DataFrame:
    return (
        filtered_records(dataset_path, min_rating)
        .group_by("match_id")
        .agg(pl.col("rating").mean().alias("rating"))
        .with_columns(
            pl.when(pl.col("rating") < 1200)
            .then(pl.lit("Below 1200"))
            .when(pl.col("rating") < 1400)
            .then(pl.lit("1200–1399"))
            .when(pl.col("rating") < 1600)
            .then(pl.lit("1400–1599"))
            .when(pl.col("rating") < 1800)
            .then(pl.lit("1600–1799"))
            .otherwise(pl.lit("1800+"))
            .alias("rating_band")
        )
        .group_by("rating_band")
        .agg(pl.len().alias("matches"))
        .with_columns(
            pl.col("rating_band")
            .replace_strict({
                "Below 1200": 0,
                "1200–1399": 1,
                "1400–1599": 2,
                "1600–1799": 3,
                "1800+": 4,
            })
            .alias("sort_order")
        )
        .sort("sort_order")
        .drop("sort_order")
        .collect()
    )


def compute_turn_distribution(
    dataset_path: Path | str,
    min_rating: int,
) -> pl.DataFrame:
    return (
        filtered_records(dataset_path, min_rating)
        .group_by("match_id")
        .agg(pl.col("turns").first().alias("turns"))
        .with_columns(
            pl.when(pl.col("turns") < 10)
            .then(pl.lit("Under 10"))
            .when(pl.col("turns") < 20)
            .then(pl.lit("10–19"))
            .when(pl.col("turns") < 30)
            .then(pl.lit("20–29"))
            .when(pl.col("turns") < 40)
            .then(pl.lit("30–39"))
            .when(pl.col("turns") < 60)
            .then(pl.lit("40–59"))
            .otherwise(pl.lit("60+"))
            .alias("turn_band")
        )
        .group_by("turn_band")
        .agg(pl.len().alias("matches"))
        .with_columns(
            pl.col("turn_band")
            .replace_strict({
                "Under 10": 0,
                "10–19": 1,
                "20–29": 2,
                "30–39": 3,
                "40–59": 4,
                "60+": 5,
            })
            .alias("sort_order")
        )
        .sort("sort_order")
        .drop("sort_order")
        .collect()
    )


def get_all_pokemon(dataset_path: Path | str) -> list[str]:
    return (
        scan_dataset(dataset_path)
        .explode("pokemon", empty_as_null=True)
        .with_columns(normalized_pokemon_column().alias("pokemon"))
        .select("pokemon")
        .drop_nulls()
        .unique()
        .sort("pokemon")
        .collect()
        .get_column("pokemon")
        .to_list()
    )


def get_pokemon_teammates(
    dataset_path: Path | str,
    pokemon: str,
    min_rating: int,
    limit: int = 20,
) -> pl.DataFrame:
    teams = filtered_records(dataset_path, min_rating).with_columns(
        pl.col("pokemon")
        .list.eval(normalized_pokemon_element())
        .alias("pokemon")
    )
    return (
        teams.filter(pl.col("pokemon").list.contains(pokemon))
        .explode("pokemon", empty_as_null=True)
        .filter(pl.col("pokemon") != pokemon)
        .group_by("pokemon")
        .agg([
            pl.len().alias("shared_teams"),
            pl.col("won").sum().alias("wins"),
        ])
        .with_columns(
            (pl.col("wins") / pl.col("shared_teams")).round(4).alias(
                "team_win_rate"
            )
        )
        .sort("shared_teams", descending=True)
        .limit(limit)
        .collect()
    )


def get_pokemon_trend(
    dataset_path: Path | str,
    pokemon: str,
    min_rating: int,
) -> pl.DataFrame:
    records = filtered_records(dataset_path, min_rating).with_columns([
        pl.from_epoch("uploadtime", time_unit="s").dt.date().alias("date"),
        pl.col("pokemon")
        .list.eval(normalized_pokemon_element())
        .alias("pokemon"),
    ])
    daily_totals = records.group_by("date").agg(pl.len().alias("team_records"))
    appearances = (
        records.filter(pl.col("pokemon").list.contains(pokemon))
        .group_by("date")
        .agg([
            pl.len().alias("appearances"),
            pl.col("won").sum().alias("wins"),
        ])
    )
    return (
        daily_totals.join(appearances, on="date", how="left")
        .fill_null(0)
        .with_columns([
            (pl.col("appearances") / pl.col("team_records") * 100)
            .round(2)
            .alias("usage_rate_pct"),
            pl.when(pl.col("appearances") > 0)
            .then(pl.col("wins") / pl.col("appearances"))
            .otherwise(None)
            .round(4)
            .alias("win_rate"),
        ])
        .sort("date")
        .collect()
    )


def _match_rows(records: pl.LazyFrame, limit: int) -> pl.DataFrame:
    return (
        records.group_by(["match_id", "uploadtime"])
        .agg([
            pl.col("player").filter(pl.col("won")).first().alias("winner"),
            pl.col("player").filter(~pl.col("won")).first().alias("loser"),
            pl.col("rating").mean().round(0).alias("avg_rating"),
            pl.col("turns").first().alias("turns"),
        ])
        .with_columns(
            pl.from_epoch("uploadtime", time_unit="s")
            .dt.strftime("%Y-%m-%d %H:%M UTC")
            .alias("played_at")
        )
        .sort("uploadtime", descending=True)
        .limit(limit)
        .select(["match_id", "played_at", "winner", "loser", "avg_rating", "turns"])
        .collect()
    )


def get_pokemon_matches(
    dataset_path: Path | str,
    pokemon: str,
    min_rating: int,
    limit: int = 50,
) -> pl.DataFrame:
    records = filtered_records(dataset_path, min_rating).with_columns(
        pl.col("pokemon")
        .list.eval(normalized_pokemon_element())
        .alias("pokemon")
    )
    match_ids = (
        records.filter(pl.col("pokemon").list.contains(pokemon))
        .select("match_id")
        .unique()
    )
    return _match_rows(records.join(match_ids, on="match_id", how="inner"), limit)


def get_recent_matches(
    dataset_path: Path | str,
    min_rating: int,
    player_query: str = "",
    limit: int = 50,
) -> pl.DataFrame:
    records = filtered_records(dataset_path, min_rating)
    if player_query:
        match_ids = (
            records.filter(
                pl.col("player")
                .str.to_lowercase()
                .str.contains(player_query.lower(), literal=True)
            )
            .select("match_id")
            .unique()
        )
        records = records.join(match_ids, on="match_id", how="inner")
    return _match_rows(records, limit)


def get_match_details(dataset_path: Path | str, match_id: str) -> list[dict]:
    return (
        scan_dataset(dataset_path)
        .filter(pl.col("match_id") == match_id)
        .with_columns(
            pl.col("pokemon")
            .list.eval(normalized_pokemon_element())
            .alias("pokemon")
        )
        .collect()
        .to_dicts()
    )


def get_player_leaderboard(
    dataset_path: Path | str,
    min_rating: int,
    minimum_matches: int = 5,
    limit: int = 100,
) -> pl.DataFrame:
    return (
        filtered_records(dataset_path, min_rating)
        .group_by("player")
        .agg([
            pl.len().alias("matches"),
            pl.col("won").sum().alias("wins"),
            pl.col("rating").mean().alias("avg_rating"),
            pl.col("uploadtime").max().alias("last_played"),
        ])
        .filter(pl.col("matches") >= minimum_matches)
        .with_columns([
            (pl.col("wins") / pl.col("matches")).round(4).alias("win_rate"),
            pl.col("avg_rating").round(1),
            pl.from_epoch("last_played", time_unit="s")
            .dt.strftime("%Y-%m-%d")
            .alias("last_played_date"),
        ])
        .sort(["wins", "matches"], descending=[True, True])
        .limit(limit)
        .collect()
    )


def get_player_profile(
    dataset_path: Path | str,
    player: str,
    min_rating: int,
) -> tuple[dict, pl.DataFrame, pl.DataFrame]:
    player_records = filtered_records(dataset_path, min_rating).filter(
        pl.col("player").str.to_lowercase() == player.lower()
    )
    summary_frame = (
        player_records.select([
            pl.len().alias("matches"),
            pl.col("won").sum().alias("wins"),
            pl.col("rating").mean().alias("avg_rating"),
            pl.col("rating").max().alias("peak_rating"),
        ])
        .collect()
    )
    summary = summary_frame.row(0, named=True)
    summary["win_rate"] = (
        summary["wins"] / summary["matches"] if summary["matches"] else 0
    )
    pokemon = (
        player_records.explode("pokemon", empty_as_null=True)
        .with_columns(normalized_pokemon_column().alias("pokemon"))
        .group_by("pokemon")
        .agg([
            pl.len().alias("appearances"),
            pl.col("won").sum().alias("wins"),
        ])
        .with_columns(
            (pl.col("wins") / pl.col("appearances")).round(4).alias("win_rate")
        )
        .sort("appearances", descending=True)
        .collect()
    )
    matches = _match_rows(player_records, 100)
    return summary, pokemon, matches


def pokemon_profile_url(tier: str, min_rating: int, pokemon: str) -> str:
    return (
        f"?page=pokemon&tier={quote_plus(tier)}&rating={min_rating}"
        f"&pokemon={quote_plus(pokemon)}"
    )


def player_profile_url(tier: str, min_rating: int, player: str) -> str:
    return (
        f"?page=player&tier={quote_plus(tier)}&rating={min_rating}"
        f"&player={quote_plus(player)}"
    )


def match_profile_url(tier: str, min_rating: int, match_id: str) -> str:
    return (
        f"?page=match&tier={quote_plus(tier)}&rating={min_rating}"
        f"&match={quote_plus(match_id)}"
    )
