import os
import json
import xmlrpc.client

def fetch_json_files():
    """Fetch all JSON files in the specified directory."""
    json_files = []
    for root, dirs, files in os.walk('data/cobblemon/spawn_pool_world'):
        for file in files:
            if file.endswith('.json'):
                json_files.append(os.path.join(root, file))
    return json_files

def parse_json_file(file_path):
    """Parse a JSON file and return the data."""
    with open(file_path, 'r') as f:
        data = json.load(f)
    return data

def format_data_for_dokuwiki(spawn):
    """Format spawn data into DokuWiki syntax."""
    pokemon_name = spawn['pokemon'].capitalize()
    content = f"===== {pokemon_name} =====\n"
    content += f"**Species**: {pokemon_name}\n"
    content += f"**Presets**: {', '.join(spawn['presets'])}\n"
    content += f"**Context**: {spawn['context']}\n"
    content += f"**Spawn Bucket**: {spawn['bucket']}\n"
    content += f"**Encounter Level Range**: {spawn['level']}\n"
    content += f"**Weight**: {spawn['weight']}\n"
    content += "**Biomes**:\n"
    for biome in spawn['condition']['biomes']:
        content += f"  * {biome}\n"
    if 'key_item' in spawn['condition']:
        key_item = spawn['condition']['key_item'].replace('_', ' ').title()
        content += f"**Key Item**: {key_item}\n"
    content += "**Additional Conditions**:\n"
    for key, value in spawn['condition'].items():
        if key != 'biomes' and key != 'key_item':
            content += f"  * {key}: {value}\n"
    return content

def update_dokuwiki_page(pokemon, content):
    """Update the DokuWiki page with the formatted content."""
    url = os.getenv('DOKUWIKI_API_URL')
    user = os.getenv('DOKUWIKI_USER')
    password = os.getenv('DOKUWIKI_PASSWORD')
    server = xmlrpc.client.ServerProxy(url)
    token = server.dokuwiki.login(user, password)
    page = f'pokedex:{pokemon.lower()}'
    summary = 'Automated update from GitHub repository'
    server.wiki.putPage(page, content, {'sum': summary})

def main():
    """Main function to fetch, parse, format, and update DokuWiki pages."""
    json_files = fetch_json_files()
    for file_path in json_files:
        data = parse_json_file(file_path)
        for spawn in data.get('spawns', []):
            content = format_data_for_dokuwiki(spawn)
            update_dokuwiki_page(spawn['pokemon'], content)

if __name__ == "__main__":
    main()
