import os
import zipfile
import shutil
from urllib.request import urlretrieve
from concurrent.futures import ThreadPoolExecutor

URL = "https://github.com/hfg-gmuend/openmoji/releases/latest/download/openmoji-72x72-color.zip"

ASSETS_DIR = "assets"
EMOJI_DIR = os.path.join(ASSETS_DIR, "emoji")
ZIP_PATH = os.path.join(ASSETS_DIR, "openmoji.zip")
TEMP_DIR = os.path.join(ASSETS_DIR, "_openmoji_tmp")

def process_image(src_path, dst_path, size=12):
    from PIL import Image

    with Image.open(src_path) as img:
        img = img.convert("RGBA")
        bbox = img.getchannel("A").getbbox()
        if bbox:
            img = img.crop(bbox)
        w, h = img.size
        m = max(w, h)
        square = Image.new("RGBA", (m, m), (0, 0, 0, 0))
        square.paste(img, ((m - w) // 2, (m - h) // 2))
        square = square.resize((size, size), Image.LANCZOS)
        square.save(dst_path)

def ensure_emoji_assets(size=12):
    if os.path.exists(EMOJI_DIR):
        return EMOJI_DIR

    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        print("PIL not available, continuing without emoji")
        return None

    os.makedirs(ASSETS_DIR, exist_ok=True)

    try:
        print("Downloading OpenMoji...")
        urlretrieve(URL, ZIP_PATH)

        print("Extracting...")
        with zipfile.ZipFile(ZIP_PATH, "r") as z:
            z.extractall(TEMP_DIR)

        print("Processing emoji...")
        os.makedirs(EMOJI_DIR, exist_ok=True)

        files = [f for f in os.listdir(TEMP_DIR) if f.endswith(".png")]

        with ThreadPoolExecutor() as ex:
            futures = []

            for f in files:
                src = os.path.join(TEMP_DIR, f)
                dst = os.path.join(EMOJI_DIR, f)
                futures.append(ex.submit(process_image, src, dst, size))

            for future in futures:
                future.result()

        print("Emoji ready")
        return EMOJI_DIR

    except Exception as e:
        print("Emoji setup failed, continuing without emoji:", e)
        if os.path.exists(EMOJI_DIR):
            shutil.rmtree(EMOJI_DIR, ignore_errors=True)
        return None

    finally:
        if os.path.exists(ZIP_PATH):
            os.remove(ZIP_PATH)
        if os.path.exists(TEMP_DIR):
            shutil.rmtree(TEMP_DIR, ignore_errors=True)
