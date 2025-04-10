import os
import json
import glob
import sys
from collections import defaultdict
from dokuwikixmlrpc import DokuWikiClient # Ensure this library is installed

# --- Configuration ---
POKEDEX_DATA_PATH = 'pokedex_data.json'
SPAWN_DATA_DIR = 'data/cobblemon/spawn_pool_world/'
WIKI_NAMESPACE_PREFIX = "mythsandlegends:datapack:spawn_pool_world:"
ITEM_PAGE_NAMESPACE = "mythsandlegends" # Namespace where item icons are stored
ITEM_PAGE_ID = f"{ITEM_PAGE_NAMESPACE}:items" # The page listing items

# Mapping for key item identifiers to their icon filenames (derived from your item list example)
# Format: 'mythsandlegends:<item_id>': '<icon_filename>.png'
ITEM_ICONS = {
    "mythsandlegends:adamant_orb": "adamant_orb.png",
    "mythsandlegends:aurora_ticket": "aurora_ticket.png",
    "mythsandlegends:azure_flute": "azure_flute.png",
    "mythsandlegends:blue_orb": "blue_orb.png",
    "mythsandlegends:bonus_disk": "bonus_disk.png",
    "mythsandlegends:clear_bell": "clear_bell.png",
    "mythsandlegends:dna_splicer": "dna_splicer.png",
    "mythsandlegends:eon_ticket": "eon_ticket.png",
    "mythsandlegends:griseous_orb": "griseous_orb.png",
    "mythsandlegends:gs_ball": "gs_ball.png",
    "mythsandlegends:jade_orb": "jade_orb.png",
    "mythsandlegends:liberty_pass": "liberty_pass.png",
    "mythsandlegends:lustrous_orb": "lustrous_orb.png",
    "mythsandlegends:member_card": "member_card.png",
    "mythsandlegends:oaks_letter": "oaks_letter.png",
    "mythsandlegends:old_sea_map": "old_sea_map.png",
    "mythsandlegends:red_orb": "red_orb.png",
    "mythsandlegends:rusted_shield": "rusted_shield.png",
    "mythsandlegends:rusted_sword": "rusted_sword.png",
    "mythsandlegends:tidal_bell": "tidal_bell.png",
    "mythsandlegends:dr_fujis_diary": "dr_fujis_diary.png",
    "mythsandlegends:rainbow_wing": "rainbow_wing.png",
    "mythsandlegends:scarlet_book": "scarlet_book.png",
    "mythsandlegends:silver_wing": "silver_wing.png",
    "mythsandlegends:violet_book": "violet_book.png",
    "mythsandlegends:cocoon_of_destruction": "cocoon_of_destruction.png",
    "mythsandlegends:sapling_of_life": "sapling_of_life.png",
    "mythsandlegends:mystery_box": "mystery_box.png",
    "mythsandlegends:reveal_glass": "reveal_glass.png",
    "mythsandlegends:dark_stone": "dark_stone.png",
    "mythsandlegends:light_stone": "light_stone.png",
    "mythsandlegends:teal_mask": "teal_mask.png",
    "mythsandlegends:sun_flute": "sun_flute.png",
    "mythsandlegends:moon_flute": "moon_flute.png",
    "mythsandlegends:lunar_feather": "lunar_feather.png", # Assuming this is Lunar Wing
    "mythsandlegends:magma_stone": "magma_stone.png",
    "mythsandlegends:diancies_crown": "diancies_crown.png",
    "mythsandlegends:fini_totem": "fini_totem.png",
    "mythsandlegends:genesect_drive": "genesect_drive.png",
    "mythsandlegends:grassland_blade": "grassland_blade.png",
    "mythsandlegends:hoopa_ring": "hoopa_ring.png",
    "mythsandlegends:ironwill_sword": "ironwill_sword.png",
    "mythsandlegends:koko_totem": "koko_totem.png",
    "mythsandlegends:lele_totem": "lele_totem.png",
    "mythsandlegends:lillies_bag": "lillies_bag.png",
    "mythsandlegends:meloetta_headset": "meloetta_headset.png",
    "mythsandlegends:necro_prism": "necro_prism.png",
    "mythsandlegends:prison_bottle": "prison_bottle.png",
    "mythsandlegends:sacred_sword": "sacred_sword.png",
    "mythsandlegends:steam_valve": "steam_valve.png",
    "mythsandlegends:type_null_mask": "type_null_mask.png",
    "mythsandlegends:antique_pokeball": "antique_pokeball.png",
    "mythsandlegends:eternatus_core": "eternatus_core.png",
    "mythsandlegends:kubfus_band": "kubfus_band.png",
    "mythsandlegends:marshadow_hood": "marshadow_hood.png",
    "mythsandlegends:plasma_tablet": "plasma_tablet.png",
    "mythsandlegends:prismatic_shell": "prismatic_shell.png",
    "mythsandlegends:reins_of_unity": "reins_of_unity.png",
    "mythsandlegends:scaly_tablet": "scaly_tablet.png",
    "mythsandlegends:scroll_of_water": "scroll_of_water.png",
    "mythsandlegends:soul_heart": "soul_heart.png",
    "mythsandlegends:zarudes_cape": "zarudes_cape.png",
    "mythsandlegends:zeraoras_thunderclaw": "zeraoras_thunderclaw.png",
    "mythsandlegends:ancient_tablet": "ancient_tablet.png",
    "mythsandlegends:mythical_pecha_berry": "mythical_pecha_berry.png",
    "mythsandlegends:scroll_of_darkness": "scroll_of_darkness.png",
    "mythsandlegends:azelf_fang": "azelf_fang.png",
    "mythsandlegends:mesprit_plume": "mesprit_plume.png",
    "mythsandlegends:stone_tablet": "stone_tablet.png",
    "mythsandlegends:uxie_claw": "uxie_claw.png",
    "mythsandlegends:ice_tablet": "ice_tablet.png",
    "mythsandlegends:steel_tablet": "steel_tablet.png",
    "mythsandlegends:bulu_totem": "bulu_totem.png",
    "mythsandlegends:cavern_shield": "cavern_shield.png",
    "mythsandlegends:iceroot_carrot": "iceroot_carrot.png",
    "mythsandlegends:shaderoot_carrot": "shaderoot_carrot.png",
    "mythsandlegends:binding_mochi": "binding_mochi.png",
    "mythsandlegends:cornerstone_mask": "cornerstone_mask.png",
    "mythsandlegends:hearthflame_mask": "hearthflame_mask.png",
    "mythsandlegends:wellspring_mask": "wellspring_mask.png",
    # Add any other key items and their icons here
}

# Conditions to specifically link to the item page
LINKABLE_ITEM_CONDITIONS = ["key_item"] # Add others if needed e.g., "held_item"

# --- Helper Functions ---

def load_json(filepath):
    """Loads JSON data from a file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: File not found - {filepath}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error: Could not decode JSON from {filepath} - {e}")
        return None
    except Exception as e:
        print(f"Error: An unexpected error occurred loading {filepath} - {e}")
        return None

def get_dokuwiki_client():
    """Initializes and returns the DokuWiki client."""
    api_url = os.getenv('DOKUWIKI_API_URL')
    user = os.getenv('DOKUWIKI_USER')
    password = os.getenv('DOKUWIKI_PASSWORD')

    if not all([api_url, user, password]):
        print("Error: Missing DokuWiki credentials/URL in environment variables.")
        print("Please set DOKUWIKI_API_URL, DOKUWIKI_USER, and DOKUWIKI_PASSWORD.")
        sys.exit(1) # Exit if credentials are missing

    try:
        # Assuming the URL includes '/lib/exe/xmlrpc.php' or similar
        # If not, you might need to adjust the URL or library usage
        client = DokuWikiClient(api_url, user, password, verbose=False)
        # Test connection
        client.dokuwiki.getVersion()
        print("Successfully connected to DokuWiki API.")
        return client
    except Exception as e:
        print(f"Error: Could not connect to DokuWiki API at {api_url} - {e}")
        sys.exit(1) # Exit if connection fails

def format_condition_value(key, value):
    """Formats a single condition key-value pair for DokuWiki."""
    if isinstance(value, list):
        # Format lists (like biomes, neededNearbyBlocks)
        formatted_items = [f"`{item}`" for item in value] # Wrap items in backticks
        return f"[{', '.join(formatted_items)}]"
    elif isinstance(value, bool):
        return str(value).lower()
    elif isinstance(value, (int, float, str)):
        if key in LINKABLE_ITEM_CONDITIONS:
            item_id = str(value)
            icon = ITEM_ICONS.get(item_id)
            # Link to the item page anchor, display item_id and icon
            link_target = f"{ITEM_PAGE_ID}#{item_id.replace(':', '_')}" # Create anchor link target
            icon_markup = f"{{{{{ITEM_PAGE_NAMESPACE}:{icon}?nolink&16}}}}" if icon else ""
            return f"[[{link_target}|`{item_id}` {icon_markup}]]"
        else:
            # Simple string/number value
            return f"`{value}`" # Wrap in backticks
    else:
        # Fallback for unexpected types
        return f"`{str(value)}`"

def format_conditions(conditions):
    """Formats the condition dictionary into a DokuWiki string."""
    if not conditions:
        return "None"

    lines = []
    for key, value in sorted(conditions.items()):
        # Skip empty/null values if desired (optional)
        # if not value:
        #    continue
        formatted_val = format_condition_value(key, value)
        lines.append(f"  * **{key}:** {formatted_val}")
    return "\n".join(lines) if lines else "None"

def generate_wiki_content(pokemon_name, gen_info, spawn_details_list):
    """Generates the full DokuWiki page content for a single Pokémon."""
    # --- Page Header ---
    title = pokemon_name.replace('-', ' ').replace('_', ' ').title()
    content = [f"====== Spawn Data: {title} ======\n"]

    # --- Basic Info ---
    if gen_info:
        content.append(f"**Pokédex Number:** {gen_info.get('pokedex', 'N/A')}")
        content.append(f"**Generation:** {gen_info.get('generation', 'N/A')}\n")
    else:
        content.append("**Pokédex Number:** Unknown")
        content.append("**Generation:** Unknown\n")

    content.append("This page details the natural spawning conditions for this Pokémon based on the `mythsandlegends` datapack.\n")

    # --- Spawn Table Header ---
    content.append("^ Spawn ID ^ Level ^ Bucket ^ Weight ^ Context ^ Presets ^ Conditions ^")

    # --- Spawn Table Rows ---
    # Group similar spawns (basic grouping by non-condition fields)
    grouped_spawns = defaultdict(list)
    for spawn in spawn_details_list:
        # Create a tuple key based on fields we want to group by
        group_key = (
            spawn.get('level', 'N/A'),
            spawn.get('bucket', 'N/A'),
            spawn.get('context', 'N/A'),
            tuple(sorted(spawn.get('presets', []))), # Use tuple for list hashing
            # Add other non-varying conditions here if needed for grouping
        )
        grouped_spawns[group_key].append(spawn)

    # Generate rows, potentially merging conditions for grouped spawns
    for group_key, spawns_in_group in grouped_spawns.items():
        # Use the first spawn for common details
        first_spawn = spawns_in_group[0]
        spawn_id = first_spawn.get('id', 'N/A') # Might list multiple if truly needed
        level = first_spawn.get('level', 'N/A')
        bucket = first_spawn.get('bucket', 'N/A')
        weight = first_spawn.get('weight', 'N/A')
        context = first_spawn.get('context', 'N/A')
        presets = ', '.join(f"`{p}`" for p in first_spawn.get('presets', [])) or 'N/A'

        # --- Condition Merging (Example: Merge biomes and key_items) ---
        all_conditions_str = []
        # Collect all unique conditions across the group
        merged_conditions = defaultdict(set)
        all_raw_conditions = [] # Store full condition dicts for detailed view if needed

        for spawn in spawns_in_group:
             raw_cond = spawn.get('condition', {})
             all_raw_conditions.append(raw_cond)
             for key, value in raw_cond.items():
                 if isinstance(value, list):
                     merged_conditions[key].update(value) # Add all items from lists
                 else:
                     merged_conditions[key].add(value) # Add single items

        # Format merged conditions
        formatted_merged_conditions = []
        for key, value_set in sorted(merged_conditions.items()):
             # Convert set back to list for consistent formatting
             value = sorted(list(value_set))
             if len(value) == 1:
                 value = value[0] # Use single value if only one item

             formatted_val = format_condition_value(key, value)
             formatted_merged_conditions.append(f"  * **{key}:** {formatted_val}")

        condition_str = "\n".join(formatted_merged_conditions) if formatted_merged_conditions else "None"
        # --- End Condition Merging ---

        # Add Weight Multiplier if present (only shows first one if multiple in group)
        if 'weightMultiplier' in first_spawn:
            multiplier_data = first_spawn['weightMultiplier']
            multiplier = multiplier_data.get('multiplier', 'N/A')
            multiplier_cond = format_conditions(multiplier_data.get('condition', {}))
            condition_str += f"\n  * **weightMultiplier:**\n    * multiplier: `{multiplier}`\n    * condition:\n{multiplier_cond.replace('  *', '      *')}" # Indent multiplier conditions


        # If multiple spawns were grouped, indicate it (optional)
        if len(spawns_in_group) > 1:
            spawn_id += f" (and {len(spawns_in_group) - 1} similar)"
            # Alternative: list all IDs: spawn_id = ', '.join(f"`{s.get('id', 'N/A')}`" for s in spawns_in_group)

        content.append(f"| `{spawn_id}` | `{level}` | `{bucket}` | `{weight}` | `{context}` | {presets} | {condition_str} |")

    return "\n".join(content)

def update_wiki_page(client, page_id, content, summary="Automated spawn data update"):
    """Updates a DokuWiki page with the given content."""
    try:
        print(f"Attempting to update page: {page_id}")
        # Use putPage to create or update the page
        client.dokuwiki.putPage(page_id, content, {'sum': summary})
        print(f"Successfully updated page: {page_id}")
        return True
    except Exception as e:
        print(f"Error: Failed to update page {page_id} - {e}")
        # You might want to check the specific error type from the library
        # e.g., if it's a permission error, authentication error etc.
        return False

# --- Main Execution ---

if __name__ == "__main__":
    print("Starting DokuWiki update process...")

    # 1. Initialize DokuWiki Client
    wiki_client = get_dokuwiki_client()

    # 2. Load Pokedex Data
    pokedex_data = load_json(POKEDEX_DATA_PATH)
    if pokedex_data is None:
        print("Error: Could not load pokedex data. Exiting.")
        sys.exit(1)

    # 3. Find and Process Spawn Files
    spawn_files = glob.glob(os.path.join(SPAWN_DATA_DIR, '*.json'))
    if not spawn_files:
        print(f"Warning: No JSON files found in {SPAWN_DATA_DIR}")
        sys.exit(0) # Exit cleanly if no files found

    pokemon_spawns = defaultdict(list)
    print(f"Found {len(spawn_files)} spawn files to process.")

    for filepath in spawn_files:
        spawn_data = load_json(filepath)
        if spawn_data is None or not spawn_data.get('enabled', False):
            # print(f"Skipping disabled or invalid file: {filepath}")
            continue

        spawns_list = spawn_data.get('spawns', [])
        for spawn_detail in spawns_list:
            pokemon_name = spawn_detail.get('pokemon')
            if pokemon_name:
                # Clean up name if needed (e.g., remove potential prefixes)
                if ':' in pokemon_name:
                   pokemon_name = pokemon_name.split(':')[-1]
                pokemon_spawns[pokemon_name].append(spawn_detail)
            else:
                print(f"Warning: Spawn entry in {filepath} is missing 'pokemon' field.")

    # 4. Generate and Update Wiki Pages
    print(f"\nProcessing {len(pokemon_spawns)} unique Pokémon...")
    updated_pages = 0
    failed_pages = 0

    for pokemon_name, spawn_details in pokemon_spawns.items():
        gen_info = pokedex_data.get(pokemon_name)
        generation = str(gen_info.get('generation', 'Unknown')) if gen_info else 'Unknown'

        # Construct page ID: mythsandlegends:datapack:spawn_pool_world:<Generation>:<PokemonName>
        # Ensure names are valid for DokuWiki (lowercase, underscores maybe)
        safe_pokemon_name = pokemon_name.lower().replace('-', '_')
        page_id = f"{WIKI_NAMESPACE_PREFIX}{generation}:{safe_pokemon_name}"

        print(f"\nGenerating content for: {pokemon_name} (Page ID: {page_id})")
        wiki_content = generate_wiki_content(pokemon_name, gen_info, spawn_details)

        # Update the page
        if update_wiki_page(wiki_client, page_id, wiki_content):
             updated_pages += 1
        else:
             failed_pages += 1

    print("\n--- Update Summary ---")
    print(f"Successfully updated pages: {updated_pages}")
    print(f"Failed page updates: {failed_pages}")

    if failed_pages > 0:
        sys.exit(1) # Indicate failure in the workflow run
    else:
        print("Wiki update process completed successfully.")
        sys.exit(0) # Indicate success