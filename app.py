"""Streamlit entry point for Pokémon Showdown Meta Lab."""

from __future__ import annotations

import streamlit as st

from showdown_app.config import DEFAULT_MIN_RATING, DEFAULT_TIER, TIERS
from showdown_app.data_source import DatasetSourceError
from showdown_app.pages import (
    render_battles,
    render_first_ko_analysis,
    render_methodology,
    render_overview,
    render_players,
    render_pokemon_explorer,
)
from showdown_app.services import (
    cached_pokemon_stats,
    cached_summary,
    load_remote_dataset,
)
from showdown_app.ui import apply_theme, render_hero, render_source_badge


PAGES = {
    "overview": "Overview",
    "first-ko": "First KO study",
    "pokemon": "Pokémon",
    "players": "Players",
    "battles": "Battles",
    "methodology": "About the data",
}
DETAIL_TO_PARENT = {"player": "players", "match": "battles"}


st.set_page_config(
    page_title="Pokémon Showdown Meta Lab",
    page_icon="⚔️",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_theme()


def query_value(name: str, default: str) -> str:
    value = st.query_params.get(name, default)
    return value[0] if isinstance(value, list) else value


def replace_query(page: str, tier: str, rating: int) -> None:
    st.query_params.clear()
    st.query_params.update(page=page, tier=tier, rating=str(rating))
    st.rerun()


def read_route() -> tuple[str, str, int]:
    page = query_value("page", "overview")
    if page not in {*PAGES, *DETAIL_TO_PARENT}:
        page = "overview"
    tier = query_value("tier", DEFAULT_TIER)
    if tier not in TIERS:
        tier = DEFAULT_TIER
    try:
        rating = int(query_value("rating", str(DEFAULT_MIN_RATING)))
    except ValueError:
        rating = DEFAULT_MIN_RATING
    return page, tier, max(0, min(2000, rating))


def render_sidebar(page: str, tier: str, min_rating: int) -> None:
    parent_page = DETAIL_TO_PARENT.get(page, page)
    with st.sidebar:
        st.markdown("## ⚔️ Meta Lab")
        st.caption("A connected exploration of public competitive-battle data.")
        st.divider()

        nav_labels = list(PAGES.values())
        selected_label = st.radio(
            "Explore",
            nav_labels,
            index=nav_labels.index(PAGES[parent_page]),
        )
        selected_page = next(
            slug for slug, label in PAGES.items() if label == selected_label
        )
        if selected_page != parent_page:
            replace_query(selected_page, tier, min_rating)

        st.divider()
        tier_labels = [config.label for config in TIERS.values()]
        selected_tier_label = st.selectbox(
            "Format",
            tier_labels,
            index=tier_labels.index(TIERS[tier].label),
        )
        selected_tier = next(
            slug
            for slug, config in TIERS.items()
            if config.label == selected_tier_label
        )
        if selected_tier != tier:
            replace_query(parent_page, selected_tier, min_rating)

        selected_rating = st.slider(
            "Minimum ladder rating",
            min_value=0,
            max_value=2000,
            value=min_rating,
            step=50,
            help="Higher values focus the analysis on more highly rated players.",
        )
        if selected_rating != min_rating:
            replace_query(parent_page, tier, selected_rating)

        st.divider()
        if st.button("Refresh from GitHub", width="stretch"):
            st.cache_resource.clear()
            st.cache_data.clear()
            st.rerun()
        st.markdown(
            '<p class="nav-note">GitHub Release assets are the source of truth. '
            "The app validates them before using its temporary performance cache.</p>",
            unsafe_allow_html=True,
        )


page, tier, min_rating = read_route()
render_sidebar(page, tier, min_rating)

try:
    with st.spinner("Checking the current GitHub release and preparing the dataset…"):
        dataset = load_remote_dataset(tier)
except (DatasetSourceError, OSError, ValueError) as exc:
    st.error("The current GitHub dataset could not be prepared.")
    with st.expander("Technical detail"):
        st.code(str(exc))
    st.stop()
except Exception as exc:
    st.error("GitHub could not be reached or returned an unexpected response.")
    with st.expander("Technical detail"):
        st.code(str(exc))
    st.stop()

dataset_path = str(dataset.dataset_path)
summary = cached_summary(dataset_path, min_rating)
if not summary["total_matches"]:
    st.warning("No battles match this rating threshold. Try lowering the filter.")
    st.stop()
stats = cached_pokemon_stats(dataset_path, min_rating)

render_hero(TIERS[tier], min_rating, summary)
metric_1, metric_2, metric_3, metric_4 = st.columns(4)
metric_1.metric("Battles analyzed", f"{summary['total_matches']:,}")
metric_2.metric("Public accounts", f"{summary['unique_players']:,}")
metric_3.metric("Average rating", f"{summary['avg_rating']:,.0f}")
metric_4.metric("Median battle length", f"{summary['median_turns']:,.0f} turns")
st.markdown(TIERS[tier].explanation)
render_source_badge(dataset)
st.divider()

if page == "overview":
    render_overview(dataset, tier, min_rating, summary, stats)
elif page == "first-ko":
    render_first_ko_analysis(dataset, tier, min_rating)
elif page == "pokemon":
    render_pokemon_explorer(
        dataset,
        tier,
        min_rating,
        stats,
        requested_pokemon=query_value("pokemon", ""),
    )
elif page in {"players", "player"}:
    render_players(
        dataset,
        tier,
        min_rating,
        requested_player=query_value("player", ""),
    )
elif page in {"battles", "match"}:
    render_battles(
        dataset,
        tier,
        min_rating,
        requested_match=query_value("match", ""),
    )
elif page == "methodology":
    render_methodology(dataset, tier, min_rating, summary)
