# update_wiki.py (Python script)
import dokuwikixmlrpc
import os
import json
from pathlib import Path
import ssl
import logging
import re # Import regular expressions

# --- Configuration ---
WIKI_URL = os.environ["DOKUWIKI_API_URL"]
WIKI_USER = os.environ["DOKUWIKI_USER"]
WIKI_PASSWORD = os.environ["DOKUWIKI_PASSWORD"]
REPO_ROOT = os.environ["GITHUB_WORKSPACE"] # get the github workspace path
ITEM_WIKI_PAGE_ID = "mythsandlegends:items" # ID of the page with item icons
POKEDEX_DATA_FILE = "pokedex_data.json" # Path to your Pokedex data file
SPAWN_INFO_NAMESPACE = "spawn-info" # Namespace for the generated pages

# Disable SSL verification (USE WITH CAUTION)
ssl._create_default_https_context = ssl._create_unverified_context

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Helper Functions ---

def load_pokemon_data(filepath):
    """Loads Pokedex data from a JSON file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Ensure keys are lowercase for consistent lookup
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
    """Fetches a DokuWiki page and parses the item table for icons."""
    item_icon_map = {}
    try:
        content = rpc.get_page(page_id)
        # Regex to find table rows: Icon | Name | Identifier | ...
        # Captures: 1=Icon Markup, 2=Identifier (mythsandlegends:...)
        # Adjusted regex to be more robust against whitespace variations and code tags
        # It looks for the icon, skips columns until it finds `mythsandlegends:`, then captures the identifier.
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
    """Creates or updates a wiki page with spawn information."""
    # Use the configured namespace
    full_page_name = f"{SPAWN_INFO_NAMESPACE}:{page_name}"
    logging.info(f"Processing page: {full_page_name}")

    # Basic Pokemon Info (handle potential missing data)
    first_spawn = data.get("spawns", [{}])[0]
    pokemon_name_raw = first_spawn.get("pokemon", "UnknownPokemon")
    pokemon_name_lower = pokemon_name_raw.lower()
    pokemon_name_display = pokemon_name_raw.capitalize()

    # Look up Pokedex data
    poke_info = pokemon_data.get(pokemon_name_lower, {})
    pokedex_num = poke_info.get("pokedex", "N/A")
    generation = poke_info.get("generation", "N/A")
    if pokedex_num == "N/A":
        logging.warning(f"Pokedex data not found for: {pokemon_name_lower}")

    # Start building content
    content = f"===== {pokemon_name_display} =====\n\n"
    content += f"**Pokédex Number:** {pokedex_num}\n"
    content += f"**Generation:** {generation}\n\n"

    # Group spawns by key_item
    spawns_by_key_item = {}
    for spawn in data.get("spawns", []):
        # Default to "None" or "Unknown" if key_item is missing or empty
        key_item_id = spawn.get("condition", {}).get("key_item")
        if not key_item_id: # Handles None or empty string
             key_item_id = "None"
        spawns_by_key_item.setdefault(key_item_id, []).append(spawn)

    # Iterate over key items and their associated spawns
    for key_item_id, spawns in spawns_by_key_item.items():
        # Get item icon and formatted name
        item_icon = item_icon_map.get(key_item_id, "") # Get icon markup or empty string
        # Format name from ID if not 'None'
        key_items_display = key_item_id.replace("mythsandlegends:", "").replace("_", " ").title() if key_item_id != "None" else "None"

        content += f"\n===== {item_icon} {key_items_display} =====\n" # Add icon before the name

        # Combine biomes from all spawns with this key item
        all_biomes = set() # Use a set for automatic uniqueness
        for spawn in spawns:
             # Ensure 'condition' and 'biomes' exist and biomes is iterable
            condition = spawn.get("condition", {})
            biomes = condition.get("biomes", [])
            if isinstance(biomes, list): # Check if it's a list
                 all_biomes.update(biomes) # Add items from the list to the set
            elif isinstance(biomes, str): # Handle if it's just a string biome
                 all_biomes.add(biomes)


        # Use the first spawn for common details (assuming they are consistent per key item)
        # If spawns list is empty, provide default values
        combined_spawn = spawns[0] if spawns else {}
        condition_data = combined_spawn.get("condition", {})

        # Extract details safely using .get()
        presets = ", ".join(combined_spawn.get("presets", ["N/A"]))
        context = combined_spawn.get("context", "N/A")
        bucket = combined_spawn.get("bucket", "N/A")
        level = combined_spawn.get("level", "N/A")
        weight = combined_spawn.get("weight", "N/A") # Weight might be specific per spawn entry, consider how to represent if it varies.

        # Add common details (if not already added globally, decide structure)
        # content += f"**Species:** {pokemon_name_display}\n" # Already at the top
        content += f"**Presets:** {presets}\n"
        if context and context != "N/A": # Only show context if it exists
            content += f"**Context:** {context}\n"
        content += f"**Spawn Bucket:** {bucket}\n"
        content += f"**Level Range:** {level}\n"
        content += f"**Weight:** {weight}\n" # Note: This takes the weight of the *first* spawn listed for this key item.

        # Biomes table for this key item
        if all_biomes:
            content += "\n^ Biomes ^\n"
            # Sort biomes alphabetically for consistency
            for biome in sorted(list(all_biomes)):
                content += f"| {biome.strip()} |\n" # Ensure no leading/trailing whitespace
        else:
            content += "**Biomes:** N/A\n" # Indicate if no biomes are specified


        # Additional Conditions table
        other_conditions = {
            k: v
            for k, v in condition_data.items()
            # Exclude known keys and keys with falsey values (None, empty string, etc.)
            if k not in ("biomes", "key_item") and v
        }
        if other_conditions:
            content += "\n^ Additional Conditions ^ Value ^\n"  # Table header
            for condition, value in sorted(other_conditions.items()): # Sort for consistency
                 # Handle list values (like 'times') gracefully
                value_str = ", ".join(value) if isinstance(value, list) else str(value)
                content += f"| {condition.replace('_',' ').title()} | {value_str} |\n"

    # Add a final newline for spacing
    content += "\n"

    try:
        # Check if page exists before putting content
        # page_info = rpc.get_page_info(full_page_name) # Optional: Check if exists
        rpc.put_page(full_page_name, content, summary="Automatic update from datapack repository")
        logging.info(f"Successfully updated wiki page: {full_page_name}")
    except dokuwikixmlrpc.DokuWikiError as e:
        logging.error(f"DokuWiki XMLRPC Error updating page '{full_page_name}': {e}")
    except Exception as e:
        logging.error(f"Failed to update wiki page '{full_page_name}': {e}")


def process_repository(rpc, root_path, pokemon_data, item_icon_map):
    """Processes JSON files in the spawn pool directory."""
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

                # Basic validation: Check if 'spawns' key exists and is a non-empty list
                if "spawns" not in data or not isinstance(data["spawns"], list) or not data["spawns"]:
                    logging.warning(f"Skipping {json_file.name}: 'spawns' key missing, not a list, or empty.")
                    continue

                # Basic validation: Check if the first spawn has a 'pokemon' key
                if "pokemon" not in data["spawns"][0] or not data["spawns"][0]["pokemon"]:
                     logging.warning(f"Skipping {json_file.name}: 'pokemon' key missing or empty in the first spawn.")
                     continue

                # Use the Pokemon name from the first spawn entry for the page title
                pokemon_name = data["spawns"][0]["pokemon"].capitalize()
                # Use the raw pokemon name (or a generated ID) for the page ID to avoid issues with special chars
                page_id_name = data["spawns"][0]["pokemon"].lower().replace(':','_').replace(' ','_') # Make it filename safe

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

    # Validate environment variables
    if not all([WIKI_URL, WIKI_USER, WIKI_PASSWORD, REPO_ROOT]):
        logging.error("Missing one or more required environment variables (DOKUWIKI_API_URL, DOKUWIKI_USER, DOKUWIKI_PASSWORD, GITHUB_WORKSPACE). Exiting.")
        exit(1)

    # Initialize the XML-RPC client
    rpc = None # Initialize rpc to None outside the try block
    try:
        rpc = dokuwikixmlrpc.DokuWikiClient(WIKI_URL, WIKI_USER, WIKI_PASSWORD)
        # Optional: Verify connection with a simple call
        rpc.dokuwiki_version()
        logging.info(f"Successfully connected to DokuWiki at {WIKI_URL}")
    # Correctly aligned with 'try'
    except Exception as e:
        logging.error(f"Failed to initialize DokuWiki client: {e}")
        # Optionally log the type of exception for more detail:
        # logging.error(f"Exception type: {type(e).__name__}")
        exit(1) # Exit if connection fails

    # Check if rpc was successfully initialized before proceeding
    if rpc is None:
         logging.error("RPC client was not initialized. Exiting.")
         exit(1)

    # Load external data
    pokemon_data = load_pokemon_data(POKEDEX_DATA_FILE)
    item_icon_map = fetch_and_parse_item_icons(rpc, ITEM_WIKI_PAGE_ID)

    if not pokemon_data:
        logging.warning("Pokedex data is empty. Pokédex numbers and generations will be 'N/A'.")
    if not item_icon_map:
        logging.warning("Item icon map is empty. Icons will not be displayed.")

    # Process the repository
    process_repository(rpc, REPO_ROOT, pokemon_data, item_icon_map)

    logging.info("DokuWiki update script finished.")