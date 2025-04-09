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

# Disable SSL verification (USE WITH CAUTION - only if necessary and you trust the server)
# Consider properly configuring certificate verification instead if possible.
# ssl._create_default_https_context = ssl._create_unverified_context

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Helper Functions ---

def load_pokemon_data(filepath):
    """Loads Pokemon data from a JSON file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Ensure keys are lowercase for consistent matching
            return {k.lower(): v for k, v in data.items()}
    except FileNotFoundError:
        logging.error(f"Pokedex data file not found: {filepath}")
        return {}
    except json.JSONDecodeError:
        logging.error(f"Error decoding JSON from {filepath}")
        return {}
    except Exception as e:
        logging.error(f"An error occurred loading Pokedex data from {filepath}: {e}")
        return {}

def fetch_and_parse_item_icons(rpc: dokuwikixmlrpc.DokuWikiClient, page_id: str) -> dict:
    """Fetches item icon markup from a specific DokuWiki page."""
    item_icon_map = {}
    logging.info(f"Attempting to fetch item icons from wiki page: '{page_id}'")
    try:
        # --- CORRECTED LINE ---
        content = rpc.wiki_getPage(page_id)
        # Regex to find lines like: ^ Icon | Name | `myths:item_id` | Desc ^
        # It extracts the Icon markup {{...}} and the item_id `myths:...`
        # Adjust the regex pattern if your wiki table format is different.
        pattern = re.compile(r"^\^.*?({{.*?}})\s*\|.*?\|.*?`(mythsandlegends:[a-zA-Z0-9_]+)`.*?$", re.MULTILINE)
        matches = pattern.finditer(content)
        count = 0
        for match in matches:
            icon_markup = match.group(1).strip()
            identifier = match.group(2).strip()
            if identifier and icon_markup:
                item_icon_map[identifier] = icon_markup
                logging.debug(f"Mapped item: {identifier} -> {icon_markup}")
                count += 1
            else:
                logging.warning(f"Found partial match but missing identifier or icon markup in line: {match.group(0)}")

        if count == 0:
            logging.warning(f"No items parsed from wiki page '{page_id}'. Check page content and regex pattern.")
            logging.debug(f"Content checked was:\n---\n{content[:500]}...\n---") # Log beginning of content for debug
        else:
            logging.info(f"Successfully parsed {count} item icons from '{page_id}'.")
    except dokuwikixmlrpc.DokuWikiError as e:
        logging.error(f"DokuWiki XMLRPC Error fetching page '{page_id}': {e}")
    except AttributeError:
         # This can happen if wiki_getPage returns None or unexpected type
         logging.error(f"Could not get valid content from page '{page_id}'. Check if page exists and has content.")
    except Exception as e:
        # Catching generic Exception to log unexpected errors during parsing
        logging.error(f"An unexpected error occurred parsing item icons from page '{page_id}': {e}", exc_info=True)
    return item_icon_map


# --- Core Wiki Update Logic ---

def create_or_update_wiki_page(rpc: dokuwikixmlrpc.DokuWikiClient, page_name: str, data: dict, pokemon_data: dict, item_icon_map: dict):
    """Generates DokuWiki markup and updates the corresponding wiki page."""
    full_page_name = f"{SPAWN_INFO_NAMESPACE}:{page_name}"
    logging.info(f"Processing page generation for: {full_page_name}")

    # Defensive checks for expected data structure
    if not data.get("spawns") or not isinstance(data["spawns"], list):
        logging.error(f"Skipping {full_page_name}: Invalid or missing 'spawns' list in data.")
        return
    first_spawn = data["spawns"][0]
    if not first_spawn or not isinstance(first_spawn, dict):
         logging.error(f"Skipping {full_page_name}: First spawn entry is invalid.")
         return

    pokemon_name_raw = first_spawn.get("pokemon")
    if not pokemon_name_raw:
        logging.error(f"Skipping {full_page_name}: Missing 'pokemon' name in first spawn entry.")
        return

    pokemon_name_lower = pokemon_name_raw.lower()
    pokemon_name_display = pokemon_name_raw.capitalize() # Simple capitalization

    poke_info = pokemon_data.get(pokemon_name_lower, {})
    pokedex_num = poke_info.get("pokedex", "N/A")
    generation = poke_info.get("generation", "N/A")
    if pokedex_num == "N/A":
        logging.warning(f"Pokedex data not found for: {pokemon_name_lower} (Raw: {pokemon_name_raw})")

    # Start building content
    content = f"===== {pokemon_name_display} =====\n\n"
    content += f"**Pokédex Number:** {pokedex_num}\n"
    content += f"**Generation:** {generation}\n\n"

    # Group spawns by their key item requirement
    spawns_by_key_item = {}
    for i, spawn in enumerate(data.get("spawns", [])):
        if not isinstance(spawn, dict):
            logging.warning(f"Spawn entry at index {i} for {full_page_name} is not a dictionary, skipping.")
            continue
        # Default to "None" if no key_item condition exists
        key_item_id = spawn.get("condition", {}).get("key_item", "None")
        # Ensure key_item_id is a string
        if not isinstance(key_item_id, str):
             logging.warning(f"Key item ID '{key_item_id}' in spawn entry {i} for {full_page_name} is not a string, treating as 'None'.")
             key_item_id = "None"
        spawns_by_key_item.setdefault(key_item_id, []).append(spawn)

    if not spawns_by_key_item:
        logging.warning(f"No valid spawn entries found to process for {full_page_name} after grouping.")
        content += "//No valid spawn configurations found in the source data.//\n"
    else:
        # Process each key item group
        for key_item_id, spawns in spawns_by_key_item.items():
            item_icon = item_icon_map.get(key_item_id, "")
            # Make the display name more readable
            key_items_display = key_item_id.replace("mythsandlegends:", "").replace("_", " ").title() if key_item_id != "None" else "No Specific Key Item"

            content += f"\n==== Spawn Details ({key_items_display}) {item_icon}====\n"

            # Aggregate details - assuming they are mostly the same for the same key item,
            # but collecting all biomes is important.
            all_biomes = set()
            condition_data = {}
            presets = "N/A"
            context = "N/A"
            bucket = "N/A"
            level = "N/A"
            weight = "N/A"

            if spawns: # Use the first spawn entry for common details
                combined_spawn = spawns[0]
                condition_data = combined_spawn.get("condition", {})

                presets_raw = combined_spawn.get("presets", ["N/A"])
                presets = ", ".join([str(p) for p in presets_raw]) # Ensure all are strings

                context = combined_spawn.get("context", "N/A")
                bucket = combined_spawn.get("bucket", "N/A")
                level = combined_spawn.get("level", "N/A")
                weight = combined_spawn.get("weight", "N/A")

                # Collect biomes from ALL spawns in this group
                for spawn in spawns:
                    biomes = spawn.get("condition", {}).get("biomes", [])
                    if isinstance(biomes, list):
                        all_biomes.update(b.strip() for b in biomes if isinstance(b, str))
                    elif isinstance(biomes, str):
                        all_biomes.add(biomes.strip())
                    # else: log warning?

            # Add collected details to content
            content += f"**Presets:** {presets}\n"
            if context and context != "N/A": # Only show if present and not default N/A
                content += f"**Context:** {context}\n"
            content += f"**Spawn Bucket:** {bucket}\n"
            content += f"**Level Range:** {level}\n"
            content += f"**Weight:** {weight}\n"

            # Biomes Table
            if all_biomes:
                content += "\n^ Biomes ^\n"
                for biome in sorted(list(all_biomes)):
                    content += f"| {biome} |\n"
            else:
                content += "**Biomes:** N/A\n" # Or specify if context implies biomes are irrelevant

            # Other Conditions Table
            other_conditions = {
                k: v for k, v in condition_data.items() if k not in ("biomes", "key_item") and v # Ensure value is not empty/false
            }
            if other_conditions:
                content += "\n^ Additional Conditions ^ Value ^\n"
                for condition, value in sorted(other_conditions.items()):
                    # Format value nicely (list to comma-separated string)
                    value_str = ", ".join(map(str, value)) if isinstance(value, list) else str(value)
                    # Make condition key more readable
                    condition_display = condition.replace('_', ' ').title()
                    content += f"| {condition_display} | {value_str} |\n"
            content += "\n" # Add space before next section or end of page


    # Final content adjustment (e.g., adding a footer)
    content += "\n----\n//This page was automatically generated based on the datapack.//"

    # Update the wiki page
    try:
        logging.info(f"Attempting to update wiki page: {full_page_name}")
        # --- CORRECTED LINE ---
        success = rpc.wiki_putPage(full_page_name, content, {"sum": "Automatic update from datapack repository"})
        if success:
             logging.info(f"Successfully updated wiki page: {full_page_name}")
        else:
             # Note: putPage often returns True on success, but check library specifics if needed
             logging.warning(f"Wiki page update call for '{full_page_name}' completed, but returned non-True status (check wiki logs/history).")

    except dokuwikixmlrpc.DokuWikiError as e:
        logging.error(f"DokuWiki XMLRPC Error updating page '{full_page_name}': {e}")
    except Exception as e:
        logging.error(f"Failed to update wiki page '{full_page_name}' due to an unexpected error: {e}", exc_info=True) # Log traceback


def process_repository(rpc: dokuwikixmlrpc.DokuWikiClient, root_path: str, pokemon_data: dict, item_icon_map: dict):
    """Finds spawn JSON files and triggers the update process for each."""
    data_folder = Path(root_path) / "data/cobblemon/spawn_pool_world"
    if not data_folder.is_dir():
        logging.error(f"Spawn data folder not found: {data_folder}")
        return

    json_files_found = list(data_folder.glob("*.json"))
    if not json_files_found:
        logging.warning(f"No JSON files found in {data_folder}")
        return

    logging.info(f"Found {len(json_files_found)} JSON files to process in {data_folder}.")

    processed_count = 0
    error_count = 0
    for json_file in json_files_found:
        logging.debug(f"Processing file: {json_file.name}")
        try:
            with open(json_file, "r", encoding='utf-8') as file:
                data = json.load(file)

                # Basic validation of the loaded JSON data structure
                if "spawns" not in data or not isinstance(data["spawns"], list) or not data["spawns"]:
                    logging.warning(f"Skipping {json_file.name}: 'spawns' key missing, not a list, or empty.")
                    continue

                first_spawn = data["spawns"][0]
                if not isinstance(first_spawn, dict) or "pokemon" not in first_spawn or not first_spawn["pokemon"]:
                    logging.warning(f"Skipping {json_file.name}: 'pokemon' key missing or empty in the first spawn entry.")
                    continue

                # Derive page name from the pokemon field in the first spawn entry
                # Clean the name for use as a DokuWiki page ID
                pokemon_name_id = first_spawn["pokemon"].lower().replace(':','_').replace(' ','_').replace('.','').replace('-','_') # Be safe with page IDs
                if not pokemon_name_id:
                     logging.warning(f"Could not derive a valid page ID from pokemon '{first_spawn['pokemon']}' in {json_file.name}, skipping.")
                     continue


                create_or_update_wiki_page(rpc, pokemon_name_id, data, pokemon_data, item_icon_map)
                processed_count += 1

        except json.JSONDecodeError:
            logging.error(f"Failed to decode JSON from {json_file.name}")
            error_count += 1
        except KeyError as e:
            logging.error(f"Missing expected key {e} while processing {json_file.name}")
            error_count += 1
        except Exception as e:
            logging.error(f"An unexpected error occurred processing {json_file.name}: {e}", exc_info=True) # Log traceback for unexpected errors
            error_count += 1

    logging.info(f"Finished processing JSON files. Processed: {processed_count}, Errors: {error_count}")


# --- Main Execution ---
if __name__ == "__main__":
    logging.info("Starting DokuWiki update script.")

    # Check environment variables
    missing_vars = []
    if not WIKI_URL: missing_vars.append("DOKUWIKI_API_URL")
    if not WIKI_USER: missing_vars.append("DOKUWIKI_USER")
    if not WIKI_PASSWORD: missing_vars.append("DOKUWIKI_PASSWORD")
    if not REPO_ROOT or not Path(REPO_ROOT).is_dir(): missing_vars.append("GITHUB_WORKSPACE (must be a valid directory)")

    if missing_vars:
        logging.error(f"Missing or invalid required environment variables: {', '.join(missing_vars)}. Exiting.")
        exit(1)
    else:
        logging.info("Environment variables seem okay.")

    # Load external data first
    pokedex_data_path = Path(REPO_ROOT) / POKEDEX_DATA_FILE # Assume pokedex data is in repo root
    logging.info(f"Loading Pokedex data from: {pokedex_data_path}")
    pokemon_data = load_pokemon_data(pokedex_data_path)
    if not pokemon_data:
        logging.warning("Pokedex data is empty or failed to load. Pokédex numbers and generations will be 'N/A'.")


    try:
        logging.info(f"Attempting to initialize DokuWikiClient for {WIKI_URL}...")
        # Consider adding a timeout
        rpc = dokuwikixmlrpc.DokuWikiClient(WIKI_URL, WIKI_USER, WIKI_PASSWORD) # Add , verbose=True for debugging XML-RPC calls
        logging.info("DokuWikiClient object created successfully.")

        logging.info("Attempting to verify connection and API version...")
        # Use getattr for safer access in case methods don't exist in older lib versions
        version = getattr(rpc, 'dokuwiki_version', 'N/A')
        api_version = getattr(rpc, 'rpc_version_supported', lambda: 'N/A')() # Call if exists
        logging.info(f"Connected to DokuWiki. Version: {version}, XML-RPC API Version: {api_version}")

        # Fetch item icons AFTER successful connection
        item_icon_map = fetch_and_parse_item_icons(rpc, ITEM_WIKI_PAGE_ID)
        if not item_icon_map:
            logging.warning("Item icon map is empty. Icons will not be displayed.")

        # Process the repository data
        process_repository(rpc, REPO_ROOT, pokemon_data, item_icon_map)

    except dokuwikixmlrpc.DokuWikiError as e:
         logging.error(f"DokuWiki XMLRPC Communication Error: {e}", exc_info=True)
         exit(1)
    except ConnectionRefusedError as e:
         logging.error(f"Connection Refused: Could not connect to DokuWiki at {WIKI_URL}. Check URL and server status. Error: {e}", exc_info=True)
         exit(1)
    except Exception as e:
        # Catch any other unexpected exceptions during setup or processing
        logging.error(f"A fatal error occurred during script execution: {e}", exc_info=True) # Log traceback
        exit(1)

    logging.info("DokuWiki update script finished.")