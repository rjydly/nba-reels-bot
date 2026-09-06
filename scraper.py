import subprocess
import json
import os
import csv
import random

QUERIES_FILE = 'queries.csv'
QUEUE_FILE = 'data/queue.json'
PROCESSED_FILE = 'data/processed.json'

def load_queries():
    if not os.path.exists(QUERIES_FILE):
        return ["nba basketball edits #shorts", "euroleague basketball highlights #shorts"]
    with open(QUERIES_FILE, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return [row['query'].strip() for row in reader if row.get('query')]

def get_nba_content():
    all_queries = load_queries()
    # Triem 4 temes diferents a l'atzar per tenir varietat d'estils i equips
    selected_queries = random.sample(all_queries, min(4, len(all_queries)))
    
    os.makedirs('data', exist_ok=True)
    processed = []
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, 'r', encoding='utf-8') as f:
            processed = json.load(f)

    new_queue = []

    for query in selected_queries:
        print(f"🔍 Cercant temàtica: '{query}'...")
        # Demanem 8 resultats per query per poder descartar si ja estan vistos
        cmd = [
            'yt-dlp',
            f'ytsearch8:{query}',
            '--match-filter', 'duration <= 60 & width < height',
            '--dump-single-json',
            '--flat-playlist',
            '--extractor-args', 'youtube:player_client=ios'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        try:
            data = json.loads(result.stdout)
            for entry in data.get('entries', []):
                vid_id = entry.get('id')
                if vid_id and vid_id not in processed and not any(v['id'] == vid_id for v in new_queue):
                    new_queue.append({
                        "id": vid_id,
                        "url": f"https://www.youtube.com/watch?v={vid_id}",
                        "title": entry.get('title', 'Basketball Reel')
                    })
                if len(new_queue) >= 20:
                    break
        except Exception as e:
            print(f"⚠️ Error processant resultats de la query: {e}")

        if len(new_queue) >= 20:
            break

    # Guardem els 20 vídeos
    final_queue = new_queue[:20]
    with open(QUEUE_FILE, 'w', encoding='utf-8') as f:
        json.dump(final_queue, f, indent=4)
    
    print(f"✅ Cua completada amb {len(final_queue)} vídeos diferents.")

if __name__ == "__main__":
    get_nba_content()
