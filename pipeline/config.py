"""Centralized configuration — loads .env and exports module-level constants."""

import os

from dotenv import load_dotenv
load_dotenv()

google_api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")

GEMINI_VISION_MODEL = "gemini-2.5-flash"
GEMINI_TTS_MODEL = "gemini-3.1-flash-tts-preview"
DEEPSEEK_MODEL = "deepseek-chat"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

VOICE_MAP = {
    "hu": ("Despina", "Aoede"),
    "de": ("Kore", "Gacrux"),
    "es": ("Laomedeia", "Sulafat"),
    "fr": ("Vindemiatrix", "Callirrhoe"),
}

LANG_NAMES = {"hu": "Hungarian", "de": "German", "es": "Spanish", "fr": "French"}

TARGET_LANGS = ["de", "es", "fr"]

SAMPLE_RATE = 24000
CHANNELS = 1
MP3_BITRATE = "128k"

OUTPUT_DIR = "output"
TEMP_DIR = "temp"

DIRECTOR_NOTES_HU = (
    "Style: Native Hungarian speaker, warm and inviting tone. "
    "Friendly patchwork instructor demonstrating techniques with passion. "
    "Pace: Moderate, welcoming pace. Clear articulation."
)
DIRECTOR_NOTES_DE = (
    "Style: Native German speaker, precise and clear articulation. "
    "Professional patchwork instructor with authoritative yet friendly delivery. "
    "Pace: Steady, well-measured pace. Crisp enunciation."
)
DIRECTOR_NOTES_ES = (
    "Style: Native Spanish speaker, warm and upbeat delivery. "
    "Enthusiastic patchwork instructor with lively, engaging tone. "
    "Pace: Natural, flowing pace. Expressive intonation."
)
DIRECTOR_NOTES_FR = (
    "Style: Native French speaker, gentle and articulate tone. "
    "Elegant patchwork instructor with calm, encouraging delivery. "
    "Pace: Relaxed, graceful pace. Soft but clear articulation."
)

DIRECTOR_NOTES = {
    "hu": DIRECTOR_NOTES_HU,
    "de": DIRECTOR_NOTES_DE,
    "es": DIRECTOR_NOTES_ES,
    "fr": DIRECTOR_NOTES_FR,
}
