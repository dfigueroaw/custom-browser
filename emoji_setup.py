import os
import zipfile
import shutil
from urllib.request import urlretrieve

URL = "https://github.com/hfg-gmuend/openmoji/releases/latest/download/openmoji-72x72-color.zip"

ASSETS_DIR = "assets"
EMOJI_DIR = os.path.join(ASSETS_DIR, "emoji")
ZIP_PATH = os.path.join(ASSETS_DIR, "openmoji.zip")

def ensure_emoji_assets():
    if os.path.exists(EMOJI_DIR):
        return EMOJI_DIR

    os.makedirs(ASSETS_DIR, exist_ok=True)

    try:
        print("Downloading OpenMoji...")
        urlretrieve(URL, ZIP_PATH)

        print("Extracting...")
        with zipfile.ZipFile(ZIP_PATH, "r") as z:
            z.extractall(EMOJI_DIR)

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
