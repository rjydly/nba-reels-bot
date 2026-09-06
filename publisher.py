import os
import sys
import time
import json
import requests
import subprocess
from moviepy import VideoFileClip, ColorClip, CompositeVideoClip

# --- CONFIGURACIÓ D'ENTORN ---
# GitHub ens dona aquestes automàticament
GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY")
GITHUB_SHA = os.getenv("GITHUB_SHA")

# Aquestes les has de posar tu als Secrets de GitHub
ZERNIO_API_KEY = os.getenv("ZERNIO_API_KEY")
INSTAGRAM_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID")

# Camins de fitxers
VIDEO_PATH = "reels/video.mp4"
COVER_PATH = "reels/cover.jpg"
QUEUE_FILE = "data/queue.json"
PROCESSED_FILE = "data/processed.json"

# URL Pública per a Zernio (Usem el SHA per saltar la memòria cau de la CDN)
RAW_BASE = f"https://raw.githubusercontent.com/{GITHUB_REPOSITORY}/{GITHUB_SHA}"
VIDEO_URL = f"{RAW_BASE}/{VIDEO_PATH}"
COVER_URL = f"{RAW_BASE}/{COVER_PATH}"

def fit_to_1080x1920(clip):
    """Normalitza qualsevol vídeo al format Reel (9:16) amb fons negre."""
    w, h = clip.size
    target_ratio = 1080 / 1920
    current_ratio = w / h

    if abs(current_ratio - target_ratio) < 0.01:
        # Ja és gairebé 9:16, només re-escalem
        return clip.resized(width=1080, height=1920)
    
    # Si no és 9:16, calculem escala per encaixar (letterboxing)
    scale = min(1080 / w, 1920 / h)
    new_w, new_h = int(w * scale), int(h * scale)
    # Ens assegurem que les mides siguin parells (requisit d'algunes versions de ffmpeg)
    new_w = new_w if new_w % 2 == 0 else new_w - 1
    new_h = new_h if new_h % 2 == 0 else new_h - 1
    
    resized_clip = clip.resized(width=new_w, height=new_h)
    
    # Crear fons negre
    bg = ColorClip(size=(1080, 1920), color=(0, 0, 0)).with_duration(clip.duration)
    # Centrar el vídeo sobre el fons
    return CompositeVideoClip([bg, resized_clip.with_position("center")])

def process_next_video():
    """Pas 1: Descarrega, processa i actualitza les llistes locals."""
    if not os.path.exists(QUEUE_FILE):
        print("❌ Error: No existeix el fitxer de cua."); sys.exit(1)

    with open(QUEUE_FILE, 'r') as f:
        queue = json.load(f)

    if not queue:
        print("📭 La cua està buida. Res a publicar."); sys.exit(0)

    # Agafem el primer vídeo
    item = queue.pop(0)
    print(f"🎬 Processant: {item['title']} ({item['url']})")

    # 1. Descarregar de YouTube
    try:
        # Baixem la millor qualitat que sigui MP4 i menor de 1080p per velocitat
        subprocess.run([
            'yt-dlp', 
            '-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4', 
            '--max-filesize', '40M',
            '-o', 'temp_raw.mp4', 
            item['url']
        ], check=True)
    except Exception as e:
        print(f"❌ Error descarregant de YouTube: {e}"); sys.exit(1)

    # 2. Processar amb MoviePy
    print("⚙️ Normalitzant format i generant portada...")
    clip = VideoFileClip("temp_raw.mp4")
    
    # Apliquem normalització 1080x1920
    final_clip = fit_to_1080x1920(clip)
    
    # Guardar vídeo optimitzat
    final_clip.write_videofile(
        VIDEO_PATH, 
        bitrate="3500k", 
        codec="libx264", 
        audio_codec="aac",
        fps=30,
        temp_audiofile="temp-audio.m4a", 
        remove_temp=True
    )
    
    # Guardar portada (frame al segon 0.5 per evitar negres)
    final_clip.save_frame(COVER_PATH, t=0.5)
    
    clip.close()
    final_clip.close()

    # 3. Actualitzar fitxers d'estat
    with open(QUEUE_FILE, 'w') as f:
        json.dump(queue, f, indent=4)

    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, 'r') as f:
            processed = json.load(f)
    else:
        processed = []
    
    processed.append(item['id'])
    with open(PROCESSED_FILE, 'w') as f:
        json.dump(processed, f, indent=4)

    print(f"✅ Vídeo i portada generats a la carpeta /reels.")

def wait_until_public(url, retries=15):
    """Espera que la CDN de GitHub serveixi el fitxer."""
    print(f"🔍 Verificant disponibilitat pública a: {url}")
    for i in range(retries):
        try:
            r = requests.head(url, allow_redirects=True, timeout=10)
            if r.status_code == 200:
                print("✅ Fitxer disponible!")
                return True
        except:
            pass
        print(f"  [{i+1}/{retries}] Esperant CDN de GitHub (10s)...")
        time.sleep(10)
    return False

def publish_to_zernio():
    """Pas 2: Envia la petició a Zernio."""
    if not ZERNIO_API_KEY or not INSTAGRAM_ACCOUNT_ID:
        print("\n⚠️ MODE TEST: No s'han trobat secrets de Zernio.")
        print(f"🔗 Vídeo URL: {VIDEO_URL}")
        print(f"🖼️ Cover URL: {COVER_URL}")
        print("El sistema funciona, però no s'ha publicat res a Instagram.")
        return

    # Esperar que els dos fitxers estiguin vius a la web
    if not wait_until_public(VIDEO_URL) or not wait_until_public(COVER_URL):
        print("❌ Error: Els fitxers no s'han fet públics a temps."); sys.exit(1)

    payload = {
        "content": "NBA Vibes 🏀🔥 #nba #basketball #edits #hoops",
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

    print("🚀 Enviant a Zernio...")
    r = requests.post(
        "https://zernio.com/api/v1/posts",
        headers={
            "Authorization": f"Bearer {ZERNIO_API_KEY}",
            "Content-Type": "application/json"
        },
        json=payload
    )

    if r.status_code >= 300:
        print(f"❌ Error Zernio ({r.status_code}): {r.text}")
        sys.exit(1)
    
    print(f"✅ REEL PUBLICAT! ID: {r.json().get('post', {}).get('_id')}")

if __name__ == "__main__":
    # Si passem l'argument --publish, fem la crida a l'API
    if len(sys.argv) > 1 and sys.argv[1] == "--publish":
        publish_to_zernio()
    else:
        # Per defecte, processem el vídeo
        process_next_video()
