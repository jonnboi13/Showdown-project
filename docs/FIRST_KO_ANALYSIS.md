# First-KO analysis plan

## Research question

Among public Pokémon Showdown replays with an unambiguous first KO, how strongly
is getting that first KO associated with winning the match?

## Primary measure

The primary estimate is:

```text
first-KO win rate = matches won by first-KO side / eligible matches
```

An eligible match has schema-version-2 replay data and exactly one credited side
on the first turn containing a faint event. Same-turn double KOs and matches with
no faint are reported separately rather than silently removed.

The dashboard's rating threshold is applied to the mean of the two recorded
player ratings. Both team rows are then retained, preventing the filter from
removing the side that took the first KO.

The first result should always be accompanied by:

- total filtered matches;
- enriched matches;
- eligible matches;
- same-turn double-KO matches;
- parsed no-KO matches;
- legacy matches still awaiting enrichment; and
- a confidence interval around the first-KO win rate.

## Follow-up analyses

The raw association is only the beginning. Useful stratifications include:

- turn of first KO;
- ladder-rating band;
- short, medium, and long battles;
- format (OU, UU, or Ubers);
- team archetype; and
- time period or metagame phase.

A later model can estimate the association while controlling for rating
difference, team composition, player repetition, and period effects. Conclusions
must use “associated with winning,” not causal language.

## Bias and edge cases

- Public replays are a selected sample of played battles.
- A forfeit after gaining an overwhelming advantage may occur before a faint.
- Self-KO and indirect damage complicate causal attribution.
- Same-turn faint order is a logging detail, so ties are not broken by order.
- Repeated accounts violate an assumption that every match is independent.
- A first KO late in a battle may mean something different from one on turn 2.

## Pipeline readiness

New ingestion writes the enriched schema automatically. Existing release batches
can be upgraded incrementally with:

```bash
python -m scripts.ingest --tier gen9ou --mode enrich --max-enrichment-batches 10
```

The manifest records completed batch versions, so another run resumes with the
next pending batch. No batch is replaced unless every replay in it parses and the
set of match IDs validates.
