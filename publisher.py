import os, sys, time, json, requests, subprocess
from moviepy import VideoFileClip

# Config d'entorn
GITHUB_REPOSITORY = os.environ["GITHUB_REPOSITORY"]
GITHUB_SHA = os.environ["GITHUB_SHA"]
ZERNIO_API_KEY = os.environ["ZERNIO_API_KEY"]
INSTAGRAM_ACCOUNT_ID = os.environ["INSTAGRAM_ACCOUNT_ID"]

# Camins de fitxers
VIDEO_PATH = "reels/video.mp4"
COVER_PATH = "reels/cover.jpg"
RAW_BASE = f"https://raw.githubusercontent.com/{GITHUB_REPOSITORY}/{GITHUB_SHA}"
VIDEO_URL = f"{RAW_BASE}/{VIDEO_PATH}"
COVER_URL = f"{RAW_BASE}/{COVER_PATH}"

def process_next_video():
    # 1. Llegir cua
    with open('data/queue.json', 'r') as f:
        queue = json.load(f)
    if not queue: return print("Cua buida")
    
    item = queue.pop(0)
    
    # 2. Descarregar de YouTube
    print(f"Baixant: {item['url']}")
    subprocess.run(['yt-dlp', '-f', 'mp4', '-o', 'temp_raw.mp4', item['url']])
    
    # 3. Processar amb MoviePy (Normalitzar i generar portada)
    clip = VideoFileClip("temp_raw.mp4")
    # Forçar 1080x1920 si cal (aquí podríem posar la funció de normalització de l'altre bot)
    clip.write_videofile(VIDEO_PATH, bitrate="3500k", codec="libx264")
    
    # Generar portada (Frame 0.5 segons per evitar pantalles negres)
    clip.save_frame(COVER_PATH, t=0.5)
    clip.close()

    # 4. Actualitzar estat
    with open('data/queue.json', 'w') as f: json.dump(queue, f)
    # Guardar a processats
    with open('data/processed.json', 'r+') as f:
        proc = json.load(f); proc.append(item['id']); f.seek(0); json.dump(proc, f)

    print("✅ Vídeo preparat per a Zernio.")

def wait_until_public(url):
    for i in range(15):
        r = requests.head(url)
        if r.status_code == 200: return True
        print(f"Esperant CDN... ({r.status_code})"); time.sleep(10)
    sys.exit("Error: CDN no disponible")

def publish_to_zernio():
    wait_until_public(VIDEO_URL)
    wait_until_public(COVER_URL)
    
    payload = {
        "content": "NBA vibes 🏀🔥 #nba #basketball #edits",
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
    
    r = requests.post(
        "https://zernio.com/api/v1/posts",
        headers={"Authorization": f"Bearer {ZERNIO_API_KEY}"},
        json=payload
    )
    print(f"Zernio Response: {r.status_code} - {r.text}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--publish":
        publish_to_zernio()
    else:
        process_next_video()
