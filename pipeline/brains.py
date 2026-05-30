"""Phase 3 — SRT Translation: source SRT → reference lang → target lang SRTs via DeepSeek."""

import os
import sys
import argparse
import time

from openai import OpenAI

from google import genai

from pipeline import config
from pipeline.utils import parse_srt, SRT_TS_RE, strip_markdown_fences, insert_srt_indices


def load_master_srt(path: str) -> str:
    """Load master SRT file as raw text."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _clean_response(text: str) -> str:
    """Strip markdown wrapping, commentary, and extra whitespace from API response.
    Also inserts missing SRT index numbers."""
    text = strip_markdown_fences(text)

    # Strip leading non-digit preamble
    while text and not text[0].isdigit():
        idx = text.find("\n")
        if idx == -1:
            break
        candidate = text[idx + 1:].lstrip()
        if candidate and candidate[0].isdigit():
            text = candidate
            break
        text = candidate

    # Strip trailing non-SRT junk after the last blank-line separator
    last_sep = text.rfind("\n\n")
    if last_sep != -1:
        after_last = text[last_sep + 2:]
        if after_last and not after_last.strip()[0].isdigit():
            text = text[:last_sep].rstrip() + "\n"

    # Insert missing SRT index numbers (same fix as Phase 2)
    text = insert_srt_indices(text)

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

    if abs(len(master_entries) - len(trans_entries)) > 1:
        print(f"  [{lang}] Validation failed: entry count mismatch ({len(master_entries)} vs {len(trans_entries)})")
        return False

    for i, ((ms, me), (ts, te)) in enumerate(zip(master_entries, trans_entries)):
        if ms != ts or me != te:
            print(f"  [{lang}] Validation failed: timestamp mismatch at entry {i + 1}")
            return False

    try:
        entries = parse_srt(translated_srt)
        if len(entries) != len(master_entries):
            print(f"  [{lang}] Validation failed: parse entry count mismatch")
            return False
    except Exception as e:
        print(f"  [{lang}] Validation failed: SRT parse error: {e}")
        return False

    return True


def translate_with_deepseek(master_srt: str, lang: str, client: OpenAI, source_lang: str = "Hungarian") -> str:
    """Translate SRT using DeepSeek API."""
    lang_name = config.LANG_NAMES.get(lang, lang)
    system_prompt = config.load_prompt(
        "translate_system.txt",
        source_lang=source_lang,
        target_lang=lang_name,
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


def translate_with_gemini(master_srt: str, lang: str, gemini_client: genai.Client, source_lang: str = "Hungarian") -> str:
    """Fallback: Translate SRT using Gemini."""
    lang_name = config.LANG_NAMES.get(lang, lang)
    prompt = config.load_prompt(
        "translate_gemini.txt",
        source_lang=source_lang,
        target_lang=lang_name,
    )
    prompt = f"{prompt}\n\n{master_srt}"

    response = gemini_client.models.generate_content(
        model=config.GEMINI_VISION_MODEL,
        contents=prompt,
    )

    if not response.candidates:
        raise RuntimeError(f"[{lang}] Gemini fallback: no candidates returned")

    text = response.text or ""
    return _clean_response(text)


def translate_language(master_srt: str, lang: str, deepseek_client: OpenAI,
                       gemini_client: genai.Client = None, source_lang: str = "Hungarian") -> str:
    """Translate SRT for a single language with retries and Gemini fallback."""
    lang_name = config.LANG_NAMES.get(lang, lang)
    print(f"\n  Translating from {source_lang} to {lang_name} ({lang})...")

    for attempt in range(3):
        try:
            print(f"    DeepSeek attempt {attempt + 1}...")
            translated = translate_with_deepseek(master_srt, lang, deepseek_client, source_lang)
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

    if gemini_client:
        print(f"    [{lang}] DeepSeek exhausted, falling back to Gemini...")
        try:
            translated = translate_with_gemini(master_srt, lang, gemini_client, source_lang)
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
    parser.add_argument("--langs", default=None, help="Comma-separated target language codes (default: de,es,fr)")
    parser.add_argument("--source-lang", default=None, help="Source language name for the input SRT (default: Hungarian)")
    args = parser.parse_args()

    if not config.deepseek_api_key:
        print("ERROR: DEEPSEEK_API_KEY not set. Check your .env file.")
        sys.exit(1)

    input_path = args.input or os.path.join(config.OUTPUT_DIR, "master_hu.srt")
    if not os.path.isfile(input_path):
        print(f"ERROR: Input SRT not found: {input_path}")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    target_langs = args.langs.split(",") if args.langs else config.TARGET_LANGS
    for lang in target_langs:
        if lang not in config.LANG_NAMES:
            print(f"ERROR: Unknown language code: {lang}")
            sys.exit(1)
    source_lang_name = args.source_lang or config.LANG_NAMES.get(config.SOURCE_LANG, "Hungarian")

    deepseek_client = OpenAI(
        base_url=config.DEEPSEEK_BASE_URL,
        api_key=config.deepseek_api_key,
    )

    gemini_client = None
    if config.vertex_api_key:
        gemini_client = config.create_vertex_client()

    print("=" * 60)
    print("  Phase 3: SRT Translation")
    print(f"  Input: {input_path}")
    print(f"  Source: {source_lang_name}")
    print(f"  Targets: {', '.join(target_langs)}")
    print("=" * 60)

    master_srt = load_master_srt(input_path)
    master_entries = _extract_timestamps(master_srt)
    print(f"  Master SRT: {len(master_entries)} entries")

    for lang in target_langs:
        translated = translate_language(master_srt, lang, deepseek_client, gemini_client, source_lang_name)
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
