"""Centralized configuration — loads .env and exports module-level constants."""

import os
import sys

# Ensure stdout handles Unicode on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
from google import genai

load_dotenv()

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(os.path.dirname(os.path.dirname(__file__)), "vertex-key.json")

vertex_api_key = os.getenv("VERTEX_API_KEY")
deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")

VERTEX_PROJECT = "foltvilag-enterprise-audio"
VERTEX_LOCATION = "us-central1"


def create_vertex_client() -> genai.Client:
    """Create a Vertex AI-routed Gemini client using ADC authentication."""
    return genai.Client(
        vertexai=True,
        project=VERTEX_PROJECT,
        location=VERTEX_LOCATION,
    )

GEMINI_VISION_MODEL = "gemini-2.5-flash"
GEMINI_AUDIO_MODEL = "gemini-2.5-flash"
GEMINI_TTS_MODEL = "gemini-3.1-flash-tts-preview"
DEEPSEEK_MODEL = "deepseek-chat"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

AUDIO_TRANSCRIBER = "gemini"

VOICE_MAP = {
    "hu": ("Despina", "Aoede"),
    "en": ("Aoede", "Despina"),
    "de": ("Kore", "Gacrux"),
    "es": ("Laomedeia", "Sulafat"),
    "fr": ("Vindemiatrix", "Callirrhoe"),
}

LANG_NAMES = {
    "hu": "Hungarian",
    "en": "English",
    "de": "German",
    "es": "Spanish",
    "fr": "French",
}

TARGET_LANGS = ["de", "es", "fr"]
SOURCE_LANG = "hu"
REFERENCE_LANG = "en"

SAMPLE_RATE = 24000
CHANNELS = 1

OUTPUT_DIR = "output"
WAV_SEGMENTS_DIR = "wav_segments"
TEMP_DIR = "temp"

def load_prompt(filename: str, **kwargs) -> str:
    """Load a prompt template from prompts/ directory, filling {placeholders}."""
    base = os.path.dirname(os.path.dirname(__file__))
    path = os.path.join(base, "prompts", filename)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Prompt file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        template = f.read().strip()
    return template.format(**kwargs) if kwargs else template


def _load_director_notes(lang: str) -> str:
    """Load director notes from prompts/director_notes_{lang}.txt"""
    return load_prompt(f"director_notes_{lang}.txt")

DIRECTOR_NOTES = {
    "hu": _load_director_notes("hu"),
    "en": _load_director_notes("en"),
    "de": _load_director_notes("de"),
    "es": _load_director_notes("es"),
    "fr": _load_director_notes("fr"),
}
