"""Vega-Lite chart specifications used across dashboard pages."""

from __future__ import annotations

import polars as pl
import streamlit as st


def first_ko_rate_chart(
    frame: pl.DataFrame,
    category: str,
    category_title: str,
) -> None:
    """Plot first-KO win rates with an even-chance reference line."""
    spec = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "data": {"values": frame.to_dicts()},
        "height": 330,
        "layer": [
            {
                "mark": {
                    "type": "bar",
                    "cornerRadiusTopLeft": 6,
                    "cornerRadiusTopRight": 6,
                    "color": "#6941c6",
                },
                "encoding": {
                    "x": {
                        "field": category,
                        "type": "nominal",
                        "title": category_title,
                        "sort": None,
                    },
                    "y": {
                        "field": "first_ko_win_rate",
                        "type": "quantitative",
                        "title": "First-KO side win rate",
                        "axis": {"format": ".0%"},
                        "scale": {"domain": [0, 1]},
                    },
                    "tooltip": [
                        {"field": category, "type": "nominal", "title": category_title},
                        {
                            "field": "first_ko_win_rate",
                            "type": "quantitative",
                            "title": "Win rate",
                            "format": ".1%",
                        },
                        {"field": "matches", "type": "quantitative", "title": "Matches"},
                    ],
                },
            },
            {
                "mark": {
                    "type": "rule",
                    "strokeDash": [6, 5],
                    "strokeWidth": 2,
                    "color": "#0e9384",
                },
                "encoding": {"y": {"datum": 0.5}},
            },
        ],
        "config": {"view": {"stroke": None}},
    }
    st.vega_lite_chart(spec=spec, width="stretch", theme=None)


def usage_bar_chart(stats: pl.DataFrame) -> None:
    top_usage = stats.head(18)
    spec = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "data": {
            "values": top_usage.select([
                "pokemon", "usage_rate_pct", "appearances", "win_rate"
            ]).to_dicts()
        },
        "height": 500,
        "mark": {"type": "bar", "cornerRadiusEnd": 5},
        "encoding": {
            "y": {
                "field": "pokemon",
                "type": "nominal",
                "sort": "-x",
                "title": None,
            },
            "x": {
                "field": "usage_rate_pct",
                "type": "quantitative",
                "title": "Share of teams (%)",
            },
            "color": {
                "field": "win_rate",
                "type": "quantitative",
                "title": "Win rate",
                "scale": {"scheme": "purplebluegreen", "domain": [0.35, 0.65]},
            },
            "tooltip": [
                {"field": "pokemon", "type": "nominal", "title": "Pokémon"},
                {
                    "field": "usage_rate_pct",
                    "type": "quantitative",
                    "title": "Usage",
                    "format": ".1f",
                },
                {
                    "field": "win_rate",
                    "type": "quantitative",
                    "title": "Win rate",
                    "format": ".1%",
                },
                {"field": "appearances", "type": "quantitative", "title": "Teams"},
            ],
        },
        "config": {"view": {"stroke": None}},
    }
    st.vega_lite_chart(spec=spec, width="stretch", theme=None)


def usage_win_scatter(
    stats: pl.DataFrame,
    minimum_appearances: int = 10,
) -> None:
    chart_data = stats.filter(pl.col("appearances") >= minimum_appearances)
    spec = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "data": {
            "values": chart_data.select([
                "pokemon",
                "usage_rate_pct",
                "win_rate",
                "appearances",
                "win_rate_low",
                "avg_rating",
            ]).to_dicts()
        },
        "height": 500,
        "layer": [
            {
                "mark": {"type": "rule", "strokeDash": [5, 5], "color": "#98a2b3"},
                "encoding": {"y": {"datum": 0.5}},
            },
            {
                "mark": {
                    "type": "circle",
                    "opacity": 0.76,
                    "stroke": "white",
                    "strokeWidth": 1,
                },
                "encoding": {
                    "x": {
                        "field": "usage_rate_pct",
                        "type": "quantitative",
                        "title": "Share of teams (%)",
                    },
                    "y": {
                        "field": "win_rate",
                        "type": "quantitative",
                        "title": "Observed win rate",
                        "axis": {"format": ".0%"},
                        "scale": {"domain": [0.2, 0.8]},
                    },
                    "size": {
                        "field": "appearances",
                        "type": "quantitative",
                        "title": "Teams",
                        "scale": {"range": [35, 850]},
                    },
                    "color": {
                        "field": "win_rate_low",
                        "type": "quantitative",
                        "title": "95% lower bound",
                        "scale": {"scheme": "viridis"},
                    },
                    "tooltip": [
                        {"field": "pokemon", "type": "nominal", "title": "Pokémon"},
                        {
                            "field": "usage_rate_pct",
                            "type": "quantitative",
                            "title": "Usage",
                            "format": ".1f",
                        },
                        {
                            "field": "win_rate",
                            "type": "quantitative",
                            "title": "Win rate",
                            "format": ".1%",
                        },
                        {
                            "field": "win_rate_low",
                            "type": "quantitative",
                            "title": "95% low",
                            "format": ".1%",
                        },
                        {"field": "appearances", "type": "quantitative", "title": "Teams"},
                    ],
                },
            },
        ],
        "config": {"view": {"stroke": None}},
    }
    st.vega_lite_chart(spec=spec, width="stretch", theme=None)


def simple_bar_chart(
    frame: pl.DataFrame,
    category: str,
    value: str,
    title: str,
    color: str,
) -> None:
    spec = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "data": {"values": frame.to_dicts()},
        "height": 300,
        "mark": {
            "type": "bar",
            "cornerRadiusTopLeft": 4,
            "cornerRadiusTopRight": 4,
        },
        "encoding": {
            "x": {"field": category, "type": "nominal", "title": None},
            "y": {"field": value, "type": "quantitative", "title": title},
            "color": {"value": color},
            "tooltip": [
                {"field": category, "type": "nominal", "title": "Group"},
                {"field": value, "type": "quantitative", "title": title},
            ],
        },
        "config": {"view": {"stroke": None}},
    }
    st.vega_lite_chart(spec=spec, width="stretch", theme=None)


def pokemon_trend_chart(trend: pl.DataFrame) -> None:
    spec = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "data": {"values": trend.to_dicts()},
        "height": 340,
        "mark": {"type": "line", "point": True, "strokeWidth": 3},
        "encoding": {
            "x": {"field": "date", "type": "temporal", "title": None},
            "y": {
                "field": "usage_rate_pct",
                "type": "quantitative",
                "title": "Share of teams (%)",
            },
            "color": {"value": "#6941c6"},
            "tooltip": [
                {"field": "date", "type": "temporal", "title": "Date"},
                {
                    "field": "usage_rate_pct",
                    "type": "quantitative",
                    "title": "Usage",
                    "format": ".1f",
                },
                {"field": "appearances", "type": "quantitative", "title": "Teams"},
                {
                    "field": "win_rate",
                    "type": "quantitative",
                    "title": "Win rate",
                    "format": ".1%",
                },
            ],
        },
        "config": {"view": {"stroke": None}},
    }
    st.vega_lite_chart(spec=spec, width="stretch", theme=None)
