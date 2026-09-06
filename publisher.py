import os
import sys
import time
import json
import requests
import subprocess
from PIL import Image, ImageFilter
import numpy as np
from moviepy import VideoFileClip, CompositeVideoClip

GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY")
GITHUB_SHA = os.getenv("GITHUB_SHA")
ZERNIO_API_KEY = os.getenv("ZERNIO_API_KEY")
INSTAGRAM_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID")
YOUTUBE_COOKIES = os.getenv("YOUTUBE_COOKIES")

VIDEO_PATH = "reels/video.mp4"
COVER_PATH = "assets/thumbnail.png"  # Portada fixa corporativa
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

def fit_to_1080x1920_with_blur(clip):
    """
    Si el vídeo és 9:16, l'escala a 1080x1920.
    Si NO és 9:16, centra el vídeo nítid i posa de fons
    el propi vídeo desenfocat (blurred background) i lleugerament enfosquit.
    """
    w, h = clip.size
    target_ratio = 1080 / 1920
    current_ratio = w / h

    # Si ja té relació 9:16 (amb marge d'error del 2%), només redimensionem
    if abs(current_ratio - target_ratio) < 0.02:
        return clip.resized(width=1080, height=1920)

    print("🔄 El vídeo no és 9:16. Aplicant efecte de fons desenfocat (blurred background)...")

    # 1. Vídeo en primer pla (nítid i centrat, mantenint proporcions)
    scale = min(1080 / w, 1920 / h)
    new_w, new_h = int(w * scale), int(h * scale)
    new_w = new_w if new_w % 2 == 0 else new_w - 1
    new_h = new_h if new_h % 2 == 0 else new_h - 1
    fg = clip.resized(width=new_w, height=new_h).with_position("center")

    # 2. Funció de desenfocament d'alt rendiment (Downscale -> Gaussian Blur -> Upscale + Enfosquit)
    def blur_frame(frame):
        img = Image.fromarray(frame)
        if img.mode != "RGB":
            img = img.convert("RGB")
        # Reduïm per fer el desenfocament ultra ràpid sense sobrecarregar la CPU
        small = img.resize((72, 128), Image.Resampling.BILINEAR)
        blurred = small.filter(ImageFilter.GaussianBlur(radius=6))
        full = blurred.resize((1080, 1920), Image.Resampling.BICUBIC)
        # Enfosquim un 35% perquè el vídeo central ressalti molt més
        darkened = full.point(lambda p: int(p * 0.65))
        return np.array(darkened)

    # 3. Vídeo de fons estirat i desenfocat
    bg = clip.resized(width=1080, height=1920).image_transform(blur_frame)

    # 4. Composició final assegurant l'àudio original
    composite = CompositeVideoClip([bg, fg], size=(1080, 1920)).with_audio(clip.audio)
    return composite

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

    print("⚙️ Normalitzant format vertical (9:16) amb MoviePy...")
    clip = VideoFileClip("temp_raw.mp4")
    final_clip = fit_to_1080x1920_with_blur(clip)
    final_clip.write_videofile(VIDEO_PATH, bitrate="3500k", codec="libx264", audio_codec="aac", fps=30)
    clip.close()
    final_clip.close()

    # Comprovem que existeixi la portada fixa
    if not os.path.exists(COVER_PATH):
        print(f"⚠️ ATENCIÓ: No s'ha trobat '{COVER_PATH}'. Recorda pujar la portada fixa.")

    with open(QUEUE_FILE, 'w', encoding='utf-8') as f:
        json.dump(queue, f, indent=4)

    processed = []
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, 'r', encoding='utf-8') as f:
            processed = json.load(f)
    processed.append(target_item['id'])
    with open(PROCESSED_FILE, 'w', encoding='utf-8') as f:
        json.dump(processed, f, indent=4)

    print(f"✅ Reel preparat a '{VIDEO_PATH}'.")

def wait_until_public(url, retries=15):
    print(f"🔍 Verificant URL pública: {url}")
    for i in range(retries):
        try:
            r = requests.head(url, allow_redirects=True, timeout=10)
            if r.status_code == 200:
                print("✅ Disponible!")
                return True
        except:
            pass
        print(f"  [{i+1}/{retries}] Esperant CDN de GitHub (10s)...")
        time.sleep(10)
    return False

def publish_to_zernio():
    if not ZERNIO_API_KEY:
        print("⚠️ Mode Test: Vídeo URL:", VIDEO_URL)
        print("⚠️ Mode Test: Portada URL:", COVER_URL)
        return

    if not wait_until_public(VIDEO_URL) or not wait_until_public(COVER_URL):
        print("❌ Error: Els fitxers no estan disponibles a la CDN."); sys.exit(1)

    payload = {
        "content": "Hoops daily 🔥🏀 #nba #basketball #euroleague #edits",
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
    r = requests.post("https://zernio.com/api/v1/posts",
                     headers={"Authorization": f"Bearer {ZERNIO_API_KEY}", "Content-Type": "application/json"},
                     json=payload)
    print(f"Zernio Status: {r.status_code}")
    if r.status_code >= 300:
        print("Resposta Zernio:", r.text)

if __name__ == "__main__":
    if "--publish" in sys.argv:
        publish_to_zernio()
    else:
        process_next_video()
