"""Versioned data contract shared by ingestion and analysis."""

from __future__ import annotations

import polars as pl


RECORD_SCHEMA_VERSION = 2

TEAM_RECORD_SCHEMA: dict[str, pl.DataType] = {
    "schema_version": pl.Int16,
    "match_id": pl.String,
    "format": pl.String,
    "rating": pl.Int32,
    "player": pl.String,
    "won": pl.Boolean,
    "turns": pl.Int64,
    "pokemon": pl.List(pl.String),
    "uploadtime": pl.Int64,
    "first_ko_turn": pl.Int64,
    "first_ko_player": pl.String,
    "first_ko_victim": pl.String,
    "first_ko_tied": pl.Boolean,
    "got_first_ko": pl.Boolean,
    "total_faints": pl.Int64,
}


def coerce_team_records(frame: pl.DataFrame) -> pl.DataFrame:
    """Return records in the current column order and physical types.

    Missing first-KO columns remain null for legacy rows. That distinction is
    important: null means "not parsed yet," while a version-2 row with
    ``total_faints == 0`` means the replay was parsed and contained no faint.
    """
    expressions: list[pl.Expr] = []
    for column, dtype in TEAM_RECORD_SCHEMA.items():
        if column not in frame.columns:
            default = 1 if column == "schema_version" else None
            expressions.append(pl.lit(default, dtype=dtype).alias(column))

    if expressions:
        frame = frame.with_columns(expressions)

    return frame.select([
        pl.col(column).cast(dtype, strict=False)
        for column, dtype in TEAM_RECORD_SCHEMA.items()
    ])
