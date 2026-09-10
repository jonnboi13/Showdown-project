import requests
import re
import polars as pl



match_id = "gen9ou-2668447365" 
url = f"https://replay.pokemonshowdown.com/{match_id}.json"

response = requests.get(url)
battle_data = response.json()

# Grab the giant log string and split it into individual lines
log_lines = battle_data["log"].split("\n")

# Grab the match format and rating
match_format = battle_data.get("format", "Unknown")
match_rating = battle_data.get("rating", "Unknown")

# Regex patterns for searching for specific lines in the log
pokemon_pattern = re.compile(r"\|poke\|(p[12])\|([^|]+)")
player_pattern = re.compile(r"\|player\|(p[12])\|([^|]+)")
win_pattern = re.compile(r"\|win\|([^|]+)")
turn_pattern = re.compile(r"\|turn\|(\d+)")


# Loop through each line and test our regex
extracted_data = []
players = {}
winner = "Unknown"
turns = 0
for line in log_lines:

    # Check for a match with the player pattern and store the player names in a dictionary
    player_match = player_pattern.search(line)
    if player_match:
        slot, name = player_match.groups()
        players[slot] = name

    # Check for a match with the pokemon pattern
    pokemon_match = pokemon_pattern.search(line)
    if pokemon_match:
        slot, pokemon = pokemon_match.groups()
        # Get the player name from the players dictionary, defaulting to "Unknown" if not found
        player_name = players.get(slot, "Unknown")
        # Append the player name and pokemon to the extracted_data list
        extracted_data.append({"player": player_name, "pokemon": pokemon})

    # Check for a match with the win pattern
    win_match = win_pattern.search(line)
    if win_match:
        winner = win_match.group(1)

    # Check for a match with the turn pattern
    turn_match = turn_pattern.search(line)
    if turn_match:
        turns = max(turns, int(turn_match.group(1)))




df = pl.DataFrame(extracted_data, schema=["player", "pokemon"])
grouped_pokemon = df.group_by("player").agg(pl.col("pokemon").implode())

match_info = grouped_pokemon.with_columns(
    (pl.col("player") == winner).alias("won"),
    pl.lit(turns).alias("turns"),
    pl.lit(match_format).alias("format"),
    pl.lit(match_rating).alias("rating"),
    pl.lit(match_id).alias("match_id")
).select([
            "match_id",  # Re-order columns
            "format",
            "rating",
            "player",
            "won",
            "turns",
            "pokemon"
        ])



print(match_info)
