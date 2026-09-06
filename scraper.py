import subprocess
import json
import os

def get_nba_content():
    # Busquem especificament amb paraules que forcin verticalitat
    query = "nba basketball edits high quality vertical #shorts"
    
    # Comandament amb filtres tècnics: durada curta i que l'alçada sigui major que l'amplada
    cmd = [
        'yt-dlp',
        f'ytsearch30:{query}',
        '--match-filter', 'duration <= 60 & width < height', 
        '--dump-single-json',
        '--flat-playlist',
        '--extractor-args', 'youtube:player_client=ios', # Enganyem YouTube (ios bypass)
    ]
    
    print(f"🔍 Buscant vídeos verticals de l'NBA a YouTube...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    try:
        data = json.loads(result.stdout)
    except Exception as e:
        print(f"❌ Error al llegir JSON de YouTube: {e}")
        return

    # Gestionar carpetes i fitxers
    os.makedirs('data', exist_ok=True)
    processed_path = 'data/processed.json'
    queue_path = 'data/queue.json'

    if os.path.exists(processed_path):
        with open(processed_path, 'r') as f:
            processed = json.load(f)
    else:
        processed = []

    queue = []
    for entry in data.get('entries', []):
        if entry['id'] not in processed:
            queue.append({
                "id": entry['id'],
                "url": f"https://www.youtube.com/watch?v={entry['id']}",
                "title": entry['title']
            })
    
    # Guardem els 20 millors a la cua
    with open(queue_path, 'w') as f:
        json.dump(queue[:20], f, indent=4)
    
    print(f"✅ Cua generada amb {len(queue[:20])} vídeos verticals nous.")

if __name__ == "__main__":
    get_nba_content()
