import streamlit as st
import polars as pl
from src.analytics import (
    get_tier_lazyframe, 
    compute_pokemon_stats, 
    compute_meta_summary, 
    get_match_details
)
from src.data_loader import ensure_data_loaded

# Ensure remote assets are present before rendering UI
ensure_data_loaded()

st.set_page_config(page_title="Showdown Analytics", layout="wide")

st.title("Pokémon Showdown Meta Dashboard")

# Sidebar controls
tier = st.sidebar.selectbox("Select Format Tier", ["gen9ou", "gen9uu", "gen9ubers"])
min_rating = st.sidebar.slider("Minimum Rating Filter", min_value=0, max_value=2000, value=1500, step=50)

# Load data lazily based on tier
try:
    lf = get_tier_lazyframe(tier)
except FileNotFoundError:
    st.error(f"No data manifest found for tier: {tier}")
    st.stop()

# 1. High-Level Meta Summary
summary = compute_meta_summary(lf)
col1, col2, col3 = st.columns(3)
col1.metric("Total Player Records", f"{summary['total_player_records']:,}")
col2.metric("Average Turns", f"{summary['avg_turns']:.1f}")
col3.metric("Average Ladder Rating", f"{summary['avg_rating']:.1f}")

st.divider()

# 2. Main Pokémon Statistics Table
st.subheader("Tier Usage & Win Rates")
df_stats = compute_pokemon_stats(lf, min_rating=min_rating)

st.dataframe(
    df_stats,
    use_container_width=True,
    hide_index=True
)

st.divider()

# 3. Match Inspector Drill-Down
st.subheader("Match Inspector")
match_id_input = st.text_input("Enter Match ID for detailed breakdown:")

if match_id_input:
    try:
        match_records = get_match_details(tier, match_id_input)
        st.json(match_records)
    except (KeyError, FileNotFoundError) as e:
        st.warning(str(e))