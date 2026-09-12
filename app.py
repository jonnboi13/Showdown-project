import streamlit as st
import polars as pl
from src.analytics import (
    get_tier_lazyframe, 
    compute_pokemon_stats, 
    compute_meta_summary, 
    get_match_details,
    get_filtered_matches
)
from src.data_loader import ensure_data_ledgers_and_parquets

ensure_data_ledgers_and_parquets()

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
summary = compute_meta_summary(lf, min_rating=min_rating)

if summary['total_player_records'] == 0:
    st.warning("No matches found matching the selected minimum rating filter.")
    st.stop()

col1, col2, col3 = st.columns(3)
col1.metric("Total Player Records", f"{summary['total_player_records']:,}")
col2.metric("Average Turns", f"{summary['avg_turns']:.1f}")
col3.metric("Average Ladder Rating", f"{summary['avg_rating']:.1f}")

st.divider()

# 2. Main Pokémon Statistics Table
st.subheader("Tier Usage & Win Rates")
df_stats = compute_pokemon_stats(lf, min_rating=min_rating)

# Add a search filter input for Pokémon names
search_query = st.text_input("Filter Pokémon in table:", "", placeholder="Type a Pokémon name...")

if search_query:
    # Filter stats dataframe based on text input (case-insensitive)
    filtered_stats = df_stats.filter(
        pl.col("pokemon").str.to_lowercase().str.contains(search_query.lower())
    )
else:
    filtered_stats = df_stats

st.dataframe(
    filtered_stats,
    use_container_width=True,
    hide_index=True
)
st.divider()

# 3. Hidden Gems Finder
st.subheader("💎 Hidden Gems Finder")
st.markdown("Discover niche Pokémon with high win rates but low overall usage/pick rates.")

col_gem1, col_gem2, col_gem3 = st.columns(3)
with col_gem1:
    max_usage = st.slider("Max Usage Rate (%)", min_value=1.0, max_value=20.0, value=5.0, step=0.5)
with col_gem2:
    min_win_rate = st.slider("Min Win Rate", min_value=0.5, max_value=0.9, value=0.55, step=0.01)
with col_gem3:
    min_appearances = st.number_input("Min Appearances", min_value=1, max_value=50, value=5, step=1)

hidden_gems_df = df_stats.filter(
    (pl.col("usage_rate_pct") <= max_usage) &
    (pl.col("win_rate") >= min_win_rate) &
    (pl.col("appearances") >= min_appearances)
).sort("win_rate", descending=True)

if hidden_gems_df.is_empty():
    st.info("No Pokémon match these specific hidden gem criteria. Try relaxing the filters.")
else:
    st.dataframe(
        hidden_gems_df,
        use_container_width=True,
        hide_index=True
    )

st.divider()

# 4. Pokémon Match Lookup
st.subheader("🔍 Pokémon Match Lookup")
st.markdown("Select a specific Pokémon to inspect all recorded matches featuring it.")

all_pokemon = (
    lf.explode("pokemon")
      .with_columns(pl.col("pokemon").str.replace(r"(,\s+[MF]|\-\*)$", "").alias("pokemon"))
      .select("pokemon")
      .unique()
      .sort("pokemon")
      .collect()
      .get_column("pokemon")
      .to_list()
)

selected_pokemon = st.selectbox("Choose a Pokémon:", all_pokemon if all_pokemon else ["None"])

if selected_pokemon and selected_pokemon != "None":
    matching_match_ids = (
        lf.with_columns(
            pl.col("pokemon").list.eval(pl.element().str.replace(r"(,\s+[MF]|\-\*)$", ""))
        )
        .filter(pl.col("pokemon").list.contains(selected_pokemon))
        .filter(pl.col("rating") >= min_rating)
        .select("match_id")
        .unique()
    )
    
    poke_matches_lf = lf.join(matching_match_ids, on="match_id", how="inner")
    
    poke_match_df = (
        poke_matches_lf.group_by(["match_id", "uploadtime"])
        .agg([
            pl.col("player").filter(pl.col("won") == True).first().alias("winner"),
            pl.col("player").filter(pl.col("won") == False).first().alias("loser"),
            pl.col("rating").mean().alias("avg_rating"),
            pl.col("turns").first().alias("turns")
        ])
        .sort("uploadtime", descending=True)
        .limit(50)
        .collect()
    )
    
    if poke_match_df.is_empty():
        st.info(f"No matches found featuring {selected_pokemon} at the current rating threshold.")
    else:
        st.markdown(f"Showing recent matches featuring **{selected_pokemon}** (up to 50):")
        selected_poke_row = st.dataframe(
            poke_match_df,
            use_container_width=True,
            hide_index=True,
            selection_mode="single-row",
            on_select="rerun",
            key="poke_match_selector"
        )
        
        poke_rows = selected_poke_row.get("selection", {}).get("rows", [])
        if poke_rows:
            r_idx = poke_rows[0]
            chosen_poke_match_id = poke_match_df["match_id"][r_idx]
            st.markdown(f"### ⚔️ Match Summary: `{chosen_poke_match_id}`")
            replay_url = f"https://replay.pokemonshowdown.com/{chosen_poke_match_id}"
            st.markdown(f"[🎥 Watch Full Replay on Pokémon Showdown]({replay_url})")
            
            try:
                match_records = get_match_details(tier, chosen_poke_match_id)
                if len(match_records) == 2:
                    p1, p2 = match_records[0], match_records[1]
                    winner_rec = p1 if p1["won"] else p2
                    loser_rec = p2 if p1["won"] else p1
                    
                    m_col1, m_col2, m_col3 = st.columns(3)
                    m_col1.metric("Format", winner_rec.get("format", "Gen 9 OU"))
                    m_col2.metric("Total Turns", winner_rec.get("turns", "N/A"))
                    m_col3.metric("Ladder Rating", f"{winner_rec.get('rating', 0):.0f}")
                    
                    st.divider()
                    
                    col_win, col_loss = st.columns(2)
                    with col_win:
                        st.success(f"🏆 **Winner:** {winner_rec['player']}")
                        st.markdown("**Team Roster:**")
                        for pkm in winner_rec.get("pokemon", []):
                            st.markdown(f"- {pkm}")
                            
                    with col_loss:
                        st.error(f"❌ **Loser:** {loser_rec['player']}")
                        st.markdown("**Team Roster:**")
                        for pkm in loser_rec.get("pokemon", []):
                            st.markdown(f"- {pkm}")
                else:
                    st.json(match_records)
            except (KeyError, FileNotFoundError) as e:
                st.warning(str(e))

st.divider()

# 5. General Match Inspector & Explorer
st.subheader("Match Inspector & Game Browser")

col_search1, col_search2 = st.columns(2)
with col_search1:
    player_filter = st.text_input("Search by Player Name:", "")
with col_search2:
    match_min_rating = st.number_input("Minimum Match Rating:", min_value=0, max_value=2000, value=1500, step=50)

match_df = get_filtered_matches(lf, player_query=player_filter, min_rating=match_min_rating)

if match_df.is_empty():
    st.info("No matches found matching your search criteria.")
else:
    st.markdown("Select a row below to inspect match details (sorted by most recent upload time):")
    
    selected_match_row = st.dataframe(
        match_df,
        use_container_width=True,
        hide_index=True,
        selection_mode="single-row",
        on_select="rerun"
    )
    
    selected_rows = selected_match_row.get("selection", {}).get("rows", [])
    
    if selected_rows:
        row_idx = selected_rows[0]
        chosen_match_id = match_df["match_id"][row_idx]
        
        st.markdown(f"### ⚔️ Match Summary: `{chosen_match_id}`")
        replay_url = f"https://replay.pokemonshowdown.com/{chosen_match_id}"
        st.markdown(f"[🎥 Watch Full Replay on Pokémon Showdown]({replay_url})")
        
        try:
            match_records = get_match_details(tier, chosen_match_id)
            if len(match_records) == 2:
                p1, p2 = match_records[0], match_records[1]
                winner_rec = p1 if p1["won"] else p2
                loser_rec = p2 if p1["won"] else p1
                
                m_col1, m_col2, m_col3 = st.columns(3)
                m_col1.metric("Format", winner_rec.get("format", "Gen 9 OU"))
                m_col2.metric("Total Turns", winner_rec.get("turns", "N/A"))
                m_col3.metric("Ladder Rating", f"{winner_rec.get('rating', 0):.0f}")
                
                st.divider()
                
                col_win, col_loss = st.columns(2)
                with col_win:
                    st.success(f"🏆 **Winner:** {winner_rec['player']}")
                    st.markdown("**Team Roster:**")
                    for pkm in winner_rec.get("pokemon", []):
                        st.markdown(f"- {pkm}")
                        
                with col_loss:
                    st.error(f"❌ **Loser:** {loser_rec['player']}")
                    st.markdown("**Team Roster:**")
                    for pkm in loser_rec.get("pokemon", []):
                        st.markdown(f"- {pkm}")
            else:
                st.json(match_records)
        except (KeyError, FileNotFoundError) as e:
            st.warning(str(e))