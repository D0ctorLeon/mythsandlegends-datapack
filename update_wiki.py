import dokuwikixmlrpc
import os
import json
from pathlib import Path
import ssl
import logging
import re

# --- Configuration ---
WIKI_URL = os.environ["DOKUWIKI_API_URL"]
WIKI_USER = os.environ["DOKUWIKI_USER"]
WIKI_PASSWORD = os.environ["DOKUWIKI_PASSWORD"]
REPO_ROOT = os.environ["GITHUB_WORKSPACE"]
ITEM_WIKI_PAGE_ID = "mythsandlegends:items"
POKEDEX_DATA_FILE = "pokedex_data.json"
SPAWN_INFO_NAMESPACE = "spawn-info"

# Disable SSL verification (USE WITH CAUTION)
ssl._create_default_https_context = ssl._create_unverified_context

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Helper Functions ---

def load_pokemon_data(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return {k.lower(): v for k, v in data.items()}
    except FileNotFoundError:
        logging.error(f"Pokedex data file not found: {filepath}")
        return {}
    except json.JSONDecodeError:
        logging.error(f"Error decoding JSON from {filepath}")
        return {}
    except Exception as e:
        logging.error(f"An error occurred loading Pokedex data: {e}")
        return {}

def fetch_and_parse_item_icons(rpc, page_id):
    item_icon_map = {}
    try:
        content = rpc.call("wiki.getPage", page_id)
        pattern = re.compile(r"^\^.*?({{.*?}})\s*\|.*?\|.*?`(mythsandlegends:[a-zA-Z0-9_]+)`.*?$", re.MULTILINE)
        for match in pattern.finditer(content):
            icon_markup = match.group(1).strip()
            identifier = match.group(2).strip()
            if identifier and icon_markup:
                item_icon_map[identifier] = icon_markup
                logging.debug(f"Mapped item: {identifier} -> {icon_markup}")
        if not item_icon_map:
            logging.warning(f"No items parsed from wiki page '{page_id}'. Check page content and regex.")
        else:
            logging.info(f"Successfully parsed {len(item_icon_map)} item icons from '{page_id}'.")
    except dokuwikixmlrpc.DokuWikiError as e:
        logging.error(f"DokuWiki XMLRPC Error fetching page '{page_id}': {e}")
    except Exception as e:
        logging.error(f"Error parsing item icons from page '{page_id}': {e}")
    return item_icon_map

# --- Core Wiki Update Logic ---

def create_or_update_wiki_page(rpc, page_name, data, pokemon_data, item_icon_map):
    full_page_name = f"{SPAWN_INFO_NAMESPACE}:{page_name}"
    logging.info(f"Processing page: {full_page_name}")

    first_spawn = data.get("spawns", [{}])[0]
    pokemon_name_raw = first_spawn.get("pokemon", "UnknownPokemon")
    pokemon_name_lower = pokemon_name_raw.lower()
    pokemon_name_display = pokemon_name_raw.capitalize()

    poke_info = pokemon_data.get(pokemon_name_lower, {})
    pokedex_num = poke_info.get("pokedex", "N/A")
    generation = poke_info.get("generation", "N/A")
    if pokedex_num == "N/A":
        logging.warning(f"Pokedex data not found for: {pokemon_name_lower}")

    content = f"===== {pokemon_name_display} =====\n\n"
    content += f"**Pokédex Number:** {pokedex_num}\n"
    content += f"**Generation:** {generation}\n\n"

    spawns_by_key_item = {}
    for spawn in data.get("spawns", []):
        key_item_id = spawn.get("condition", {}).get("key_item", "None")
        spawns_by_key_item.setdefault(key_item_id, []).append(spawn)

    for key_item_id, spawns in spawns_by_key_item.items():
        item_icon = item_icon_map.get(key_item_id, "")
        key_items_display = key_item_id.replace("mythsandlegends:", "").replace("_", " ").title() if key_item_id != "None" else "None"

        content += f"\n===== {item_icon} {key_items_display} =====\n"

        all_biomes = set()
        for spawn in spawns:
            condition = spawn.get("condition", {})
            biomes = condition.get("biomes", [])
            if isinstance(biomes, list):
                all_biomes.update(biomes)
            elif isinstance(biomes, str):
                all_biomes.add(biomes)

        combined_spawn = spawns[0] if spawns else {}
        condition_data = combined_spawn.get("condition", {})

        # Preset formatting fix for possible dicts
        presets_raw = combined_spawn.get("presets", ["N/A"])
        presets = ", ".join([p if isinstance(p, str) else json.dumps(p) for p in presets_raw])

        context = combined_spawn.get("context", "N/A")
        bucket = combined_spawn.get("bucket", "N/A")
        level = combined_spawn.get("level", "N/A")
        weight = combined_spawn.get("weight", "N/A")

        content += f"**Presets:** {presets}\n"
        if context and context != "N/A":
            content += f"**Context:** {context}\n"
        content += f"**Spawn Bucket:** {bucket}\n"
        content += f"**Level Range:** {level}\n"
        content += f"**Weight:** {weight}\n"

        if all_biomes:
            content += "\n^ Biomes ^\n"
            for biome in sorted(list(all_biomes)):
                content += f"| {biome.strip()} |\n"
        else:
            content += "**Biomes:** N/A\n"

        other_conditions = {
            k: v
            for k, v in condition_data.items()
            if k not in ("biomes", "key_item") and v
        }
        if other_conditions:
            content += "\n^ Additional Conditions ^ Value ^\n"
            for condition, value in sorted(other_conditions.items()):
                value_str = ", ".join(value) if isinstance(value, list) else str(value)
                content += f"| {condition.replace('_',' ').title()} | {value_str} |\n"

    content += "\n"

    try:
        rpc.call("wiki.putPage", full_page_name, content, {"sum": "Automatic update from datapack repository"})
        logging.info(f"Successfully updated wiki page: {full_page_name}")
    except dokuwikixmlrpc.DokuWikiError as e:
        logging.error(f"DokuWiki XMLRPC Error updating page '{full_page_name}': {e}")
    except Exception as e:
        logging.error(f"Failed to update wiki page '{full_page_name}': {e}")

def process_repository(rpc, root_path, pokemon_data, item_icon_map):
    data_folder = Path(root_path) / "data/cobblemon/spawn_pool_world"
    if not data_folder.is_dir():
        logging.error(f"Spawn data folder not found: {data_folder}")
        return

    json_files_found = list(data_folder.glob("*.json"))
    if not json_files_found:
        logging.warning(f"No JSON files found in {data_folder}")
        return

    logging.info(f"Found {len(json_files_found)} JSON files to process.")

    for json_file in json_files_found:
        logging.debug(f"Processing file: {json_file.name}")
        try:
            with open(json_file, "r", encoding='utf-8') as file:
                data = json.load(file)

                if "spawns" not in data or not isinstance(data["spawns"], list) or not data["spawns"]:
                    logging.warning(f"Skipping {json_file.name}: 'spawns' key missing, not a list, or empty.")
                    continue

                if "pokemon" not in data["spawns"][0] or not data["spawns"][0]["pokemon"]:
                    logging.warning(f"Skipping {json_file.name}: 'pokemon' key missing or empty in the first spawn.")
                    continue

                pokemon_name = data["spawns"][0]["pokemon"].capitalize()
                page_id_name = data["spawns"][0]["pokemon"].lower().replace(':','_').replace(' ','_')

                create_or_update_wiki_page(rpc, page_id_name, data, pokemon_data, item_icon_map)

        except json.JSONDecodeError:
            logging.error(f"Failed to decode JSON from {json_file.name}")
        except KeyError as e:
            logging.error(f"Missing expected key {e} in {json_file.name}")
        except Exception as e:
            logging.error(f"An unexpected error occurred processing {json_file.name}: {e}")

# --- Main Execution ---
if __name__ == "__main__":
    logging.info("Starting DokuWiki update script.")

    if not all([WIKI_URL, WIKI_USER, WIKI_PASSWORD, REPO_ROOT]):
        logging.error("Missing required environment variables. Exiting.")
        exit(1)

    rpc = None
    try:
        logging.info(f"Attempting to initialize DokuWikiClient for {WIKI_URL}...")
        rpc = dokuwikixmlrpc.DokuWikiClient(WIKI_URL, WIKI_USER, WIKI_PASSWORD)
        logging.info("DokuWikiClient object created successfully.")

        logging.info("Attempting to verify connection using dokuwiki_version() and rpc_version_supported()...")
        version = rpc.dokuwiki_version
        api_version = rpc.rpc_version_supported()
        logging.info(f"Connected to DokuWiki. Version: {version}, API Version: {api_version}")

    except dokuwikixmlrpc.DokuWikiError as e:
        logging.error(f"DokuWiki API Error during connection verification: {e}")
        exit(1)
    except Exception as e:
        logging.error(f"Failed to initialize or verify DokuWiki client: {e}")
        logging.error(f"Exception type: {type(e).__name__}")
        exit(1)

    if rpc is None:
        logging.error("RPC client could not be initialized. Exiting.")
        exit(1)

    pokemon_data = load_pokemon_data(POKEDEX_DATA_FILE)
    item_icon_map = fetch_and_parse_item_icons(rpc, ITEM_WIKI_PAGE_ID)

    if not pokemon_data:
        logging.warning("Pokedex data is empty. Pokédex numbers and generations will be 'N/A'.")
    if not item_icon_map:
        logging.warning("Item icon map is empty. Icons will not be displayed.")

    process_repository(rpc, REPO_ROOT, pokemon_data, item_icon_map)

    logging.info("DokuWiki update script finished.")
