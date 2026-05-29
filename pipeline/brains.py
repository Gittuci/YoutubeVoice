"""Phase 3 — SRT Translation: master_hu.srt → de/es/fr SRTs via DeepSeek."""

import os
import sys
import argparse
import time

from openai import OpenAI

from google import genai

from pipeline import config
from pipeline.utils import parse_srt, SRT_TS_RE


def load_master_srt(path: str) -> str:
    """Load master SRT file as raw text."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _clean_response(text: str) -> str:
    """Strip markdown wrapping, commentary, and extra whitespace from API response."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    while text and not text[0].isdigit():
        idx = text.find("\n")
        if idx == -1:
            break
        candidate = text[idx + 1:].lstrip()
        if candidate and candidate[0].isdigit():
            text = candidate
            break
        text = candidate
    return text


def _extract_timestamps(srt_text: str) -> list:
    """Extract all timestamp strings (start,end) from SRT text."""
    timestamps = []
    for m in SRT_TS_RE.finditer(srt_text):
        start = f"{m.group(2)}:{m.group(3)}:{m.group(4)},{m.group(5)}"
        end = f"{m.group(6)}:{m.group(7)}:{m.group(8)},{m.group(9)}"
        timestamps.append((start, end))
    return timestamps


def validate_translation(master_srt: str, translated_srt: str, lang: str) -> bool:
    """
    Validate translated SRT against master:
    - Same entry count
    - All timestamp strings match exactly
    - Starts with a digit (SRT index), not backticks
    - Parses without errors
    """
    if not translated_srt or not translated_srt[0].isdigit():
        print(f"  [{lang}] Validation failed: response does not start with SRT index")
        return False

    master_entries = _extract_timestamps(master_srt)
    trans_entries = _extract_timestamps(translated_srt)

    if len(master_entries) != len(trans_entries):
        print(f"  [{lang}] Validation failed: entry count mismatch ({len(master_entries)} vs {len(trans_entries)})")
        return False

    for i, ((ms, me), (ts, te)) in enumerate(zip(master_entries, trans_entries)):
        if ms != ts or me != te:
            print(f"  [{lang}] Validation failed: timestamp mismatch at entry {i + 1}")
            return False

    try:
        entries = parse_srt_from_text(translated_srt)
        if len(entries) != len(master_entries):
            print(f"  [{lang}] Validation failed: parse entry count mismatch")
            return False
    except Exception as e:
        print(f"  [{lang}] Validation failed: SRT parse error: {e}")
        return False

    return True


def parse_srt_from_text(text: str):
    """Parse SRT from raw text."""
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".srt", delete=False, encoding="utf-8") as f:
        f.write(text)
        tmp_path = f.name
    try:
        entries = parse_srt(tmp_path)
    finally:
        os.unlink(tmp_path)
    return entries


def translate_with_deepseek(master_srt: str, lang: str, client: OpenAI) -> str:
    """Translate SRT using DeepSeek API."""
    lang_name = config.LANG_NAMES.get(lang, lang)
    system_prompt = (
        f"Translate the following Hungarian SRT subtitles into {lang_name}.\n"
        "STRICT RULES:\n"
        "- Preserve ALL SRT entry indexes and timestamps EXACTLY as-is — copy them verbatim.\n"
        "- Only translate the subtitle text part of each entry.\n"
        "- Keep translations natural, instructional, and concise enough to fit within the timestamp durations.\n"
        "- Output valid SRT format only — no commentary, no markdown, no extra text.\n"
        "- The entire output must be a valid .srt file.\n"
        "- Start your response with the first SRT index number. Do not prefix with any text."
    )

    response = client.chat.completions.create(
        model=config.DEEPSEEK_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": master_srt},
        ],
        temperature=0.1,
    )

    text = response.choices[0].message.content or ""
    return _clean_response(text)


def translate_with_gemini(master_srt: str, lang: str, gemini_client: genai.Client) -> str:
    """Fallback: Translate SRT using Gemini."""
    lang_name = config.LANG_NAMES.get(lang, lang)
    prompt = (
        f"Translate the following Hungarian SRT subtitles into {lang_name}.\n"
        "STRICT RULES:\n"
        "- Preserve ALL SRT entry indexes and timestamps EXACTLY as-is — copy them verbatim.\n"
        "- Only translate the subtitle text part of each entry.\n"
        "- Keep translations natural, instructional, and concise enough to fit within the timestamp durations.\n"
        "- Output valid SRT format only — no commentary, no markdown, no extra text.\n"
        "- Start your response with the first SRT index number.\n\n"
        f"{master_srt}"
    )

    response = gemini_client.models.generate_content(
        model=config.GEMINI_VISION_MODEL,
        contents=prompt,
    )

    if not response.candidates:
        raise RuntimeError(f"[{lang}] Gemini fallback: no candidates returned")

    text = response.text or ""
    return _clean_response(text)


def translate_language(master_srt: str, lang: str, deepseek_client: OpenAI,
                       gemini_client: genai.Client = None) -> str:
    """Translate SRT for a single language with retries and Gemini fallback."""
    lang_name = config.LANG_NAMES.get(lang, lang)
    print(f"\n  Translating to {lang_name} ({lang})...")

    for attempt in range(3):
        try:
            print(f"    DeepSeek attempt {attempt + 1}...")
            translated = translate_with_deepseek(master_srt, lang, deepseek_client)
            if validate_translation(master_srt, translated, lang):
                print(f"    [{lang}] Translation validated ({len(_extract_timestamps(translated))} entries)")
                return translated
            print(f"    [{lang}] Validation failed, retrying...")
            time.sleep(1)
        except Exception as e:
            print(f"    [{lang}] DeepSeek error: {e}")
            if attempt < 2:
                print("    Retrying...")
                time.sleep(1)

    if gemini_client and config.google_api_key:
        print(f"    [{lang}] DeepSeek exhausted, falling back to Gemini...")
        try:
            translated = translate_with_gemini(master_srt, lang, gemini_client)
            if validate_translation(master_srt, translated, lang):
                print(f"    [{lang}] Gemini fallback validated")
                return translated
            print(f"    [{lang}] Gemini fallback validation failed")
        except Exception as e:
            print(f"    [{lang}] Gemini fallback error: {e}")

    raise RuntimeError(f"[{lang}] All translation attempts failed")


def main():
    parser = argparse.ArgumentParser(description="Phase 3: SRT Translation")
    parser.add_argument("--input", default=None, help="Input SRT file (default: output/master_hu.srt)")
    parser.add_argument("--output-dir", default=config.OUTPUT_DIR, help="Output directory")
    args = parser.parse_args()

    if not config.deepseek_api_key:
        print("ERROR: DEEPSEEK_API_KEY not set. Check your .env file.")
        sys.exit(1)

    input_path = args.input or os.path.join(config.OUTPUT_DIR, "master_hu.srt")
    if not os.path.isfile(input_path):
        print(f"ERROR: Input SRT not found: {input_path}")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    deepseek_client = OpenAI(
        base_url=config.DEEPSEEK_BASE_URL,
        api_key=config.deepseek_api_key,
    )

    gemini_client = None
    if config.google_api_key:
        gemini_client = genai.Client(api_key=config.google_api_key)

    print("=" * 60)
    print("  Phase 3: SRT Translation")
    print(f"  Input: {input_path}")
    print(f"  Targets: {', '.join(config.TARGET_LANGS)}")
    print("=" * 60)

    master_srt = load_master_srt(input_path)
    master_entries = _extract_timestamps(master_srt)
    print(f"  Master SRT: {len(master_entries)} entries")

    for lang in config.TARGET_LANGS:
        translated = translate_language(master_srt, lang, deepseek_client, gemini_client)
        output_path = os.path.join(args.output_dir, f"master_{lang}.srt")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(translated)
        print(f"    Saved: {output_path}")
        time.sleep(1)

    print(f"\n{'=' * 60}")
    print(f"  Phase 3 complete")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
