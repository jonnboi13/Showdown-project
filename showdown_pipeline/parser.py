"""Convert a Pokémon Showdown replay payload into analysis-ready team rows."""

from __future__ import annotations

import re
from dataclasses import dataclass

import polars as pl
import requests

from showdown_pipeline.schema import RECORD_SCHEMA_VERSION, coerce_team_records


POKEMON_PATTERN = re.compile(r"^\|poke\|(p[12])\|([^|]+)")
PLAYER_PATTERN = re.compile(r"^\|player\|(p[12])\|([^|]+)")
WIN_PATTERN = re.compile(r"^\|win\|([^|]+)")
TURN_PATTERN = re.compile(r"^\|turn\|(\d+)")
ACTIVE_PATTERN = re.compile(
    r"^\|(?:switch|drag|replace|detailschange)\|(p[12][a-z]?): ([^|]+)\|([^|]+)"
)
FAINT_PATTERN = re.compile(r"^\|faint\|(p[12][a-z]?): ([^|]+)")


@dataclass(frozen=True)
class FaintEvent:
    side: str
    turn: int | None
    victim: str


@dataclass(frozen=True)
class FirstKo:
    turn: int | None
    player: str | None
    victim: str | None
    side: str | None
    tied: bool
    total_faints: int


def _species_from_details(details: str) -> str:
    return details.split(",", maxsplit=1)[0].removesuffix("-*")


def _player_rating(log_line: str) -> int | None:
    """Read the optional Elo field from a Showdown ``|player|`` message."""
    parts = log_line.split("|")
    if len(parts) <= 5 or not parts[5].strip():
        return None
    try:
        return int(float(parts[5]))
    except ValueError:
        return None


def _side(actor: str) -> str:
    return actor[:2]


def _other_side(side: str) -> str:
    return "p2" if side == "p1" else "p1"


def _summarize_first_ko(
    faint_events: list[FaintEvent],
    players: dict[str, str],
) -> FirstKo:
    if not faint_events:
        return FirstKo(None, None, None, None, False, 0)

    first_turn = faint_events[0].turn
    first_turn_events = [event for event in faint_events if event.turn == first_turn]
    victim_sides = {event.side for event in first_turn_events}
    tied = len(victim_sides) > 1
    if tied:
        return FirstKo(first_turn, None, None, None, True, len(faint_events))

    victim = first_turn_events[0]
    first_ko_side = _other_side(victim.side)
    return FirstKo(
        first_turn,
        players.get(first_ko_side),
        victim.victim,
        first_ko_side,
        False,
        len(faint_events),
    )


def parse_replay_payload(match_id: str, payload: dict) -> pl.DataFrame:
    """Parse a replay API payload without performing network I/O.

    A first KO is considered unambiguous only when every faint on the first
    fainting turn belongs to the same side. If both sides faint on that turn,
    ``first_ko_tied`` is true and ``got_first_ko`` is null for both team rows.
    """
    log_lines = payload["log"].splitlines()
    match_format = payload.get("format", "Unknown")
    raw_rating = payload.get("rating")
    rating = raw_rating if isinstance(raw_rating, int) else None
    upload_time = int(payload.get("uploadtime", 0))

    players: dict[str, str] = {}
    player_ratings: dict[str, int] = {}
    rosters: dict[str, list[str]] = {"p1": [], "p2": []}
    active_species: dict[str, str] = {}
    faint_events: list[FaintEvent] = []
    winner = "Unknown"
    turns = 0
    current_turn: int | None = None

    for line in log_lines:
        player_match = PLAYER_PATTERN.search(line)
        if player_match:
            slot, name = player_match.groups()
            players[slot] = name
            parsed_rating = _player_rating(line)
            if parsed_rating is not None:
                player_ratings[slot] = parsed_rating

        pokemon_match = POKEMON_PATTERN.search(line)
        if pokemon_match:
            slot, pokemon = pokemon_match.groups()
            rosters.setdefault(slot, []).append(pokemon)

        turn_match = TURN_PATTERN.search(line)
        if turn_match:
            current_turn = int(turn_match.group(1))
            turns = max(turns, current_turn)

        active_match = ACTIVE_PATTERN.search(line)
        if active_match:
            actor, _, details = active_match.groups()
            active_species[actor] = _species_from_details(details)

        faint_match = FAINT_PATTERN.search(line)
        if faint_match:
            actor, nickname = faint_match.groups()
            faint_events.append(FaintEvent(
                side=_side(actor),
                turn=current_turn,
                victim=active_species.get(actor, nickname),
            ))

        win_match = WIN_PATTERN.search(line)
        if win_match:
            winner = win_match.group(1)

    first_ko = _summarize_first_ko(faint_events, players)
    records = []
    for slot in ("p1", "p2"):
        player = players.get(slot, "Unknown")
        got_first_ko = None
        if first_ko.side is not None:
            got_first_ko = slot == first_ko.side

        records.append({
            "schema_version": RECORD_SCHEMA_VERSION,
            "match_id": match_id,
            "format": match_format,
            "rating": player_ratings.get(slot, rating),
            "player": player,
            "won": player == winner,
            "turns": turns,
            "pokemon": rosters.get(slot, []),
            "uploadtime": upload_time,
            "first_ko_turn": first_ko.turn,
            "first_ko_player": first_ko.player,
            "first_ko_victim": first_ko.victim,
            "first_ko_tied": first_ko.tied,
            "got_first_ko": got_first_ko,
            "total_faints": first_ko.total_faints,
        })

    return coerce_team_records(pl.DataFrame(records, strict=False))


def fetch_and_parse_replay(
    match_id: str,
    session: requests.Session | None = None,
) -> pl.DataFrame:
    client = session or requests.Session()
    response = client.get(
        f"https://replay.pokemonshowdown.com/{match_id}.json",
        timeout=30,
    )
    response.raise_for_status()
    return parse_replay_payload(match_id, response.json())
