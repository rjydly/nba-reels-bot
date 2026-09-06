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
YOUTUBE_COOKIES = os.getenv("YOUTUBE_COOKIES")

VIDEO_PATH = "reels/video.mp4"
COVER_PATH = "reels/cover.jpg"
QUEUE_FILE = "data/queue.json"
PROCESSED_FILE = "data/processed.json"

RAW_BASE = f"https://raw.githubusercontent.com/{GITHUB_REPOSITORY}/{GITHUB_SHA}"
VIDEO_URL = f"{RAW_BASE}/{VIDEO_PATH}"
COVER_URL = f"{RAW_BASE}/{COVER_PATH}"

def setup_cookies():
    """Crea el fitxer cookies.txt si el secret existeix."""
    if YOUTUBE_COOKIES:
        with open("cookies.txt", "w", encoding="utf-8") as f:
            f.write(YOUTUBE_COOKIES.strip())
        return True
    return False

def fit_to_1080x1920(clip):
    w, h = clip.size
    scale = min(1080 / w, 1920 / h)
    new_w, new_h = int(w * scale), int(h * scale)
    new_w = new_w if new_w % 2 == 0 else new_w - 1
    new_h = new_h if new_h % 2 == 0 else new_h - 1
    
    resized = clip.resized(width=new_w, height=new_h)
    bg = ColorClip(size=(1080, 1920), color=(0, 0, 0)).with_duration(clip.duration)
    return CompositeVideoClip([bg, resized.with_position("center")])

def process_next_video():
    if not os.path.exists(QUEUE_FILE):
        sys.exit(0)
    with open(QUEUE_FILE, 'r', encoding='utf-8') as f:
        queue = json.load(f)
    if not queue:
        print("📭 Cua buida."); sys.exit(0)

    has_cookies = setup_cookies()
    success = False

    while queue and not success:
        item = queue.pop(0)
        print(f"📥 Intentant descarregar: {item['title']} ({item['url']})")

        cmd = [
            'yt-dlp',
            '-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4',
            '--max-filesize', '50M',
            '-o', 'temp_raw.mp4',
            item['url']
        ]

        if has_cookies:
            cmd.extend([
                '--cookies', 'cookies.txt',
                '--extractor-args', 'youtube:player_client=web,mweb,android'
            ])
        else:
            cmd.extend(['--extractor-args', 'youtube:player_client=ios,web_embedded'])

        try:
            subprocess.run(cmd, check=True)
            success = True
            target_item = item
        except Exception as e:
            print(f"⚠️ Ha fallat aquest vídeo ({e}). Provant el següent de la cua...")
            time.sleep(2)

    if not success:
        print("❌ No s'ha pogut descarregar cap vídeo de la cua disponible.")
        with open(QUEUE_FILE, 'w', encoding='utf-8') as f:
            json.dump(queue, f, indent=4)
        sys.exit(1)

    print("⚙️ Normalitzant format vertical (9:16)...")
    clip = VideoFileClip("temp_raw.mp4")
    final_clip = fit_to_1080x1920(clip)
    final_clip.write_videofile(VIDEO_PATH, bitrate="3500k", codec="libx264", audio_codec="aac", fps=30)
    final_clip.save_frame(COVER_PATH, t=0.5)
    clip.close()
    final_clip.close()

    with open(QUEUE_FILE, 'w', encoding='utf-8') as f:
        json.dump(queue, f, indent=4)

    processed = []
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, 'r', encoding='utf-8') as f:
            processed = json.load(f)
    processed.append(target_item['id'])
    with open(PROCESSED_FILE, 'w', encoding='utf-8') as f:
        json.dump(processed, f, indent=4)

    print("✅ Vídeo i portada preparats correctament.")

def publish_to_zernio():
    if not ZERNIO_API_KEY:
        print("⚠️ Mode Test: Vídeo URL:", VIDEO_URL); return

    for i in range(15):
        if requests.head(VIDEO_URL).status_code == 200:
            break
        print("Esperant CDN de GitHub..."); time.sleep(10)

    payload = {
        "content": "Hoops daily 🔥🏀 #nba #basketball #euroleague #edits",
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
    print(f"Zernio Status: {r.status_code}")

if __name__ == "__main__":
    if "--publish" in sys.argv:
        publish_to_zernio()
    else:
        process_next_video()
