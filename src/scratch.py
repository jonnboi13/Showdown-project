import requests
import re
import polars as pl

match_id = "gen9ou-2668447365" 
url = f"https://replay.pokemonshowdown.com/{match_id}.json"

response = requests.get(url)
battle_data = response.json()

# Grab the giant log string and split it into individual lines
log_lines = battle_data["log"].split("\n")


# Regex patterns for searching for specific lines in the log
pokemon_pattern = re.compile(r"\|poke\|(p[12])\|([^|]+)")
player_pattern = re.compile(r"\|player\|(p[12])\|([^|]+)")


# Loop through each line and test our regex
extracted_data = []
players = {}
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

    
        




df = pl.DataFrame(extracted_data, schema=["player", "pokemon"])
print(df)
