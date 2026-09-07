import os
import sys
import time
import json
import requests
import subprocess
from PIL import Image, ImageFilter
import numpy as np
from moviepy import VideoFileClip, CompositeVideoClip

# ==============================================================================
# 📝 CONFIGURACIÓ DE LA PUBLICACIÓ (EDITA AQUÍ EL TEU TÍTOL I HASHTAGS)
# ==============================================================================
INSTAGRAM_CAPTION = "Tonight, V stepped into the crowd, taking in live performances at Vogue World: Hollywood. Known for his own standout fashion moments, he kept it effortlessly stylish in a look worthy of the runway."
# ==============================================================================

# Variables del sistema i rutes
GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY")
GITHUB_SHA = os.getenv("GITHUB_SHA")
ZERNIO_API_KEY = os.getenv("ZERNIO_API_KEY")
INSTAGRAM_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID")
YOUTUBE_COOKIES = os.getenv("YOUTUBE_COOKIES")

VIDEO_PATH = "reels/video.mp4"
COVER_PATH = "assets/thumbnail.png"
QUEUE_FILE = "data/queue.json"
PROCESSED_FILE = "data/processed.json"

RAW_BASE = f"https://raw.githubusercontent.com/{GITHUB_REPOSITORY}/{GITHUB_SHA}"
VIDEO_URL = f"{RAW_BASE}/{VIDEO_PATH}"
COVER_URL = f"{RAW_BASE}/{COVER_PATH}"

def setup_cookies():
    if YOUTUBE_COOKIES:
        with open("cookies.txt", "w", encoding="utf-8") as f:
            f.write(YOUTUBE_COOKIES.strip())
        return True
    return False

def fit_to_1080x1920(clip):
    w, h = clip.size
    ratio = w / h

    # 1. Si ja és 9:16 (o quasi), l'escalem directament
    if ratio <= 0.65:
        return clip.resized(width=1080, height=1920)

    # 2. Si és quadrat (1:1) o 4:5, apliquem blurred background suau
    print("🎨 Vídeo quadrat o 4:5. Aplicant fons desenfocat suau...")
    scale = min(1080 / w, 1920 / h)
    new_w, new_h = int(w * scale), int(h * scale)
    new_w = new_w if new_w % 2 == 0 else new_w - 1
    new_h = new_h if new_h % 2 == 0 else new_h - 1
    fg = clip.resized(width=new_w, height=new_h).with_position("center")

    def blur_frame(frame):
        img = Image.fromarray(frame)
        if img.mode != "RGB":
            img = img.convert("RGB")
        small = img.resize((72, 128), Image.Resampling.BILINEAR)
        blurred = small.filter(ImageFilter.GaussianBlur(radius=6))
        full = blurred.resize((1080, 1920), Image.Resampling.BICUBIC)
        darkened = full.point(lambda p: int(p * 0.65))
        return np.array(darkened)

    bg = clip.resized(width=1080, height=1920).image_transform(blur_frame)
    return CompositeVideoClip([bg, fg], size=(1080, 1920)).with_audio(clip.audio)

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
        print(f"\n📥 Descarregant: {item['title']}")

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
            
            probe_clip = VideoFileClip("temp_raw.mp4")
            w, h = probe_clip.size
            ratio = w / h

            # Rebuig de seguretat per si de cas és horitzontal
            if ratio > 1.05:
                print(f"🚫 VÍDEO DESCARTAT: És horitzontal ({w}x{h}).")
                probe_clip.close()
                if os.path.exists("temp_raw.mp4"):
                    os.remove("temp_raw.mp4")
                continue

            success = True
            target_item = item
            final_clip = fit_to_1080x1920(probe_clip)

        except Exception as e:
            print(f"⚠️ Error amb aquest vídeo ({e}). Provant següent...")
            time.sleep(2)

    if not success:
        print("❌ Cap vídeo vàlid trobat a la cua.")
        with open(QUEUE_FILE, 'w', encoding='utf-8') as f:
            json.dump(queue, f, indent=4)
        sys.exit(1)

    print("⚙️ Renderitzant reel final (1080x1920)...")
    final_clip.write_videofile(VIDEO_PATH, bitrate="3500k", codec="libx264", audio_codec="aac", fps=30)
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

    print(f"✅ Reel llest per a publicar a '{VIDEO_PATH}'.")

def wait_until_public(url, retries=15):
    print(f"🔍 Verificant CDN pública: {url}")
    for i in range(retries):
        try:
            r = requests.head(url, timeout=10)
            if r.status_code == 200:
                print("✅ Fitxer disponible!")
                return True
        except:
            pass
        print(f"  [{i+1}/{retries}] Esperant CDN de GitHub (10s)...")
        time.sleep(10)
    return False

def publish_to_zernio():
    if not ZERNIO_API_KEY:
        print("\n⚠️ MODE TEST:")
        print(f"📝 Títol que es publicaria: {INSTAGRAM_CAPTION}")
        print(f"🔗 Vídeo URL: {VIDEO_URL}")
        print(f"🖼️ Cover URL: {COVER_URL}")
        return

    if not wait_until_public(VIDEO_URL) or not wait_until_public(COVER_URL):
        print("❌ Error: Els fitxers no estan disponibles a la CDN."); sys.exit(1)

    payload = {
        "content": INSTAGRAM_CAPTION,  # Utilitzem la variable definida a dalt
        "mediaItems": [{"type": "video", "url": VIDEO_URL}],
        "platforms": [{
            "platform": "instagram",
            "accountId": INSTAGRAM_ACCOUNT_ID,
            "platformSpecificData": {
                "instagramThumbnail": COVER_URL,
                "shareToFeed": True
            }
        }],
        "publishNow": True
    }

    print("🚀 Publicant a Instagram via Zernio...")
    r = requests.post("https://zernio.com/api/v1/posts",
                     headers={"Authorization": f"Bearer {ZERNIO_API_KEY}", "Content-Type": "application/json"},
                     json=payload)
    print(f"Zernio Status: {r.status_code}")
    if r.status_code >= 300:
        print("Resposta Zernio:", r.text)
    else:
        print(f"✅ REEL PUBLICAT! ID: {r.json().get('post', {}).get('_id')}")

if __name__ == "__main__":
    if "--publish" in sys.argv:
        publish_to_zernio()
    else:
        process_next_video()
