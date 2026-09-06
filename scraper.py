import os
import sys
import json
import csv
import random
from apify_client import ApifyClient

QUERIES_FILE = 'queries.csv'
QUEUE_FILE = 'data/queue.json'
PROCESSED_FILE = 'data/processed.json'
BACKUP_FILE = 'data/backup_reels.csv'
APIFY_TOKEN = os.getenv("APIFY_TOKEN")

def load_queries():
    if not os.path.exists(QUERIES_FILE):
        return ["nba 4k vertical edit", "stephen curry phonk edit"]
    with open(QUERIES_FILE, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return [row['query'].strip() for row in reader if row.get('query')]

def sync_to_backup_csv(new_backups):
    """Guarda els vídeos de reserva a backup_reels.csv mantenint l'ordre per views."""
    existing_rows = []
    seen_ids = set()

    if os.path.exists(BACKUP_FILE):
        with open(BACKUP_FILE, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_rows.append(row)
                seen_ids.add(row.get('id'))

    for item in new_backups:
        if item['id'] not in seen_ids:
            existing_rows.append({
                "id": item['id'],
                "url": item['url'],
                "title": item['title'],
                "views": item['views'],
                "status": ""
            })
            seen_ids.add(item['id'])

    try:
        existing_rows.sort(key=lambda x: int(x.get('views', 0)), reverse=True)
    except:
        pass

    with open(BACKUP_FILE, mode='w', newline='', encoding='utf-8') as f:
        fieldnames = ["id", "url", "title", "views", "status"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(existing_rows)

    print(f"💾 {len(new_backups)} vídeos guardats a '{BACKUP_FILE}' (Total reserva: {len(existing_rows)})")

def get_nba_content():
    if not APIFY_TOKEN:
        print("❌ Error: Falta el secret APIFY_TOKEN."); sys.exit(1)

    os.makedirs('data', exist_ok=True)
    all_queries = load_queries()
    
    selected_queries = random.sample(all_queries, min(2, len(all_queries)))
    print(f"🔍 Consultes per a Apify: {selected_queries}")

    client = ApifyClient(APIFY_TOKEN)

    run_input = {
        "searchQueries": selected_queries,
        "maxResults": 0,
        "maxResultsShorts": 13,
        "maxResultStreams": 0,
        "downloadSubtitles": False,
        "aiVideoDescription": False,
        "aiVideoSummary": False,
        "sortingOrder": "relevance"
    }

    print("🚀 Demanant exactament 25 vídeos a Apify...")
    # Crida neta sense arguments no suportats
    run = client.actor("streamers/youtube-scraper").call(run_input=run_input)

    processed = []
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, 'r', encoding='utf-8') as f:
            try:
                processed = json.load(f)
            except:
                processed = []

    dataset_id = getattr(run, "default_dataset_id", None) or getattr(run, "defaultDatasetId", None)
    if not dataset_id and isinstance(run, dict):
        dataset_id = run.get("defaultDatasetId")

    candidates = []
    for item in client.dataset(dataset_id).iterate_items():
        vid_id = item.get("id") if isinstance(item, dict) else getattr(item, "id", None)
        item_type = item.get("type") if isinstance(item, dict) else getattr(item, "type", None)
        item_url = item.get("url") if isinstance(item, dict) else getattr(item, "url", None)
        title = item.get("title", "NBA Edit") if isinstance(item, dict) else getattr(item, "title", "NBA Edit")
        views = item.get("viewCount", 0) if isinstance(item, dict) else getattr(item, "viewCount", 0)

        is_short = item_type == "shorts" or (item_url and "/shorts/" in item_url)

        if vid_id and is_short and vid_id not in processed:
            candidates.append({
                "id": vid_id,
                "url": item_url or f"https://www.youtube.com/watch?v={vid_id}",
                "title": title,
                "views": int(views or 0)
            })

    unique_candidates = []
    seen = set()
    for c in candidates:
        if c['id'] not in seen:
            seen.add(c['id'])
            unique_candidates.append(c)

    total_batch = unique_candidates[:25]
    total_batch.sort(key=lambda x: x['views'], reverse=True)

    today_queue = total_batch[:20]
    with open(QUEUE_FILE, 'w', encoding='utf-8') as f:
        json.dump(today_queue, f, indent=4)

    backup_reels = total_batch[20:]
    if backup_reels:
        sync_to_backup_csv(backup_reels)

    print(f"\n🎯 CUA DEL DIA: {len(today_queue)} vídeos desats a '{QUEUE_FILE}'.")
    print(f"📦 RESERVA: {len(backup_reels)} vídeos enviats a '{BACKUP_FILE}'.")

if __name__ == "__main__":
    get_nba_content()
