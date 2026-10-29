"""Page-level composition for the linked Streamlit dashboard."""

from __future__ import annotations

from urllib.parse import quote_plus

import polars as pl
import streamlit as st

from showdown_app.analytics import (
    compute_key_findings,
    get_match_details,
    match_profile_url,
    player_profile_url,
    pokemon_profile_url,
)
from showdown_app.charts import (
    first_ko_rate_chart,
    pokemon_trend_chart,
    simple_bar_chart,
    usage_bar_chart,
    usage_win_scatter,
)
from showdown_app.config import RELEASE_REPOSITORY, TIERS
from showdown_app.data_source import TierDataset
from showdown_app.services import (
    cached_first_ko_by_rating,
    cached_first_ko_by_turn,
    cached_first_ko_matches,
    cached_first_ko_summary,
    cached_player_leaderboard,
    cached_player_profile,
    cached_pokemon_matches,
    cached_pokemon_names,
    cached_pokemon_teammates,
    cached_pokemon_trend,
    cached_rating_distribution,
    cached_recent_matches,
    cached_turn_distribution,
    cached_usage_movers,
)
from showdown_app.ui import (
    matches_table,
    pokemon_table,
    render_insight_card,
    render_plain_callout,
    render_section_intro,
    render_source_badge,
    render_team_card,
)


def render_overview(
    dataset: TierDataset,
    tier: str,
    min_rating: int,
    summary: dict,
    stats: pl.DataFrame,
) -> None:
    findings = compute_key_findings(stats, summary["team_records"])
    most_used = findings["most_used"]
    strongest = findings["strongest_observed"]
    reliable = findings["strongest_lower_bound"]

    st.markdown("## What the data says")
    render_section_intro(
        "These are computed findings from the selected replay sample—not placeholder "
        "cards. Follow any card into the underlying Pokémon profile, teammates, and battles."
    )

    finding_1, finding_2, finding_3 = st.columns(3)
    with finding_1:
        render_insight_card(
            "Most common choice",
            most_used["pokemon"],
            (
                f"Appeared on {most_used['appearances']:,} teams, or "
                f"{most_used['usage_rate_pct']:.1f}% of this sample."
            ),
            pokemon_profile_url(tier, min_rating, most_used["pokemon"]),
        )
    with finding_2:
        render_insight_card(
            "Best observed result",
            strongest["pokemon"],
            (
                f"Won {strongest['win_rate']:.1%} of {strongest['appearances']:,} "
                f"appearances among Pokémon with at least {findings['sample_floor']:,} teams."
            ),
            pokemon_profile_url(tier, min_rating, strongest["pokemon"]),
        )
    with finding_3:
        render_insight_card(
            "Strongest uncertainty-adjusted result",
            reliable["pokemon"],
            (
                f"Its 95% interval starts at {reliable['win_rate_low']:.1%}; observed "
                f"win rate was {reliable['win_rate']:.1%} across "
                f"{reliable['appearances']:,} teams."
            ),
            pokemon_profile_url(tier, min_rating, reliable["pokemon"]),
        )

    ko_summary = cached_first_ko_summary(str(dataset.dataset_path), min_rating)
    st.markdown("## Active research question")
    research_card, research_status = st.columns([1.35, 1])
    with research_card:
        if ko_summary["unambiguous_matches"]:
            research_copy = (
                f"The side credited with the first KO won "
                f"{ko_summary['first_ko_win_rate']:.1%} of "
                f"{ko_summary['unambiguous_matches']:,} eligible battles."
            )
        else:
            research_copy = (
                "The analysis is defined and tested; historical replays are now "
                "being enriched with event-level KO data."
            )
        render_insight_card(
            "First KO study",
            "Does taking the first knockout predict winning?",
            research_copy,
            f"?page=first-ko&tier={tier}&rating={min_rating}",
            "Open the study →",
        )
    with research_status:
        total_matches = ko_summary["total_matches"]
        enriched = ko_summary["enriched_matches"]
        enrichment_share = enriched / total_matches if total_matches else 0
        st.markdown("### Research data readiness")
        st.progress(enrichment_share)
        st.caption(
            f"{enriched:,} of {total_matches:,} filtered battles have the "
            "event-level fields needed for this question."
        )
        st.markdown(
            "The study page reports exclusions and uncertainty instead of treating "
            "missing or ambiguous battles as losses."
        )

    st.markdown("## Team-building patterns")
    render_plain_callout(
        "Usage answers ‘how often was this Pokémon chosen?’ Win rate answers ‘how "
        "often did teams containing it win?’ A popular choice is not automatically a "
        "strong one, and a rare choice can look extreme because of a small sample."
    )
    usage_col, win_col = st.columns([1, 1.15])
    with usage_col:
        st.markdown("### The most common choices")
        usage_bar_chart(stats)
    with win_col:
        st.markdown("### Popularity versus outcomes")
        usage_win_scatter(stats, findings["sample_floor"])
        st.caption(
            f"Showing Pokémon that appeared on at least "
            f"{findings['sample_floor']:,} teams (1% of this sample)."
        )

    movers, _ = cached_usage_movers(str(dataset.dataset_path), min_rating)
    stable_movers = movers.filter(
        (pl.col("recent_appearances") >= 10)
        & (pl.col("previous_appearances") >= 10)
    )
    if not stable_movers.is_empty():
        st.markdown("## What changed in the latest week")
        render_section_intro(
            "This compares each Pokémon’s share of teams in the latest seven-day "
            "window with the seven days immediately before it."
        )
        gainers = stable_movers.head(8)
        decliners = stable_movers.sort("usage_change").head(8)
        change_left, change_right = st.columns(2)
        with change_left:
            st.markdown("### Largest gains")
            _render_mover_table(gainers)
        with change_right:
            st.markdown("### Largest declines")
            _render_mover_table(decliners)

    st.markdown("## Who and what is represented")
    distribution_left, distribution_right = st.columns(2)
    with distribution_left:
        st.markdown("### Matches by rating band")
        simple_bar_chart(
            cached_rating_distribution(str(dataset.dataset_path), min_rating),
            "rating_band",
            "matches",
            "Battles",
            "#6941c6",
        )
    with distribution_right:
        st.markdown("### Matches by length")
        simple_bar_chart(
            cached_turn_distribution(str(dataset.dataset_path), min_rating),
            "turn_band",
            "matches",
            "Battles",
            "#0e9384",
        )

    st.markdown("### Explore all Pokémon")
    pokemon_table(stats.head(30), tier, min_rating, "overview_pokemon_table")


def _render_mover_table(frame: pl.DataFrame) -> None:
    st.dataframe(
        frame.select([
            pl.col("pokemon").alias("Pokémon"),
            pl.col("previous_usage").alias("Previous"),
            pl.col("recent_usage").alias("Latest"),
            pl.col("usage_change").alias("Change"),
        ]),
        width="stretch",
        hide_index=True,
        column_config={
            "Previous": st.column_config.NumberColumn(format="%.1f%%"),
            "Latest": st.column_config.NumberColumn(format="%.1f%%"),
            "Change": st.column_config.NumberColumn(format="%+.1f pts"),
        },
    )


def render_pokemon_explorer(
    dataset: TierDataset,
    tier: str,
    min_rating: int,
    stats: pl.DataFrame,
    requested_pokemon: str = "",
) -> None:
    if requested_pokemon:
        render_pokemon_profile(dataset, tier, min_rating, stats, requested_pokemon)
        return

    st.markdown("## Pokémon explorer")
    render_section_intro(
        "A Pokémon is one selectable team member. Compare how often each one appears, "
        "its observed outcomes, and the uncertainty around those outcomes."
    )
    render_plain_callout(
        "The 95% interval is deliberately shown beside win rate. Wide intervals mean "
        "the estimate is still uncertain, usually because there are few appearances."
    )

    filter_left, filter_middle, filter_right = st.columns([2, 1, 1])
    with filter_left:
        search = st.text_input("Search Pokémon", placeholder="Start typing a name")
    with filter_middle:
        minimum_appearances = st.number_input(
            "Minimum teams",
            min_value=1,
            max_value=max(1, int(stats.get_column("appearances").max())),
            value=10,
        )
    with filter_right:
        sort_choice = st.selectbox(
            "Sort by",
            ["Most used", "Highest win rate", "Strongest 95% low"],
        )

    filtered = stats.filter(pl.col("appearances") >= minimum_appearances)
    if search.strip():
        filtered = filtered.filter(
            pl.col("pokemon")
            .str.to_lowercase()
            .str.contains(search.strip().lower(), literal=True)
        )
    if sort_choice == "Highest win rate":
        filtered = filtered.sort("win_rate", descending=True)
    elif sort_choice == "Strongest 95% low":
        filtered = filtered.sort("win_rate_low", descending=True)

    pokemon_table(filtered, tier, min_rating, "pokemon_explorer_table")
    st.caption("Use the Open column to move from comparison to a connected profile.")
    st.markdown("## Outcome map")
    usage_win_scatter(filtered, minimum_appearances)


def render_pokemon_profile(
    dataset: TierDataset,
    tier: str,
    min_rating: int,
    stats: pl.DataFrame,
    requested_pokemon: str,
) -> None:
    names = cached_pokemon_names(str(dataset.dataset_path))
    name_lookup = {name.lower(): name for name in names}
    selected = name_lookup.get(requested_pokemon.lower())
    if not selected:
        st.warning(f"No Pokémon named {requested_pokemon!r} was found in this tier.")
        st.markdown(
            f"[Return to the Pokémon explorer](?page=pokemon&tier={tier}&rating={min_rating})"
        )
        return

    row = stats.filter(pl.col("pokemon") == selected)
    st.markdown(f"[← All Pokémon](?page=pokemon&tier={tier}&rating={min_rating})")
    st.markdown(f"## {selected}")
    render_section_intro(
        "This profile connects aggregate results to daily trends, common teammates, "
        "and the individual battles behind the numbers."
    )

    if row.is_empty():
        st.info("This Pokémon has no appearances at the selected rating threshold.")
        return
    record = row.row(0, named=True)
    profile_1, profile_2, profile_3, profile_4 = st.columns(4)
    profile_1.metric("Teams", f"{record['appearances']:,}")
    profile_2.metric("Usage", f"{record['usage_rate_pct']:.1f}%")
    profile_3.metric("Observed win rate", f"{record['win_rate']:.1%}")
    profile_4.metric(
        "95% interval",
        f"{record['win_rate_low']:.1%}–{record['win_rate_high']:.1%}",
    )

    trend = cached_pokemon_trend(str(dataset.dataset_path), selected, min_rating)
    st.markdown("### Usage over time")
    pokemon_trend_chart(trend)

    teammate_col, context_col = st.columns([1.35, 1])
    teammates = cached_pokemon_teammates(
        str(dataset.dataset_path), selected, min_rating
    )
    with teammate_col:
        st.markdown("### Most common teammates")
        if teammates.is_empty():
            st.info("No teammate data is available.")
        else:
            _render_teammates(teammates, tier, min_rating)
    with context_col:
        st.markdown("### How to interpret this")
        render_plain_callout(
            "A teammate appearing often shows a common pairing, not proof that one "
            "caused the other to win. Strong players, team archetypes, and matchups "
            "can influence both selection and results."
        )

    st.markdown("### Battles containing this Pokémon")
    pokemon_matches = cached_pokemon_matches(
        str(dataset.dataset_path), selected, min_rating
    )
    matches_table(
        pokemon_matches,
        tier,
        min_rating,
        f"pokemon_matches_{tier}_{selected}",
    )


def _render_teammates(teammates: pl.DataFrame, tier: str, min_rating: int) -> None:
    display = teammates.with_columns(
        pl.col("pokemon")
        .map_elements(
            lambda name: pokemon_profile_url(tier, min_rating, name),
            return_dtype=pl.Utf8,
        )
        .alias("profile")
    ).select([
        pl.col("profile").alias("Profile"),
        pl.col("pokemon").alias("Pokémon"),
        pl.col("shared_teams").alias("Shared teams"),
        (pl.col("team_win_rate") * 100).round(1).alias("Team win rate"),
    ])
    st.dataframe(
        display,
        width="stretch",
        hide_index=True,
        column_config={
            "Profile": st.column_config.LinkColumn("Open", display_text="View →"),
            "Team win rate": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )


def render_players(
    dataset: TierDataset,
    tier: str,
    min_rating: int,
    requested_player: str = "",
) -> None:
    if requested_player:
        render_player_profile(dataset, tier, min_rating, requested_player)
        return

    st.markdown("## Player explorer")
    render_section_intro(
        "Compare activity and outcomes for public replay accounts, then follow a "
        "player into their Pokémon choices and battle history."
    )
    render_plain_callout(
        "A leaderboard based on public replays is not a complete ranking. It only "
        "describes matches present in this dataset and above your rating filter."
    )

    filter_1, filter_2 = st.columns([1, 2])
    with filter_1:
        minimum_matches = st.slider(
            "Minimum matches in sample", min_value=2, max_value=50, value=10
        )
    with filter_2:
        player_search = st.text_input(
            "Filter player names", placeholder="Search a public replay account"
        )

    leaderboard = cached_player_leaderboard(
        str(dataset.dataset_path), min_rating, minimum_matches
    )
    if player_search.strip():
        leaderboard = leaderboard.filter(
            pl.col("player")
            .str.to_lowercase()
            .str.contains(player_search.strip().lower(), literal=True)
        )

    if leaderboard.is_empty():
        st.info("No players match those filters.")
        return

    best_by_wins = leaderboard.row(0, named=True)
    best_rate = leaderboard.sort(
        ["win_rate", "matches"], descending=[True, True]
    ).row(0, named=True)
    leader_1, leader_2 = st.columns(2)
    with leader_1:
        render_insight_card(
            "Most wins in sample",
            best_by_wins["player"],
            (
                f"{best_by_wins['wins']:,} wins across "
                f"{best_by_wins['matches']:,} recorded battles."
            ),
            player_profile_url(tier, min_rating, best_by_wins["player"]),
        )
    with leader_2:
        render_insight_card(
            "Highest observed rate",
            best_rate["player"],
            f"{best_rate['win_rate']:.1%} across {best_rate['matches']:,} recorded battles.",
            player_profile_url(tier, min_rating, best_rate["player"]),
        )

    _render_player_table(leaderboard, tier, min_rating)


def _render_player_table(
    leaderboard: pl.DataFrame,
    tier: str,
    min_rating: int,
) -> None:
    display = leaderboard.with_columns(
        pl.col("player")
        .map_elements(
            lambda player: player_profile_url(tier, min_rating, player),
            return_dtype=pl.Utf8,
        )
        .alias("profile")
    ).select([
        pl.col("profile").alias("Profile"),
        pl.col("player").alias("Player"),
        pl.col("matches").alias("Battles"),
        pl.col("wins").alias("Wins"),
        (pl.col("win_rate") * 100).round(1).alias("Win rate"),
        pl.col("avg_rating").alias("Avg. rating"),
        pl.col("last_played_date").alias("Last seen"),
    ])
    st.dataframe(
        display,
        width="stretch",
        hide_index=True,
        column_config={
            "Profile": st.column_config.LinkColumn("Open", display_text="View →"),
            "Win rate": st.column_config.NumberColumn(format="%.1f%%"),
            "Avg. rating": st.column_config.NumberColumn(format="%.0f"),
        },
    )


def render_player_profile(
    dataset: TierDataset,
    tier: str,
    min_rating: int,
    player: str,
) -> None:
    summary, pokemon, matches = cached_player_profile(
        str(dataset.dataset_path), player, min_rating
    )
    st.markdown(f"[← Player explorer](?page=players&tier={tier}&rating={min_rating})")
    st.markdown(f"## Player: {player}")
    render_section_intro(
        "This profile connects one public replay account to its recorded results, "
        "most-used Pokémon, and individual battles."
    )
    if not summary["matches"]:
        st.warning("No matches were found for this player at the current threshold.")
        return

    metric_1, metric_2, metric_3, metric_4 = st.columns(4)
    metric_1.metric("Battles", f"{summary['matches']:,}")
    metric_2.metric("Wins", f"{summary['wins']:,}")
    metric_3.metric("Observed win rate", f"{summary['win_rate']:.1%}")
    metric_4.metric("Peak recorded rating", f"{summary['peak_rating']:,.0f}")

    st.markdown("### Most-used Pokémon")
    favorite_display = pokemon.head(20).with_columns(
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
        pl.col("wins").alias("Wins"),
        (pl.col("win_rate") * 100).round(1).alias("Win rate"),
    ])
    st.dataframe(
        favorite_display,
        width="stretch",
        hide_index=True,
        column_config={
            "Profile": st.column_config.LinkColumn("Open", display_text="View →"),
            "Win rate": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )

    st.markdown("### Recorded battles")
    matches_table(matches, tier, min_rating, f"player_matches_{quote_plus(player)}")


def render_battles(
    dataset: TierDataset,
    tier: str,
    min_rating: int,
    requested_match: str = "",
) -> None:
    if requested_match:
        render_match_profile(dataset, tier, min_rating, requested_match)
        return

    st.markdown("## Battle explorer")
    render_section_intro(
        "Every aggregate result comes from individual public replays. Search the "
        "sample, open a battle, and follow either player or any team member."
    )
    filter_1, filter_2 = st.columns([2, 1])
    with filter_1:
        player_query = st.text_input(
            "Player name", placeholder="Leave blank for the latest battles"
        )
    with filter_2:
        limit = st.selectbox("Battles to show", [25, 50, 100], index=1)

    matches = cached_recent_matches(
        str(dataset.dataset_path), min_rating, player_query.strip(), limit
    )
    if matches.is_empty():
        st.info("No battles match that search.")
    else:
        matches_table(matches, tier, min_rating, "battle_explorer_table")


def render_first_ko_analysis(
    dataset: TierDataset,
    tier: str,
    min_rating: int,
) -> None:
    """Render the research question even before enrichment is complete."""
    dataset_path = str(dataset.dataset_path)
    summary = cached_first_ko_summary(dataset_path, min_rating)
    total_matches = summary["total_matches"]
    enriched_matches = summary["enriched_matches"]
    eligible_matches = summary["unambiguous_matches"]
    enrichment_share = enriched_matches / total_matches if total_matches else 0
    analytic_share = eligible_matches / total_matches if total_matches else 0

    st.markdown("## Does getting the first KO predict the winner?")
    render_section_intro(
        "This study tests whether the player whose opponent loses the first Pokémon "
        "is more likely to win the battle. It is an association study, not proof that "
        "the first knockout caused the result."
    )
    render_plain_callout(
        "A knockout (KO) occurs when a Pokémon faints. The first-KO side is the one "
        "whose opponent alone has a Pokémon faint on the first turn containing any faint. "
        "The rating filter uses the average recorded player rating so neither side is dropped."
    )

    metric_1, metric_2, metric_3, metric_4 = st.columns(4)
    metric_1.metric("Filtered battles", f"{total_matches:,}")
    metric_2.metric("Event-level coverage", f"{enrichment_share:.1%}")
    metric_3.metric("Eligible battles", f"{eligible_matches:,}")
    metric_4.metric(
        "First-KO side win rate",
        (
            f"{summary['first_ko_win_rate']:.1%}"
            if summary["first_ko_win_rate"] is not None
            else "Waiting for data"
        ),
    )

    readiness_left, readiness_right = st.columns(2)
    with readiness_left:
        st.markdown("### Historical enrichment")
        st.progress(enrichment_share)
        st.caption(
            f"{enriched_matches:,} of {total_matches:,} battles have schema-v2 "
            "event fields."
        )
    with readiness_right:
        st.markdown("### Analysis coverage")
        st.progress(analytic_share)
        st.caption(
            f"{eligible_matches:,} of {total_matches:,} battles currently have one "
            "unambiguous first-KO side."
        )

    if not eligible_matches:
        st.info(
            "No eligible first-KO battles are present in the current GitHub release "
            "for these filters yet. This is a data-readiness result—not evidence for "
            "or against the hypothesis. The page will populate as the release pipeline "
            "enriches historical replay batches."
        )
    else:
        rate = summary["first_ko_win_rate"]
        interval_low = summary["first_ko_win_rate_low"]
        interval_high = summary["first_ko_win_rate_high"]
        if interval_low > 0.5:
            direction = (
                "The interval is entirely above 50%, so this sample shows a positive "
                "association between taking the first KO and winning."
            )
        elif interval_high < 0.5:
            direction = (
                "The interval is entirely below 50%, so this sample does not show the "
                "expected positive association."
            )
        else:
            direction = (
                "The interval includes 50%, so this sample does not yet separate the "
                "observed rate from an even split with 95% confidence."
            )
        sample_note = (
            " The eligible sample is still small, so treat this as an early estimate."
            if eligible_matches < 30
            else ""
        )
        st.markdown("### Current result")
        st.success(
            f"The first-KO side won {summary['first_ko_wins']:,} of "
            f"{eligible_matches:,} eligible battles ({rate:.1%}). The Wilson 95% "
            f"interval is {interval_low:.1%}–{interval_high:.1%}. {direction}{sample_note}"
        )

        by_turn = cached_first_ko_by_turn(dataset_path, min_rating)
        by_rating = cached_first_ko_by_rating(dataset_path, min_rating)
        if not by_turn.is_empty() or not by_rating.is_empty():
            st.markdown("## Where the relationship changes")
            render_section_intro(
                "Breaking the result down helps test whether an early advantage behaves "
                "differently in short versus long battles or across skill levels. Small "
                "groups can move sharply, so each bar includes its match count on hover."
            )
            chart_left, chart_right = st.columns(2)
            with chart_left:
                st.markdown("### By first-KO timing")
                if by_turn.is_empty():
                    st.info("No timing groups are available yet.")
                else:
                    first_ko_rate_chart(by_turn, "turn_band", "First-KO turn")
            with chart_right:
                st.markdown("### By ladder rating")
                if by_rating.is_empty():
                    st.info("No rating groups are available yet.")
                else:
                    first_ko_rate_chart(by_rating, "rating_band", "Average battle rating")

    st.markdown("## What enters the calculation")
    inclusion_left, exclusion_right = st.columns(2)
    with inclusion_left:
        st.markdown("### Included")
        st.markdown(
            "- One battle contributes one outcome.\n"
            "- Exactly one side is credited on the first turn containing a faint.\n"
            "- The credited side’s final win/loss result becomes the study outcome."
        )
    with exclusion_right:
        st.markdown("### Excluded from the main rate")
        st.markdown(
            f"- **{summary['tied_matches']:,}** same-turn double-KO battles.\n"
            f"- **{summary['no_ko_matches']:,}** completed battles with no parsed KO.\n"
            f"- **{total_matches - enriched_matches:,}** legacy battles awaiting enrichment."
        )

    if eligible_matches:
        evidence = cached_first_ko_matches(dataset_path, min_rating, 50)
        if not evidence.is_empty():
            st.markdown("## Battles behind the result")
            render_section_intro(
                "These are the latest eligible source battles. Open a battle to inspect "
                "both teams, or open the credited player’s profile to explore their sample."
            )
            _render_first_ko_evidence(evidence, tier, min_rating)

    st.markdown("## Interpretation guardrails")
    render_plain_callout(
        "A higher win rate would show that first KO is a useful signal in this replay "
        "sample. It would not prove causation: player skill, matchup, team strength, "
        "sacrifices, recoil, and replay-selection behavior can affect both first KO "
        "and victory."
    )
    with st.expander("Research roadmap"):
        st.markdown(
            "1. Complete schema-v2 enrichment and report coverage by format.\n"
            "2. Compare the overall rate with timing and rating subgroups.\n"
            "3. Add controls for rating difference, battle length, and team composition.\n"
            "4. Test robustness across formats and future game generations."
        )


def _render_first_ko_evidence(
    evidence: pl.DataFrame,
    tier: str,
    min_rating: int,
) -> None:
    display = evidence.with_columns([
        pl.col("match_id")
        .map_elements(
            lambda match_id: match_profile_url(tier, min_rating, match_id),
            return_dtype=pl.Utf8,
        )
        .alias("battle_link"),
        pl.col("first_ko_player")
        .map_elements(
            lambda player: player_profile_url(tier, min_rating, player),
            return_dtype=pl.Utf8,
        )
        .alias("player_link"),
        pl.when(pl.col("first_ko_won"))
        .then(pl.lit("Won"))
        .otherwise(pl.lit("Lost"))
        .alias("outcome"),
    ]).select([
        pl.col("battle_link").alias("Battle"),
        pl.col("played_at").alias("Played"),
        pl.col("player_link").alias("Player profile"),
        pl.col("first_ko_player").alias("First-KO player"),
        pl.col("outcome").alias("Result"),
        pl.col("first_ko_turn").alias("KO turn"),
        pl.col("first_ko_victim").alias("First faint"),
        pl.col("avg_rating").alias("Avg. rating"),
        pl.col("turns").alias("Battle turns"),
    ])
    st.dataframe(
        display,
        width="stretch",
        hide_index=True,
        column_config={
            "Battle": st.column_config.LinkColumn("Battle", display_text="Open →"),
            "Player profile": st.column_config.LinkColumn(
                "Profile", display_text="View →"
            ),
            "Avg. rating": st.column_config.NumberColumn(format="%.0f"),
        },
    )


def render_match_profile(
    dataset: TierDataset,
    tier: str,
    min_rating: int,
    match_id: str,
) -> None:
    records = get_match_details(dataset.dataset_path, match_id)
    st.markdown(f"[← Battle explorer](?page=battles&tier={tier}&rating={min_rating})")
    st.markdown(f"## Battle: `{match_id}`")
    if len(records) != 2:
        st.warning("This battle was not found in the current GitHub-backed dataset.")
        return

    winner = next((record for record in records if record.get("won")), records[0])
    loser = next((record for record in records if not record.get("won")), records[1])
    ratings = [record["rating"] for record in records if record.get("rating")]
    average_rating = sum(ratings) / len(ratings) if ratings else 0
    replay_url = f"https://replay.pokemonshowdown.com/{match_id}"

    schema_version = max(record.get("schema_version") or 1 for record in records)
    if schema_version < 2:
        first_ko_status = "Awaiting enrichment"
    elif any(record.get("first_ko_tied") for record in records):
        first_ko_status = "Same-turn tie"
    elif max(record.get("total_faints") or 0 for record in records) == 0:
        first_ko_status = "No KO recorded"
    else:
        first_ko_turn = next(
            (
                record.get("first_ko_turn")
                for record in records
                if record.get("first_ko_turn")
            ),
            None,
        )
        first_ko_status = f"Turn {first_ko_turn}" if first_ko_turn else "Unavailable"

    metric_1, metric_2, metric_3, metric_4 = st.columns(4)
    metric_1.metric("Turns", winner.get("turns", "—"))
    metric_2.metric(
        "Average rating", f"{average_rating:,.0f}" if average_rating else "—"
    )
    metric_3.metric("Format", TIERS[tier].label)
    metric_4.metric("First KO", first_ko_status)
    st.link_button("Watch the original replay ↗", replay_url, type="primary")

    credited = next(
        (record for record in records if record.get("got_first_ko") is True),
        None,
    )
    if credited:
        outcome = "won" if credited.get("won") else "lost"
        victim = credited.get("first_ko_victim") or "an opposing Pokémon"
        credited_player_url = player_profile_url(
            tier, min_rating, credited["player"]
        )
        victim_url = pokemon_profile_url(tier, min_rating, victim)
        st.markdown(
            f"**First-KO evidence:** [{credited['player']}]({credited_player_url}) "
            f"was credited on turn {credited.get('first_ko_turn')} when "
            f"[{victim}]({victim_url}) fainted first; that player **{outcome}** the battle."
        )
    elif schema_version < 2:
        st.caption(
            "This legacy battle has not been enriched with event-level first-KO data yet."
        )

    team_1, team_2 = st.columns(2)
    with team_1:
        render_team_card(winner, "Winner", tier, min_rating)
    with team_2:
        render_team_card(loser, "Runner-up", tier, min_rating)

    render_plain_callout(
        "Click either player name to see their record in this sample, or click a "
        "Pokémon to see its aggregate performance, common teammates, and other battles."
    )


def render_methodology(
    dataset: TierDataset,
    tier: str,
    min_rating: int,
    summary: dict,
) -> None:
    st.markdown("## About the data")
    render_section_intro(
        "This page makes the pipeline, definitions, and limitations visible so the "
        "analysis can be evaluated instead of treated as a black box."
    )
    render_source_badge(dataset)

    source_1, source_2, source_3 = st.columns(3)
    source_1.metric("Manifest battles", f"{dataset.remote_match_count:,}")
    source_2.metric("Archive battles", f"{dataset.actual_match_count:,}")
    source_3.metric("Archive team records", f"{dataset.record_count:,}")
    if dataset.integrity_gap:
        st.warning(
            "The current release manifest and Parquet archive differ by "
            f"{abs(dataset.integrity_gap):,} battle. The dashboard reports results "
            "from the Parquet records actually present and discloses the gap here."
        )

    st.markdown("### Data flow")
    st.code(
        "Pokémon Showdown public replay API\n"
        "        ↓\n"
        "Scheduled GitHub Actions ingestion\n"
        "        ↓\n"
        "Versioned GitHub Release assets + manifests\n"
        "        ↓\n"
        "Digest-validated temporary cache\n"
        "        ↓\n"
        "Polars queries → linked Streamlit analysis",
        language="text",
    )
    st.caption(
        "The app checks the GitHub release metadata before using a cache. Repository-local "
        "data is not used by the dashboard."
    )

    st.markdown("### First-KO study definition")
    st.markdown(
        "The first-KO side is the player whose opponent alone has a Pokémon faint on "
        "the first turn containing a faint. Same-turn double KOs and no-KO finishes "
        "are disclosed separately and excluded from the primary win-rate denominator. "
        "This turn-level rule cannot always identify indirect or self-inflicted damage, "
        "so the result is described as an association rather than a causal effect."
    )

    definition_left, definition_right = st.columns(2)
    with definition_left:
        st.markdown("### Core definitions")
        st.markdown(
            """
            - **Battle / match:** one completed replay between two players.
            - **Team record:** one player’s side of a battle. Each battle normally creates two.
            - **Usage rate:** the share of filtered team records containing a Pokémon.
            - **Observed win rate:** wins divided by appearances in this replay sample.
            - **Ladder rating:** player Elo from the replay log when available; legacy
              rows use the replay-level rating.
            - **95% interval:** a Wilson score interval showing uncertainty around win rate.
            """
        )
    with definition_right:
        st.markdown("### Important limitations")
        st.markdown(
            """
            - Public replays are not a random sample of every battle played.
            - Win rate is descriptive, not causal.
            - Team composition, player skill, and matchups are confounded.
            - Player names are public account identifiers and may not represent unique people.
            - Daily ingestion and API availability affect coverage.
            """
        )

    st.markdown("### Repository organization")
    st.code(
        "showdown_app/   application logic, data access, analytics, UI\n"
        "showdown_pipeline/ versioned parsing, ingestion, enrichment\n"
        "scripts/        command-line entry points and project checks\n"
        "tests/          deterministic unit and smoke tests\n"
        "docs/           architecture and data dictionary\n"
        ".github/        scheduled data pipeline\n"
        "app.py          Streamlit entry point",
        language="text",
    )

    st.markdown("### Source links")
    st.markdown(
        f"- [GitHub repository](https://github.com/{RELEASE_REPOSITORY})\n"
        f"- [Current data release]({dataset.release_url})\n"
        "- [Pokémon Showdown replays](https://replay.pokemonshowdown.com/)"
    )
