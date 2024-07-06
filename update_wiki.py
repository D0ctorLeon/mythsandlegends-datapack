# update_wiki.py (Python script)
import dokuwikixmlrpc
import os
import json
from pathlib import Path
import ssl
import logging

# Disable SSL verification (USE WITH CAUTION)
ssl._create_default_https_context = ssl._create_unverified_context

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def create_or_update_wiki_page(rpc, page_name, data):
    page_name = f"spawn-info:{page_name}"
    content = f"===== {page_name.split(':')[1]} =====\n\n"

    # Group spawns by key_item
    spawns_by_key_item = {}
    for spawn in data.get("spawns", []):
        key_item = spawn["condition"].get("key_item", "Unknown")  # Default to "Unknown" if missing
        spawns_by_key_item.setdefault(key_item, []).append(spawn)

    # Iterate over key items and their associated spawns
    for key_item, spawns in spawns_by_key_item.items():
        key_items = key_item.replace("_", " ").title()
        content += f"\n**Key Items:** {key_items}\n"

        # Combine biomes from all spawns with this key item
        all_biomes = [
            biome  # Keep hashtags intact
            for spawn in spawns
            for biome in spawn["condition"]["biomes"]
        ]
        unique_biomes = list(set(all_biomes))

        # Additional information (unchanged from your original script)
        combined_spawn = spawns[0].copy()
        pokemon = combined_spawn["pokemon"].capitalize()
        presets = ", ".join(combined_spawn.get("presets", []))
        context = combined_spawn.get("context", "")
        bucket = combined_spawn.get("bucket", "")
        level = combined_spawn.get("level", "")
        weight = combined_spawn.get("weight", "")

        content += f"\n**Species:** {pokemon}\n"
        content += f"**Presets:** {presets}\n"
        if context:
            content += f"**Context:** {context}\n"
        content += f"**Spawn Bucket:** {bucket}\n"
        content += f"**Level Range:** {level}\n"
        content += f"**Weight:** {weight}\n"

        # Biomes table for this key item
        if unique_biomes:
            content += "^ Biomes ^\n"
            for biome in unique_biomes:
                content += f"| {biome} |\n"

        # Additional Conditions table
        other_conditions = {
            k: v
            for k, v in combined_spawn["condition"].items()
            if k not in ("biomes", "key_item") and v
        }
        if other_conditions:
            content += "^ Additional Conditions ^ Value ^\n"  # Table header
            for condition, value in other_conditions.items():
                content += f"| {condition} | {value} |\n"


    rpc.put_page(page_name, content, summary="Automatic update from datapack repository")

def process_repository(rpc, root_path):
    data_folder = Path(root_path) / "data/cobblemon/spawn_pool_world"
    for json_file in data_folder.glob("*.json"):
        with open(json_file, "r") as file:
            data = json.load(file)
            pokemon_name = data["spawns"][0]["pokemon"].capitalize()
            create_or_update_wiki_page(rpc, pokemon_name, data)


# Configuration (Replace placeholders)
wiki_url = os.environ["DOKUWIKI_API_URL"]
username = os.environ["DOKUWIKI_USER"]
password = os.environ["DOKUWIKI_PASSWORD"]
# Initialize the XML-RPC client
rpc = dokuwikixmlrpc.DokuWikiClient(wiki_url, username, password)


# Get the repository root path
repo_root = os.environ["GITHUB_WORKSPACE"] # get the github workspace path

process_repository(rpc, repo_root)
