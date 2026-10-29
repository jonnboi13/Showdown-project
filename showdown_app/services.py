"""Streamlit-cached access to remote data and analytical queries."""

from __future__ import annotations

import polars as pl
import streamlit as st

from showdown_app.analytics import (
    compute_first_ko_by_rating,
    compute_first_ko_by_turn,
    compute_first_ko_summary,
    compute_meta_summary,
    compute_pokemon_stats,
    compute_rating_distribution,
    compute_turn_distribution,
    compute_usage_movers,
    get_all_pokemon,
    get_first_ko_matches,
    get_player_leaderboard,
    get_player_profile,
    get_pokemon_matches,
    get_pokemon_teammates,
    get_pokemon_trend,
    get_recent_matches,
)
from showdown_app.data_source import TierDataset, ensure_tier_dataset


@st.cache_resource(show_spinner=False, ttl=300)
def load_remote_dataset(tier: str) -> TierDataset:
    return ensure_tier_dataset(tier)


@st.cache_data(show_spinner=False, ttl=1800)
def cached_summary(dataset_path: str, minimum_rating: int) -> dict:
    return compute_meta_summary(dataset_path, minimum_rating)


@st.cache_data(show_spinner=False, ttl=1200)
def cached_first_ko_summary(dataset_path: str, minimum_rating: int) -> dict:
    return compute_first_ko_summary(dataset_path, minimum_rating)


@st.cache_data(show_spinner=False, ttl=1200)
def cached_first_ko_by_turn(
    dataset_path: str,
    minimum_rating: int,
) -> pl.DataFrame:
    return compute_first_ko_by_turn(dataset_path, minimum_rating)


@st.cache_data(show_spinner=False, ttl=1200)
def cached_first_ko_by_rating(
    dataset_path: str,
    minimum_rating: int,
) -> pl.DataFrame:
    return compute_first_ko_by_rating(dataset_path, minimum_rating)


@st.cache_data(show_spinner=False, ttl=900)
def cached_first_ko_matches(
    dataset_path: str,
    minimum_rating: int,
    limit: int,
) -> pl.DataFrame:
    return get_first_ko_matches(dataset_path, minimum_rating, limit=limit)


@st.cache_data(show_spinner=False, ttl=1800)
def cached_pokemon_stats(dataset_path: str, minimum_rating: int) -> pl.DataFrame:
    return compute_pokemon_stats(dataset_path, minimum_rating)


@st.cache_data(show_spinner=False, ttl=1800)
def cached_usage_movers(
    dataset_path: str,
    minimum_rating: int,
) -> tuple[pl.DataFrame, dict]:
    return compute_usage_movers(dataset_path, minimum_rating)


@st.cache_data(show_spinner=False, ttl=1800)
def cached_rating_distribution(
    dataset_path: str,
    minimum_rating: int,
) -> pl.DataFrame:
    return compute_rating_distribution(dataset_path, minimum_rating)


@st.cache_data(show_spinner=False, ttl=1800)
def cached_turn_distribution(
    dataset_path: str,
    minimum_rating: int,
) -> pl.DataFrame:
    return compute_turn_distribution(dataset_path, minimum_rating)


@st.cache_data(show_spinner=False, ttl=1800)
def cached_pokemon_names(dataset_path: str) -> list[str]:
    return get_all_pokemon(dataset_path)


@st.cache_data(show_spinner=False, ttl=1200)
def cached_pokemon_trend(
    dataset_path: str,
    pokemon: str,
    minimum_rating: int,
) -> pl.DataFrame:
    return get_pokemon_trend(dataset_path, pokemon, minimum_rating)


@st.cache_data(show_spinner=False, ttl=1200)
def cached_pokemon_teammates(
    dataset_path: str,
    pokemon: str,
    minimum_rating: int,
) -> pl.DataFrame:
    return get_pokemon_teammates(dataset_path, pokemon, minimum_rating)


@st.cache_data(show_spinner=False, ttl=1200)
def cached_pokemon_matches(
    dataset_path: str,
    pokemon: str,
    minimum_rating: int,
) -> pl.DataFrame:
    return get_pokemon_matches(dataset_path, pokemon, minimum_rating)


@st.cache_data(show_spinner=False, ttl=1200)
def cached_player_leaderboard(
    dataset_path: str,
    minimum_rating: int,
    minimum_matches: int,
) -> pl.DataFrame:
    return get_player_leaderboard(
        dataset_path,
        minimum_rating,
        minimum_matches=minimum_matches,
    )


@st.cache_data(show_spinner=False, ttl=1200)
def cached_player_profile(
    dataset_path: str,
    player: str,
    minimum_rating: int,
) -> tuple[dict, pl.DataFrame, pl.DataFrame]:
    return get_player_profile(dataset_path, player, minimum_rating)


@st.cache_data(show_spinner=False, ttl=900)
def cached_recent_matches(
    dataset_path: str,
    minimum_rating: int,
    player_query: str,
    limit: int,
) -> pl.DataFrame:
    return get_recent_matches(
        dataset_path,
        minimum_rating,
        player_query=player_query,
        limit=limit,
    )
