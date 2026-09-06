import subprocess
import json
import os

def get_nba_content():
    query = "nba basketball edits high quality #shorts"
    # Busquem 20 vídeos, filtrant que siguin curts (<60s)
    cmd = [
        'yt-dlp',
        f'ytsearch20:{query}',
        '--match-filter', 'duration <= 60',
        '--dump-single-json',
        '--flat-playlist'
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(result.stdout)
    
    if os.path.exists('data/processed.json'):
        with open('data/processed.json', 'r') as f:
            processed = json.load(f)
    else:
        processed = []

    queue = []
    for entry in data['entries']:
        if entry['id'] not in processed:
            queue.append({
                "id": entry['id'],
                "url": f"https://www.youtube.com/watch?v={entry['id']}",
                "title": entry['title']
            })
    
    with open('data/queue.json', 'w') as f:
        json.dump(queue, f, indent=4)
    print(f"✅ Cua guardada amb {len(queue)} vídeos.")

if __name__ == "__main__":
    get_nba_content()
