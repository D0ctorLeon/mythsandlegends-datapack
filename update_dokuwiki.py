#!/usr/bin/env python
import os
import json
import argparse
import glob
from collections import defaultdict
import logging
import hashlib
import ssl
import re # Import regex for safe filenames
from pathlib import Path # Use pathlib for paths

# --- DokuWiki XMLRPC Library ---
try:
    from dokuwikixmlrpc import DokuWikiClient, DokuWikiURLError, DokuWikiError, DokuWikiXMLRPCProtocolError, DokuWikiXMLRPCError
except ImportError:
    print("Error: The 'dokuwikixmlrpc' library is required. Please install it using 'pip install dokuwikixmlrpc'")
    exit(1)

# --- Environment Variables ---
try:
    from dotenv import load_dotenv
    load_dotenv() # Load .env file if present
except ImportError:
    print("Info: 'python-dotenv' not found. Relying on environment variables or command-line arguments.")
    pass


# --- SSL Verification Workaround ---
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError: pass
else: ssl._create_default_https_context = _create_unverified_https_context
# --- End Workaround ---

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Constants ---
# Define standard condition keys that have dedicated columns or specific handling
KNOWN_CONDITION_KEYS = {
    "biomes", "canSeeSky", "timeRange", "isRaining", "isThundering",
    "key_item", "neededNearbyBlocks",
    "required_cells", "required_cores", # Zygarde
    "pokemon_in_party_requirement",    # Party Pokemon
    "item_requirement"                 # Required Items
}
# Define context descriptions for tooltips (used in link generation)
CONTEXT_DESCRIPTIONS = {
    "grounded": "Will only spawn on land",
    "submerged": "Will only spawn underwater",
    "surface": "Will only spawn on the surface of water or lava"
}
CONTEXT_LINK_NAMESPACE = "mythsandlegends:conditions:context"
CONDITION_LINK_NAMESPACE = "mythsandlegends:conditions"
ITEM_LINK_NAMESPACE = "mythsandlegends:items" # Namespace for item links

# --- Helper Functions ---

def load_json_file(filepath):
    """Loads JSON data from a file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON from {filepath}: {e}")
    except FileNotFoundError:
        logging.error(f"File not found: {filepath}")
    except Exception as e:
        logging.error(f"Error reading {filepath}: {e}")
    return None

def get_item_icon_markup(item_id):
    """Generates DokuWiki markup for an item icon, checking namespace."""
    if item_id and isinstance(item_id, str) and ':' in item_id:
        # Simple heuristic: assume standard format namespace:name
        # You might need stricter validation depending on your item ID formats
        return f"{{{{:{item_id}.png?nolink&16}}}}"
    elif item_id and isinstance(item_id, str): # Handle unqualified IDs if necessary
        # Example: Assume 'minecraft' namespace if none provided
        # return f"{{{{:minecraft:{item_id}.png?nolink&16}}}}"
        pass # Or ignore unqualified IDs for icons
    return ""

def format_condition_value_for_display(key, value, wiki_namespace):
    """Formats condition VALUES for display in the wiki table. Adds links where appropriate."""
    if value is None or value == "" or (isinstance(value, list) and not value):
        return " " # Return space for empty/null cells/empty lists

    # --- Biome Specific Formatting (No Links) ---
    if key == "biomes":
        if isinstance(value, list):
            formatted_items = [str(item).strip() for item in value if str(item).strip()]
            # Use DokuWiki's newline `\\` for lists within table cells
            return " \\\\ ".join(formatted_items) if formatted_items else " "
        else:
            return str(value) # Handle single string biome case

    # --- Default Formatting ---
    if isinstance(value, bool):
        return str(value)

    if isinstance(value, list):
        # Default list formatting (e.g., for neededNearbyBlocks if not handled specifically)
        formatted_items = [str(item).strip() for item in value if str(item).strip()]
        return " \\\\ ".join(formatted_items) if formatted_items else " "

    item_id = str(value) # Treat single values as potential items/links

    # Specific formatting for known keys linking VALUES (Key Item)
    if key == "key_item":
        icon = get_item_icon_markup(item_id)
        item_page_link = f"[[{ITEM_LINK_NAMESPACE}#{item_id.replace(':','_')}|{item_id}]]"
        return f"{icon} {item_page_link}".strip()

    # Default: return string representation for other single values
    return item_id

def create_condition_link(key, wiki_namespace, display_text=None):
    """Creates a DokuWiki link for a condition KEY."""
    page_key = key # Use raw key for page name unless sanitization needed
    link_text = display_text if display_text is not None else key
    return f"[[{wiki_namespace}:{page_key}|{link_text}]]"

def make_hashable(data):
    """Recursively converts lists and dicts to tuples and frozensets for hashing."""
    if isinstance(data, dict):
        # Sort items by key before creating frozenset for consistent hashing
        return frozenset((k, make_hashable(v)) for k, v in sorted(data.items()))
    if isinstance(data, list):
        # Convert elements and then the list to a tuple
        # If the list contains dicts that need consistent order (like requirements),
        # ensure they are sorted before conversion if possible.
        # (Sorting is handled specifically for requirements lists in merge_similar_spawns)
        return tuple(make_hashable(item) for item in data)
    # Assume primitive types (int, str, bool, float, None) are hashable
    return data


def merge_similar_spawns(spawn_list):
    """Merges spawn entries that only differ by their biome list."""
    merged_spawns = defaultdict(lambda: {"biomes": set(), "spawns": []})

    for spawn in spawn_list:
        conditions = spawn.get("condition", {}) or {}
        anticonditions = spawn.get("anticondition", {}) or {}

        # Create a key based on all relevant properties EXCEPT biomes
        key_conditions = {k: v for k, v in conditions.items() if k != 'biomes'}

        # Prepare complex condition structures for hashing
        # Pokemon in Party Requirement: Sort list by species before hashing
        party_req = sorted(key_conditions.get('pokemon_in_party_requirement', []) or [], key=lambda x: x.get('species', ''))
        hashable_party_req = make_hashable(party_req)
        if 'pokemon_in_party_requirement' in key_conditions: # Replace original list with hashable version for key
            key_conditions['pokemon_in_party_requirement'] = hashable_party_req

        # Item Requirement: Sort list by ID before hashing
        item_req = sorted(key_conditions.get('item_requirement', []) or [], key=lambda x: x.get('id', ''))
        hashable_item_req = make_hashable(item_req)
        if 'item_requirement' in key_conditions: # Replace original list with hashable version for key
             key_conditions['item_requirement'] = hashable_item_req

        # Make the rest of the conditions and anticonditions hashable
        hashable_conditions = make_hashable(key_conditions)
        hashable_anticonditions = make_hashable(anticonditions)


        try:
            key_tuple = (
                spawn.get("context"),
                spawn.get("level"),
                spawn.get("bucket"),
                spawn.get("weight"),
                make_hashable(spawn.get("weightMultiplier")), # Hash multiplier structure
                hashable_conditions,
                hashable_anticonditions,
                # Add any other fields that MUST match here (e.g., presets?)
                tuple(sorted(spawn.get("presets", []))) # Example: include presets
            )
        except Exception as e: # Catch broader exceptions during hashing
            logging.warning(f"Could not create hashable key for spawn {spawn.get('id', 'N/A')}. Skipping merge possibility. Error: {e}. Data: {spawn}")
            key_tuple = f"unique_{spawn.get('id', os.urandom(8).hex())}" # Fallback to unique key


        # Add biomes from the current spawn
        spawn_biomes = conditions.get("biomes", [])
        if isinstance(spawn_biomes, list):
            merged_spawns[key_tuple]["biomes"].update(b for b in spawn_biomes if b) # Add non-empty biomes
        elif spawn_biomes: # Handle single string biome case
             merged_spawns[key_tuple]["biomes"].add(spawn_biomes)

        # Store the first representative spawn
        if not merged_spawns[key_tuple]["spawns"]:
            merged_spawns[key_tuple]["spawns"].append(spawn)

    # Convert back to a list of dictionaries
    final_list = []
    for key_data, merged_data in merged_spawns.items():
        if not merged_data["spawns"]: continue

        representative_spawn = merged_data["spawns"][0]
        new_spawn = representative_spawn.copy()
        new_spawn["condition"] = new_spawn.get("condition", {}).copy()
        new_spawn["condition"]["biomes"] = sorted(list(merged_data["biomes"])) # Use merged biomes

        final_list.append(new_spawn)

    return final_list


def generate_wiki_content(pokemon_name, pokedex_data, spawn_entries, version, wiki_namespace):
    """Generates the DokuWiki page content for a single Pokémon."""
    pokedex_info = pokedex_data.get(pokemon_name, {})
    gen = pokedex_info.get('generation', 'unknown')
    number = pokedex_info.get('pokedex', '???')
    safe_pokemon_name_display = pokemon_name.capitalize()

    content = f"====== Spawn Data: {safe_pokemon_name_display} (Gen {gen}, #{number}) ======\n\n"
    content += f"This page details the natural spawning conditions for **{safe_pokemon_name_display}** based on the Myths and Legends datapack (Version: {version}).\n\n"

    # 1. Merge similar spawn entries
    merged_spawns = merge_similar_spawns(spawn_entries)
    if len(merged_spawns) < len(spawn_entries):
        logging.info(f"Merged {len(spawn_entries)} spawn entries down to {len(merged_spawns)} for {pokemon_name}")

    # 2. Determine which optional columns are needed
    # Define potential optional headers and their activation check keys
    optional_headers_config = {
        "CanSeeSky": {"keys": ["canSeeSky"]},
        "Time": {"keys": ["timeRange"]},
        "Weather": {"keys": ["isRaining", "isThundering"]},
        "Key Item": {"keys": ["key_item"]},
        "Nearby Blocks": {"keys": ["neededNearbyBlocks"]},
        "Zygarde Cube": {"keys": ["required_cells", "required_cores"]},
        "Party Pokémon": {"keys": ["pokemon_in_party_requirement"]},
        "Required Items": {"keys": ["item_requirement"]},
        "Other Conditions": {"check_other": True} # Special flag
    }
    active_optional_headers = {hdr: False for hdr in optional_headers_config}

    for entry in merged_spawns:
        conditions = entry.get("condition", {}) or {}
        anticonditions = entry.get("anticondition", {}) or {}

        for header, config in optional_headers_config.items():
            if active_optional_headers[header]: continue # Already activated

            if config.get("check_other"):
                has_other = False
                for key, value in conditions.items():
                    if key not in KNOWN_CONDITION_KEYS and value is not None:
                        has_other = True
                        break
                if anticonditions: has_other = True
                if has_other: active_optional_headers[header] = True
            else:
                for key in config["keys"]:
                    if conditions.get(key) is not None:
                        active_optional_headers[header] = True
                        break # Check next header once activated

    # Base headers + active optional headers
    base_headers = ["Context", "Level", "Bucket", "Weight", "Biomes"]
    final_headers = base_headers + [hdr for hdr, active in active_optional_headers.items() if active]


    # Create header row with links
    header_links = {
        # Base headers (if linking needed)
        "Biomes": f"Biomes / [[https://docs.google.com/document/d/1iB0EJSc2r6mRJXIo1n3XpHbZ5udwJVnrh2pXdhTyH8c/edit|Biome Tags]]",
        # Optional headers linked to condition pages
        "CanSeeSky": create_condition_link("canSeeSky", CONDITION_LINK_NAMESPACE),
        "Time": create_condition_link("timeRange", CONDITION_LINK_NAMESPACE, "Time"),
        "Weather": create_condition_link("weather", CONDITION_LINK_NAMESPACE, "Weather"), # General weather page
        "Key Item": create_condition_link("key_item", CONDITION_LINK_NAMESPACE, "Key Item"),
        "Nearby Blocks": create_condition_link("neededNearbyBlocks", CONDITION_LINK_NAMESPACE, "Nearby Blocks"),
        "Zygarde Cube": create_condition_link("zygarde_cube", CONDITION_LINK_NAMESPACE, "Zygarde Cube"),
        "Party Pokémon": create_condition_link("pokemon_in_party", CONDITION_LINK_NAMESPACE, "Party Pokémon"), # Use dedicated page name
        "Required Items": create_condition_link("item_requirement", CONDITION_LINK_NAMESPACE, "Required Items"),
        "Other Conditions": "Other Conditions" # No link for the header itself
    }
    content += "^ " + " ^ ".join(header_links.get(h, h) for h in final_headers) + " ^\n"


    # 3. Generate table rows for merged entries
    for i, entry in enumerate(merged_spawns):
        conditions = entry.get("condition", {}) or {}
        anticonditions = entry.get("anticondition", {}) or {}
        row_data = {}

        # --- Populate data for active columns ---

        # Context with link
        context_val = entry.get("context", " ")
        row_data["Context"] = f"[[{CONTEXT_LINK_NAMESPACE}:{context_val}|{context_val}]]" if context_val != " " else " "

        row_data["Level"] = entry.get("level", " ")
        row_data["Bucket"] = entry.get("bucket", " ")
        row_data["Biomes"] = format_condition_value_for_display("biomes", conditions.get("biomes"), wiki_namespace)

        # Weight + Multiplier
        weight_str = str(entry.get("weight", " "))
        if "weightMultiplier" in entry and entry["weightMultiplier"]:
            wm = entry["weightMultiplier"]
            mult = wm.get("multiplier", 1)
            wm_cond_str_parts = []
            for k, v in wm.get("condition", {}).items():
                 if v is not None:
                     cond_key_link = create_condition_link(k, CONDITION_LINK_NAMESPACE)
                     cond_val_fmt = format_condition_value_for_display(k, v, wiki_namespace)
                     wm_cond_str_parts.append(f"{cond_key_link}: {cond_val_fmt}")
            wm_cond_str = "; ".join(wm_cond_str_parts)
            weight_str += f" (x{mult}" + (f" if {wm_cond_str})" if wm_cond_str else ")")
        row_data["Weight"] = weight_str


        # --- Optional Columns ---
        if active_optional_headers["CanSeeSky"]:
            row_data["CanSeeSky"] = format_condition_value_for_display("canSeeSky", conditions.get("canSeeSky"), wiki_namespace)
        if active_optional_headers["Time"]:
            row_data["Time"] = format_condition_value_for_display("timeRange", conditions.get("timeRange"), wiki_namespace)
        if active_optional_headers["Key Item"]:
            row_data["Key Item"] = format_condition_value_for_display("key_item", conditions.get("key_item"), wiki_namespace)
        if active_optional_headers["Nearby Blocks"]:
            row_data["Nearby Blocks"] = format_condition_value_for_display("neededNearbyBlocks", conditions.get("neededNearbyBlocks"), wiki_namespace)

        # Weather
        if active_optional_headers["Weather"]:
            weather_parts = []
            is_raining = conditions.get("isRaining")
            is_thundering = conditions.get("isThundering")
            if is_raining is not None: weather_parts.append(f"{create_condition_link('isRaining', CONDITION_LINK_NAMESPACE)}: {is_raining}")
            if is_thundering is not None: weather_parts.append(f"{create_condition_link('isThundering', CONDITION_LINK_NAMESPACE)}: {is_thundering}")
            row_data["Weather"] = ", ".join(weather_parts) if weather_parts else " "

        # Zygarde Cube
        if active_optional_headers["Zygarde Cube"]:
            cells = conditions.get("required_cells")
            cores = conditions.get("required_cores")
            parts = []
            if cells is not None: parts.append(f"{cells} Cells")
            if cores is not None: parts.append(f"{cores} Cores")
            row_data["Zygarde Cube"] = " / ".join(parts) if parts else " "

        # Party Pokemon
        if active_optional_headers["Party Pokémon"]:
            req_list = conditions.get("pokemon_in_party_requirement", []) or []
            parts = []
            for req in req_list:
                species = req.get("species", "?")
                count = req.get("count", 1)
                # Link species name? Assumes pokemon pages exist.
                # parts.append(f"{count}x [[{wiki_namespace}:{species}|{species}]]")
                parts.append(f"{count}x {species}") # Simpler version without linking species
            row_data["Party Pokémon"] = " \\\\ ".join(parts) if parts else " "

        # Required Items
        if active_optional_headers["Required Items"]:
            req_list = conditions.get("item_requirement", []) or []
            parts = []
            for req in req_list:
                item_id = req.get("id", "?")
                count = req.get("count", 1)
                consume = req.get("consume", False) # Default to False if missing
                icon = get_item_icon_markup(item_id)
                item_link = f"[[{ITEM_LINK_NAMESPACE}#{item_id.replace(':','_')}|{item_id}]]"
                parts.append(f"{icon} {item_link} x{count} (Consumed: {consume})".strip())
            row_data["Required Items"] = " \\\\ ".join(parts) if parts else " "


        # Other Conditions & Anticonditions
        if active_optional_headers["Other Conditions"]:
            other_cond_list = []
            # Conditions
            for key, value in conditions.items():
                if key not in KNOWN_CONDITION_KEYS and value is not None:
                    cond_key_link = create_condition_link(key, CONDITION_LINK_NAMESPACE)
                    cond_val_fmt = format_condition_value_for_display(key, value, wiki_namespace)
                    other_cond_list.append(f"{cond_key_link}: {cond_val_fmt}")
            # Anticonditions
            if anticonditions:
                 other_cond_list.append("**NOT:**")
                 for key, value in anticonditions.items():
                     if value is not None:
                         cond_key_link = create_condition_link(key, CONDITION_LINK_NAMESPACE)
                         cond_val_fmt = format_condition_value_for_display(key, value, wiki_namespace)
                         other_cond_list.append(f"  * {cond_key_link}: {cond_val_fmt}")
            row_data["Other Conditions"] = " \\\\ ".join(other_cond_list) if other_cond_list else " "

        # --- Build row string based on active headers ---
        row = [row_data.get(h, " ") for h in final_headers]
        content += "| " + " | ".join(row) + " |\n"

    content += f"\n----\nData Version: {version}\n"
    content += "//Page last updated automatically.//"
    return content

def get_wiki_page_name(pokemon_name, pokedex_data, base_namespace):
    """Determines the DokuWiki page name."""
    pokedex_info = pokedex_data.get(pokemon_name, {})
    gen = pokedex_info.get('generation', 'unknown')
    safe_pokemon_name = re.sub(r'[^a-z0-9_]+', '_', pokemon_name.lower()).strip('_')
    if not safe_pokemon_name: safe_pokemon_name = f"unknown_{pokedex_info.get('pokedex', '???')}"
    return f"{base_namespace}:gen{gen}:{safe_pokemon_name}"

def wiki_login(url, user, password):
    """Connects to the DokuWiki API."""
    if not all([url, user, password]): logging.error("DokuWiki URL, User, and Password are required."); return None
    if url.endswith('/lib/exe/xmlrpc.php'): url = url[:-len('/lib/exe/xmlrpc.php')]
    if url.endswith('/'): url = url[:-1]

    try:
        logging.info(f"Attempting to connect to DokuWiki base URL: {url}")
        wiki = DokuWikiClient(url, user, password)
        version = wiki.dokuwiki_version
        logging.info(f"Successfully connected to DokuWiki version: {version}")
        return wiki
    except DokuWikiURLError as e: logging.error(f"DokuWiki URL Error ('{url}'): {e}", exc_info=True); return None
    except (DokuWikiXMLRPCProtocolError, DokuWikiXMLRPCError) as e: logging.error(f"DokuWiki XML-RPC Error: {e}", exc_info=True); return None
    except Exception as e: logging.error(f"Failed to connect/login to DokuWiki: {e}", exc_info=True); return None

def update_wiki_page(wiki, page_name, new_content, commit_hash=None):
    """Updates a DokuWiki page if content has changed."""
    current_content_str = ""
    try:
        current_content_str = wiki.page(page_name) or ""
        logging.debug(f"Current content fetched for {page_name}")
    except (DokuWikiXMLRPCError, DokuWikiXMLRPCProtocolError) as e:
        if hasattr(e, 'faultCode') and e.faultCode == 100: # page_not_found
            logging.info(f"Page {page_name} does not exist. Will create.")
            current_content_str = ""
        else: logging.error(f"XML-RPC Error fetching page {page_name}: {e}", exc_info=True); return False
    except Exception as e: logging.error(f"Unexpected Error fetching page {page_name}: {e}", exc_info=True); return False

    normalized_current = '\n'.join(line.rstrip() for line in current_content_str.replace('\r\n', '\n').splitlines()).strip()
    normalized_new = '\n'.join(line.rstrip() for line in new_content.replace('\r\n', '\n').splitlines()).strip()
    current_content_hash = hashlib.md5(normalized_current.encode('utf-8')).hexdigest()
    new_content_hash = hashlib.md5(normalized_new.encode('utf-8')).hexdigest()

    if new_content_hash != current_content_hash:
        logging.info(f"Content changed or page is new for {page_name}. Updating...")
        try:
            summary = "Automated spawn data update" + (f" (commit: {commit_hash[:7]})" if commit_hash else "")
            wiki.put_page(page_name, new_content, summary=summary, minor=False)
            logging.info(f"Successfully updated page: {page_name}")
            return True
        except (DokuWikiError, Exception) as e: logging.error(f"Error updating page {page_name}: {e}", exc_info=True); return False
    else:
        logging.info(f"No changes detected for {page_name}. Skipping.")
        return True


# --- Main Execution ---
def main():
    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(description="Update DokuWiki with Cobblemon spawn data.")
    parser.add_argument('--url', default=os.getenv('DW_URL'), help="Base DokuWiki URL (e.g., https://wiki.example.com). Env: DW_URL.")
    parser.add_argument('--user', default=os.getenv('DW_USER'), help="DokuWiki username. Env: DW_USER.")
    parser.add_argument('--password', default=os.getenv('DW_PASSWORD'), help="DokuWiki password. Env: DW_PASSWORD.")
    parser.add_argument('--pokedex-file', default='pokedex_data.json', type=Path, help="Path to pokedex_data.json.")
    parser.add_argument('--spawn-dir', default='data/cobblemon/spawn_pool_world', type=Path, help="Directory containing spawn JSON files.")
    parser.add_argument('--namespace', default='mythsandlegends:datapack:spawn_pool_world', help="Base DokuWiki namespace for spawn pages.")
    parser.add_argument('--version-file', default='version.txt', type=Path, help="Path to file containing data version string.")
    parser.add_argument('--commit-hash', default=os.getenv('COMMIT_HASH'), help="Git commit hash (optional, for edit summary).")
    args = parser.parse_args()

    # --- Validation & Setup ---
    if not all([args.url, args.user, args.password]): parser.error("URL, user, and password are required (use args or env vars)."); return
    if not args.pokedex_file.is_file(): parser.error(f"Pokedex file not found: {args.pokedex_file}"); return
    if not args.spawn_dir.is_dir(): parser.error(f"Spawn directory not found: {args.spawn_dir}"); return

    # Read version file
    try:
        data_version = args.version_file.read_text(encoding='utf-8').strip()
        if not data_version: logging.warning(f"Version file '{args.version_file}' is empty."); data_version = "Unknown"
        logging.info(f"Using data version: {data_version}")
    except FileNotFoundError: logging.error(f"Version file not found: {args.version_file}. Using 'Unknown'."); data_version = "Unknown"
    except Exception as e: logging.error(f"Error reading version file {args.version_file}: {e}. Using 'Unknown'."); data_version = "Unknown"

    # Load Pokedex data
    logging.info(f"Loading Pokedex data from: {args.pokedex_file}")
    pokedex_data = load_json_file(args.pokedex_file)
    if not pokedex_data: logging.error("Failed to load Pokedex data. Exiting."); return

    # --- Find and Process Spawn Files ---
    spawn_files = list(args.spawn_dir.rglob('*.json')) # Use rglob for recursive search
    logging.info(f"Found {len(spawn_files)} potential spawn files in {args.spawn_dir} (recursive)")
    pokemon_spawns = defaultdict(list)

    for filepath in spawn_files:
        logging.debug(f"Processing spawn file: {filepath}")
        data = load_json_file(filepath)
        if data and data.get("enabled", True): # Consider enabled=True if key missing
            spawns_in_file = data.get("spawns", [])
            if not isinstance(spawns_in_file, list): logging.warning(f"Invalid 'spawns' format in {filepath}. Skipping."); continue

            for i, spawn_detail in enumerate(spawns_in_file):
                if not isinstance(spawn_detail, dict): logging.warning(f"Spawn entry #{i+1} in {filepath} is not a dict. Skipping."); continue
                pokemon_name = spawn_detail.get("pokemon")
                if pokemon_name and isinstance(pokemon_name, str):
                    pokemon_name = pokemon_name.lower().strip()
                    if not re.match(r'^[a-z0-9_:-]+$', pokemon_name): logging.warning(f"Skipping spawn with invalid name '{pokemon_name}' in {filepath}"); continue
                    pokemon_spawns[pokemon_name].append(spawn_detail)
                else: logging.warning(f"Spawn entry #{i+1} in {filepath} missing 'pokemon' key or invalid type.")
        elif not data: logging.warning(f"Could not read/parse {filepath}. Skipping.")

    if not pokemon_spawns: logging.warning("No enabled Pokémon spawn data found."); return

    # --- Wiki Interaction ---
    wiki = wiki_login(args.url, args.user, args.password)
    if not wiki: logging.error("Could not log in to DokuWiki. Exiting."); exit(1)

    logging.info(f"Processing {len(pokemon_spawns)} unique Pokémon for wiki updates.")
    success_count, fail_count, processed_count = 0, 0, 0

    for pokemon_name, spawns in pokemon_spawns.items():
        processed_count += 1
        logging.info(f"Processing {pokemon_name} ({processed_count}/{len(pokemon_spawns)})...")

        if not pokemon_name in pokedex_data:
             logging.warning(f"'{pokemon_name}' not found in pokedex data. Skipping wiki page.")
             continue # Don't count as failure, just skip

        page_name = get_wiki_page_name(pokemon_name, pokedex_data, args.namespace)
        logging.debug(f"Target Wiki Page: {page_name}")

        try:
            wiki_content = generate_wiki_content(pokemon_name, pokedex_data, spawns, data_version, args.namespace)
            if update_wiki_page(wiki, page_name, wiki_content, args.commit_hash):
                success_count += 1
            else:
                fail_count += 1
        except Exception as e:
            logging.error(f"Critical error processing {pokemon_name} (Page: {page_name}): {e}", exc_info=True)
            fail_count += 1

    # --- Finish ---
    logging.info(f"Wiki update finished. Success/NoChange: {success_count}, Failed: {fail_count}")
    if fail_count > 0: logging.error(f"{fail_count} errors occurred during wiki update."); exit(1)

if __name__ == "__main__":
    main()