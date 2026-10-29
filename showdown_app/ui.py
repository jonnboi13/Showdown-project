"""Reusable Streamlit presentation components."""

from __future__ import annotations

from datetime import UTC, datetime
from html import escape
from pathlib import Path

import polars as pl
import streamlit as st

from showdown_app.analytics import (
    match_profile_url,
    player_profile_url,
    pokemon_profile_url,
)
from showdown_app.config import TierConfig
from showdown_app.data_source import TierDataset


def apply_theme() -> None:
    st.markdown(
        """
        <style>
          :root {
            --ink: #101828;
            --muted: #667085;
            --line: #e4e7ec;
            --violet: #6941c6;
            --violet-dark: #42307d;
            --cyan: #0e9384;
            --surface: rgba(255, 255, 255, 0.94);
          }
          .stApp {
            background:
              radial-gradient(circle at 86% 3%, rgba(127, 86, 217, .12), transparent 26rem),
              radial-gradient(circle at 18% 82%, rgba(14, 147, 132, .08), transparent 30rem),
              #f8fafc;
          }
          .block-container {
            max-width: 1480px;
            padding-top: 1.2rem;
            padding-bottom: 4rem;
          }
          [data-testid="stSidebar"] {
            background: rgba(255, 255, 255, .96);
            border-right: 1px solid var(--line);
          }
          .hero {
            position: relative;
            overflow: hidden;
            color: #fff;
            background:
              linear-gradient(118deg, rgba(16, 24, 40, .98), rgba(66, 48, 125, .96) 58%, rgba(105, 65, 198, .94));
            border: 1px solid rgba(255, 255, 255, .12);
            border-radius: 1.4rem;
            padding: clamp(1.6rem, 4vw, 3rem);
            margin-bottom: 1.25rem;
            box-shadow: 0 28px 70px rgba(66, 48, 125, .2);
          }
          .hero::after {
            content: "";
            position: absolute;
            width: 18rem;
            height: 18rem;
            right: -5rem;
            top: -7rem;
            border-radius: 50%;
            border: 3.2rem solid rgba(255, 255, 255, .06);
          }
          .hero h1 {
            color: #fff;
            font-size: clamp(2.15rem, 5vw, 4.3rem);
            line-height: .98;
            letter-spacing: -.055em;
            max-width: 860px;
            margin: .45rem 0 .9rem;
          }
          .hero p {
            color: #e9d7fe;
            font-size: 1.08rem;
            line-height: 1.7;
            max-width: 780px;
            margin: 0;
          }
          .eyebrow {
            color: #d6bbfb;
            font-size: .76rem;
            font-weight: 750;
            letter-spacing: .15em;
            text-transform: uppercase;
          }
          .context-strip {
            display: flex;
            flex-wrap: wrap;
            gap: .65rem;
            margin-top: 1.2rem;
          }
          .context-chip {
            color: #fff;
            background: rgba(255, 255, 255, .1);
            border: 1px solid rgba(255, 255, 255, .18);
            border-radius: 999px;
            padding: .42rem .72rem;
            font-size: .82rem;
          }
          div[data-testid="stMetric"] {
            background: var(--surface);
            border: 1px solid var(--line);
            border-radius: 1rem;
            padding: 1rem 1.1rem;
            box-shadow: 0 8px 24px rgba(16, 24, 40, .045);
          }
          div[data-testid="stMetricLabel"] { color: var(--muted); }
          div[data-testid="stMetricValue"] { color: var(--ink); }
          .insight-card {
            display: block;
            min-height: 11rem;
            color: var(--ink) !important;
            text-decoration: none !important;
            background: var(--surface);
            border: 1px solid var(--line);
            border-radius: 1rem;
            padding: 1.15rem;
            box-shadow: 0 8px 24px rgba(16, 24, 40, .045);
            transition: transform .16s ease, box-shadow .16s ease, border-color .16s ease;
          }
          .insight-card:hover {
            transform: translateY(-2px);
            border-color: #b692f6;
            box-shadow: 0 15px 32px rgba(66, 48, 125, .11);
          }
          .insight-label {
            color: var(--violet);
            font-size: .72rem;
            font-weight: 750;
            letter-spacing: .11em;
            text-transform: uppercase;
          }
          .insight-title {
            font-size: 1.38rem;
            font-weight: 720;
            letter-spacing: -.025em;
            margin: .55rem 0 .35rem;
          }
          .insight-copy { color: var(--muted); line-height: 1.52; }
          .insight-link { color: var(--violet); font-weight: 650; margin-top: .7rem; }
          .section-intro {
            color: var(--muted);
            max-width: 850px;
            font-size: 1.02rem;
            line-height: 1.65;
            margin-top: -.45rem;
            margin-bottom: 1.2rem;
          }
          .plain-callout {
            background: #f4f3ff;
            border-left: 4px solid var(--violet);
            border-radius: .25rem .85rem .85rem .25rem;
            padding: 1rem 1.1rem;
            color: #3e1c96;
            line-height: 1.55;
            margin: .8rem 0 1.2rem;
          }
          .source-badge {
            display: inline-flex;
            align-items: center;
            gap: .45rem;
            color: #067647;
            background: #ecfdf3;
            border: 1px solid #abefc6;
            border-radius: 999px;
            padding: .4rem .7rem;
            font-size: .8rem;
            font-weight: 650;
          }
          .team-card {
            background: #fff;
            border: 1px solid var(--line);
            border-radius: 1rem;
            padding: 1rem 1.15rem;
          }
          .team-card.winner { border-top: 4px solid #12b76a; }
          .team-card.runner-up { border-top: 4px solid #f79009; }
          .nav-note { color: var(--muted); font-size: .82rem; line-height: 1.5; }
          hr { border-color: var(--line); }
          @media (max-width: 760px) {
            .hero { padding: 1.45rem; }
            .block-container { padding-top: .7rem; }
            .insight-card { min-height: auto; }
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def format_utc_timestamp(timestamp: int | None, date_only: bool = True) -> str:
    if not timestamp:
        return "Unknown"
    date = datetime.fromtimestamp(timestamp, tz=UTC)
    return date.strftime("%b %-d, %Y" if date_only else "%b %-d, %Y %H:%M UTC")


def render_hero(
    tier: TierConfig,
    min_rating: int,
    summary: dict,
) -> None:
    first_date = format_utc_timestamp(summary.get("first_upload"))
    last_date = format_utc_timestamp(summary.get("last_upload"))
    st.markdown(
        f"""
        <div class="hero">
          <div class="eyebrow">Senior project · competitive game analytics</div>
          <h1>Pokémon Showdown Meta Lab</h1>
          <p>
            A data exploration of how people build teams and win battles in
            {escape(tier.label)}. No Pokémon knowledge required: every metric is
            defined where it appears.
          </p>
          <div class="context-strip">
            <span class="context-chip">{summary['total_matches']:,} battles</span>
            <span class="context-chip">Rating {min_rating:,}+</span>
            <span class="context-chip">{escape(first_date)} – {escape(last_date)}</span>
            <span class="context-chip">{escape(tier.plain_name)}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_intro(text: str) -> None:
    st.markdown(
        f'<p class="section-intro">{escape(text)}</p>',
        unsafe_allow_html=True,
    )


def render_plain_callout(text: str) -> None:
    st.markdown(
        f'<div class="plain-callout"><strong>In plain English:</strong> {escape(text)}</div>',
        unsafe_allow_html=True,
    )


def render_insight_card(
    label: str,
    title: str,
    copy: str,
    url: str,
    link_text: str = "Explore the evidence →",
) -> None:
    st.markdown(
        f"""
        <a class="insight-card" href="{escape(url, quote=True)}" target="_self">
          <div class="insight-label">{escape(label)}</div>
          <div class="insight-title">{escape(title)}</div>
          <div class="insight-copy">{escape(copy)}</div>
          <div class="insight-link">{escape(link_text)}</div>
        </a>
        """,
        unsafe_allow_html=True,
    )


def render_source_badge(dataset: TierDataset) -> None:
    source_label = "validated temporary cache" if dataset.cache_hit else "fresh download"
    integrity_note = (
        "complete manifest match"
        if dataset.integrity_gap == 0
        else f"{abs(dataset.integrity_gap)}-battle manifest gap disclosed"
    )
    st.markdown(
        f"""
        <a class="source-badge" href="{escape(dataset.release_url, quote=True)}" target="_blank">
          ● GitHub release verified · {escape(source_label)} · {escape(integrity_note)} ↗
        </a>
        """,
        unsafe_allow_html=True,
    )


def pokemon_table(
    stats: pl.DataFrame,
    tier: str,
    min_rating: int,
    key: str,
) -> None:
    display = stats.with_columns(
        pl.col("pokemon")
        .map_elements(
            lambda name: pokemon_profile_url(tier, min_rating, name),
            return_dtype=pl.Utf8,
        )
        .alias("profile")
    ).select([
        pl.col("profile").alias("Profile"),
        pl.col("pokemon").alias("Pokémon"),
        pl.col("appearances").alias("Teams"),
        pl.col("usage_rate_pct").alias("Usage"),
        (pl.col("win_rate") * 100).round(1).alias("Win rate"),
        (pl.col("win_rate_low") * 100).round(1).alias("95% low"),
        (pl.col("win_rate_high") * 100).round(1).alias("95% high"),
        pl.col("avg_rating").alias("Avg. rating"),
    ])
    st.dataframe(
        display,
        width="stretch",
        hide_index=True,
        key=key,
        column_config={
            "Profile": st.column_config.LinkColumn(
                "Open",
                display_text="View →",
                help="Open the connected Pokémon profile.",
            ),
            "Usage": st.column_config.NumberColumn(format="%.1f%%"),
            "Win rate": st.column_config.NumberColumn(format="%.1f%%"),
            "95% low": st.column_config.NumberColumn(format="%.1f%%"),
            "95% high": st.column_config.NumberColumn(format="%.1f%%"),
            "Avg. rating": st.column_config.NumberColumn(format="%.0f"),
        },
    )


def matches_table(
    matches: pl.DataFrame,
    tier: str,
    min_rating: int,
    key: str,
) -> None:
    display = matches.with_columns([
        pl.col("match_id")
        .map_elements(
            lambda match_id: match_profile_url(tier, min_rating, match_id),
            return_dtype=pl.Utf8,
        )
        .alias("details"),
        pl.col("winner")
        .map_elements(
            lambda player: player_profile_url(tier, min_rating, player),
            return_dtype=pl.Utf8,
        )
        .alias("winner_profile"),
        pl.col("loser")
        .map_elements(
            lambda player: player_profile_url(tier, min_rating, player),
            return_dtype=pl.Utf8,
        )
        .alias("loser_profile"),
    ]).select([
        pl.col("details").alias("Battle"),
        pl.col("played_at").alias("Played"),
        pl.col("winner_profile").alias("Winner profile"),
        pl.col("winner").alias("Winner"),
        pl.col("loser_profile").alias("Loser profile"),
        pl.col("loser").alias("Loser"),
        pl.col("avg_rating").alias("Avg. rating"),
        pl.col("turns").alias("Turns"),
    ])
    st.dataframe(
        display,
        width="stretch",
        hide_index=True,
        key=key,
        column_config={
            "Battle": st.column_config.LinkColumn("Battle", display_text="Open →"),
            "Winner profile": st.column_config.LinkColumn(
                "Winner", display_text="Profile ↗"
            ),
            "Loser profile": st.column_config.LinkColumn(
                "Loser", display_text="Profile ↗"
            ),
            "Avg. rating": st.column_config.NumberColumn(format="%.0f"),
        },
    )


def render_team_card(
    record: dict,
    role: str,
    tier: str,
    min_rating: int,
) -> None:
    player = record.get("player", "Unknown")
    player_url = player_profile_url(tier, min_rating, player)
    css_role = "winner" if role == "Winner" else "runner-up"
    pokemon_links = "".join(
        (
            f'<li><a href="{escape(pokemon_profile_url(tier, min_rating, pokemon), quote=True)}" '
            f'target="_self">{escape(pokemon)}</a></li>'
        )
        for pokemon in record.get("pokemon", [])
    )
    st.markdown(
        f"""
        <div class="team-card {css_role}">
          <div class="insight-label">{escape(role)}</div>
          <div class="insight-title">
            <a href="{escape(player_url, quote=True)}" target="_self">{escape(player)}</a>
          </div>
          <div class="insight-copy">Rating: {record.get('rating') or 'not recorded'}</div>
          <ul>{pokemon_links}</ul>
        </div>
        """,
        unsafe_allow_html=True,
    )
