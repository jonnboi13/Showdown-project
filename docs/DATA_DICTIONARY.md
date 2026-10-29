# Data dictionary

Each row represents one player's team in one public Pokémon Showdown replay. A normal battle therefore creates two rows.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | integer | Record contract version. Version 2 contains first-KO fields; version 1 is legacy data awaiting enrichment. |
| `match_id` | string | Public replay identifier and replay URL slug. |
| `format` | string | Competitive ruleset, such as `gen9ou`. |
| `rating` | integer or null | Player Elo parsed from the replay log in schema v2. Legacy rows contain the replay-level rating on both team records. |
| `player` | string | Public replay account name. |
| `won` | boolean | Whether this player won the battle. |
| `turns` | integer | Number of turns in the completed replay. |
| `pokemon` | list of strings | The six team members revealed in the replay log. |
| `uploadtime` | integer | Replay upload time as Unix seconds. |
| `first_ko_turn` | integer or null | Turn containing the first faint event. Null for parsed no-KO matches and unenriched legacy rows. |
| `first_ko_player` | string or null | Player whose opponent was the only side to faint on the first fainting turn. |
| `first_ko_victim` | string or null | Species associated with the first unambiguous faint event. |
| `first_ko_tied` | boolean or null | True when both sides fainted on the first fainting turn. Null means the legacy row has not been enriched. |
| `got_first_ko` | boolean or null | Team-relative indicator. True for the credited side, false for the opponent, and null for tied, no-KO, or legacy rows. |
| `total_faints` | integer or null | Number of `faint` events in the replay log. Zero means a parsed replay ended without a faint; null means legacy data. |

## Derived metrics

- **Usage rate:** appearances divided by filtered team records.
- **Observed win rate:** wins divided by appearances.
- **95% win-rate interval:** Wilson score interval for a binomial proportion.
- **Usage change:** latest seven-day usage minus the preceding seven-day usage, in percentage points.
- **First-KO win rate:** wins by the credited first-KO side divided by matches with one unambiguous credited side.
- **First-KO coverage:** matches with one unambiguous first-KO side divided by all filtered matches.

## First-KO operational definition

The replay protocol reliably records faint events and their side, but it does
not always provide a simple attacker field for every cause of fainting. This
project therefore defines “got the first KO” as **the side whose opponent alone
fainted on the first turn containing any faint event**.

- If both sides faint during that turn, the result is marked tied and excluded
  from the primary first-KO win-rate denominator.
- Replays ending by forfeit or timeout before a faint are marked as parsed no-KO
  matches and excluded from that denominator.
- Self-KO, recoil, hazards, weather, and other indirect effects can make the
  credited side different from the Pokémon that directly caused the faint.
- Replay log order is not used to break same-turn ties.

These metrics describe the collected public replay sample. They are not causal
estimates and do not correct for player skill, team composition, matchup,
concessions, or replay-selection bias.
