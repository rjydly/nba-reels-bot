import subprocess
import json
import os
import csv
import random
import requests

QUERIES_FILE = 'queries.csv'
QUEUE_FILE = 'data/queue.json'
PROCESSED_FILE = 'data/processed.json'

def load_queries():
    if not os.path.exists(QUERIES_FILE):
        return ["nba 4k vertical edit #shorts", "basketball edit phonk #shorts"]
    with open(QUERIES_FILE, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return [row['query'].strip() for row in reader if row.get('query')]

def is_real_vertical_short(video_id):
    """
    Comprova si el vídeo és realment un Short vertical.
    Si és un vídeo normal de YouTube, la URL redirigeix cap a /watch?v=...
    Si és un Short de veritat, la URL es manté a /shorts/...
    """
    url = f"https://www.youtube.com/shorts/{video_id}"
    try:
        # Cookie de consentiment de Google per evitar el bloqueig GDPR a Europa
        cookies = {"SOCS": "CAESEwgDEgk2OTQ0NTQ1OTIaAmVuIAEaBgiA_LyaBg"}
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        
        r = requests.get(url, cookies=cookies, headers=headers, allow_redirects=True, timeout=6)
        
        # Si la URL final manté /shorts/, és un Short 100% garantit
        if "/shorts/" in r.url:
            return True
        return False
    except:
        return False

def get_nba_content():
    all_queries = load_queries()
    # Triem 5 temàtiques a l'atzar
    selected_queries = random.sample(all_queries, min(5, len(all_queries)))
    
    os.makedirs('data', exist_ok=True)
    processed = []
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, 'r', encoding='utf-8') as f:
            processed = json.load(f)

    new_queue = []

    for query in selected_queries:
        print(f"\n🔍 Cercant edits curts per: '{query}'...")
        
        # FILTRE CRUCIAL: Només vídeos d'entre 5 i 60 segons!
        cmd = [
            'yt-dlp',
            f'ytsearch12:{query}',
            '--match-filter', 'duration <= 60 & duration >= 5',
            '--dump-single-json',
            '--flat-playlist',
            '--extractor-args', 'youtube:player_client=ios'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        try:
            data = json.loads(result.stdout)
            for entry in data.get('entries', []):
                vid_id = entry.get('id')
                if not vid_id or vid_id in processed or any(v['id'] == vid_id for v in new_queue):
                    continue

                title = entry.get('title', 'Basketball Edit')
                
                # Comprovació en viu contra YouTube
                if is_real_vertical_short(vid_id):
                    print(f"  ✅ SHORT VERTICAL CONFIRMAT: {title}")
                    new_queue.append({
                        "id": vid_id,
                        "url": f"https://www.youtube.com/watch?v={vid_id}",
                        "title": title
                    })
                else:
                    print(f"  ❌ Descartat (és vídeo horitzontal normal): {title}")

                if len(new_queue) >= 20:
                    break
        except Exception as e:
            print(f"⚠️ Error analitzant resultats: {e}")

        if len(new_queue) >= 20:
            break

    final_queue = new_queue[:20]
    with open(QUEUE_FILE, 'w', encoding='utf-8') as f:
        json.dump(final_queue, f, indent=4)
    
    print(f"\n🎯 CUA GENERADA: {len(final_queue)} Shorts verticals reals llestos per publicar.")

if __name__ == "__main__":
    get_nba_content()
