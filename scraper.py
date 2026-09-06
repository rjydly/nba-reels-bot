import os
import sys
import json
import csv
import random
from apify_client import ApifyClient

QUERIES_FILE = 'queries.csv'
QUEUE_FILE = 'data/queue.json'
PROCESSED_FILE = 'data/processed.json'
APIFY_TOKEN = os.getenv("APIFY_TOKEN")

def load_queries():
    if not os.path.exists(QUERIES_FILE):
        return ["nba 4k vertical edit", "stephen curry phonk edit", "basketball aesthetic edit"]
    with open(QUERIES_FILE, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return [row['query'].strip() for row in reader if row.get('query')]

def get_nba_content():
    if not APIFY_TOKEN:
        print("❌ Error: Falta el secret APIFY_TOKEN a GitHub."); sys.exit(1)

    all_queries = load_queries()
    # Triem 4 cerques diferents de queries.csv
    selected_queries = random.sample(all_queries, min(4, len(all_queries)))
    print(f"🔍 Consultes seleccionades per a Apify: {selected_queries}")

    client = ApifyClient(APIFY_TOKEN)

    # PAYLOAD AMB L'ESPECIFICACIÓ EXACTA D'APIFY
    run_input = {
        "searchQueries": selected_queries,
        "maxResults": 0,               # 0 vídeos normals (estalviem quota i evitem horitzontals)
        "maxResultsShorts": 6,         # 6 Shorts per cerca (4 cerques x 6 = ~24 Shorts)
        "maxResultStreams": 0,         # 0 directes
        "downloadSubtitles": False,
        "aiVideoDescription": False,   # Evitem add-ons de pagament
        "aiVideoSummary": False,       # Evitem add-ons de pagament
        "sortingOrder": "relevance"
    }

    print("🚀 Executant 'streamers/youtube-scraper' a Apify...")
    run = client.actor("streamers/youtube-scraper").call(run_input=run_input)

    os.makedirs('data', exist_ok=True)
    processed = []
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, 'r', encoding='utf-8') as f:
            processed = json.load(f)

    candidates = []

    # Recollim els resultats del dataset
    for item in client.dataset(run["defaultDatasetId"]).iterate_items():
        vid_id = item.get("id")
        # Assegurem que sigui un Short natiu
        is_short = item.get("type") == "shorts" or "/shorts/" in item.get("url", "")

        if vid_id and is_short and vid_id not in processed:
            candidates.append({
                "id": vid_id,
                "url": item.get("url") or f"https://www.youtube.com/watch?v={vid_id}",
                "title": item.get("title", "NBA Edit"),
                "views": item.get("viewCount", 0)
            })

    # Eliminem duplicats si la mateixa cerca n'ha retornat algun de repetit
    unique_candidates = []
    seen_ids = set()
    for c in candidates:
        if c['id'] not in seen_ids:
            seen_ids.add(c['id'])
            unique_candidates.append(c)

    # Ordenem pels més vistos (els més virals primer)
    unique_candidates.sort(key=lambda x: x['views'], reverse=True)

    final_queue = unique_candidates[:20]

    with open(QUEUE_FILE, 'w', encoding='utf-8') as f:
        json.dump(final_queue, f, indent=4)

    print(f"\n🎯 CUA GENERADA AMB ÈXIT: {len(final_queue)} Shorts verticals purs.")
    for idx, v in enumerate(final_queue, 1):
        print(f"  {idx}. {v['title']} (👁️ {v['views']} views)")

if __name__ == "__main__":
    get_nba_content()
