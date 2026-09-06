import os
import sys
import time
import json
import requests
import subprocess
from moviepy import VideoFileClip, ColorClip, CompositeVideoClip

GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY")
GITHUB_SHA = os.getenv("GITHUB_SHA")
ZERNIO_API_KEY = os.getenv("ZERNIO_API_KEY")
INSTAGRAM_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID")

VIDEO_PATH = "reels/video.mp4"
COVER_PATH = "reels/cover.jpg"
QUEUE_FILE = "data/queue.json"
PROCESSED_FILE = "data/processed.json"

RAW_BASE = f"https://raw.githubusercontent.com/{GITHUB_REPOSITORY}/{GITHUB_SHA}"
VIDEO_URL = f"{RAW_BASE}/{VIDEO_PATH}"
COVER_URL = f"{RAW_BASE}/{COVER_PATH}"

def fit_to_1080x1920(clip):
    w, h = clip.size
    target_ratio = 1080 / 1920
    scale = min(1080 / w, 1920 / h)
    new_w, new_h = int(w * scale), int(h * scale)
    new_w = new_w if new_w % 2 == 0 else new_w - 1
    new_h = new_h if new_h % 2 == 0 else new_h - 1
    
    resized_clip = clip.resized(width=new_w, height=new_h)
    bg = ColorClip(size=(1080, 1920), color=(0, 0, 0)).with_duration(clip.duration)
    return CompositeVideoClip([bg, resized_clip.with_position("center")])

def process_next_video():
    if not os.path.exists(QUEUE_FILE): sys.exit(0)
    with open(QUEUE_FILE, 'r') as f: queue = json.load(f)
    if not queue: sys.exit(0)

    item = queue.pop(0)
    print(f"📥 Baixant: {item['title']}")

    try:
        # BYPASS: ios client + web_embedded eviten el bloqueig de bot
        subprocess.run([
            'yt-dlp', 
            '-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4', 
            '--extractor-args', 'youtube:player_client=ios,web_embedded',
            '-o', 'temp_raw.mp4', 
            item['url']
        ], check=True)
    except Exception as e:
        print(f"❌ Error YouTube: {e}"); sys.exit(1)

    clip = VideoFileClip("temp_raw.mp4")
    final_clip = fit_to_1080x1920(clip)
    final_clip.write_videofile(VIDEO_PATH, bitrate="3500k", codec="libx264", audio_codec="aac", fps=30)
    final_clip.save_frame(COVER_PATH, t=0.5)
    clip.close(); final_clip.close()

    with open(QUEUE_FILE, 'w') as f: json.dump(queue, f, indent=4)
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, 'r') as f: processed = json.load(f)
    else: processed = []
    processed.append(item['id'])
    with open(PROCESSED_FILE, 'w') as f: json.dump(processed, f, indent=4)

def publish_to_zernio():
    if not ZERNIO_API_KEY:
        print("⚠️ Mode Test: Vídeo URL:", VIDEO_URL); return

    # Esperar disponibilitat
    for i in range(15):
        if requests.head(VIDEO_URL).status_code == 200: break
        print("Esperant CDN..."); time.sleep(10)

    payload = {
        "content": "NBA Edits 🏀 #nba #basketball #hoops",
        "mediaItems": [{"type": "video", "url": VIDEO_URL}],
        "platforms": [{
            "platform": "instagram",
            "accountId": INSTAGRAM_ACCOUNT_ID,
            "platformSpecificData": {"instagramThumbnail": COVER_URL, "shareToFeed": True}
        }],
        "publishNow": True
    }
    r = requests.post("https://zernio.com/api/v1/posts", 
                     headers={"Authorization": f"Bearer {ZERNIO_API_KEY}"}, json=payload)
    print(f"Zernio: {r.status_code}")

if __name__ == "__main__":
    if "--publish" in sys.argv: publish_to_zernio()
    else: process_next_video()
