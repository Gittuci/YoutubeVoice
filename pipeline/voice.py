"""Phase 4 — TTS Generation: SRT files → WAV voiceover segments via Gemini TTS."""

import os
import sys
import time
import subprocess
import argparse
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

from google import genai
from google.genai import types

from pipeline import config
from pipeline.utils import parse_srt, find_ffmpeg, safe_print, pcm_to_wav, wav_segment_name, wav_is_valid


def _validate_voice(client: genai.Client, voice_name: str) -> bool:
    """Quick test to check if a voice name works with the TTS model."""
    try:
        response = client.models.generate_content(
            model=config.GEMINI_TTS_MODEL,
            contents="test",
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice_name,
                        )
                    )
                ),
            ),
        )
        if not response.candidates:
            return False
        part = response.candidates[0].content.parts[0]
        return bool(part.inline_data and part.inline_data.data)
    except Exception:
        return False


def _get_voice_for_lang(client: genai.Client, lang: str) -> str:
    """Get a working voice for a language, falling back on failure."""
    primary, fallback = config.VOICE_MAP.get(lang, ("Despina", "Aoede"))
    if _validate_voice(client, primary):
        safe_print(f"  Voice '{primary}' validated for {lang}")
        return primary
    safe_print(f"  Voice '{primary}' failed validation for {lang}, trying '{fallback}'...")
    if _validate_voice(client, fallback):
        safe_print(f"  Voice '{fallback}' validated for {lang}")
        return fallback

    candidates = ["Despina", "Aoede", "Kore", "Charon"]
    for v in candidates:
        if v == primary or v == fallback:
            continue
        if _validate_voice(client, v):
            safe_print(f"  Voice '{v}' validated as fallback for {lang}")
            return v

    raise RuntimeError(f"No working TTS voice found for {lang}")


def generate_tts(client: genai.Client, text: str, voice_name: str, director_notes: str) -> bytes:
    """Generate speech from text using Gemini TTS. Returns raw L16 PCM bytes."""
    prompt = config.load_prompt("tts_generation.txt", director_notes=director_notes, text=text)

    response = client.models.generate_content(
        model=config.GEMINI_TTS_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=voice_name,
                    )
                )
            ),
        ),
    )

    if not response.candidates:
        raise RuntimeError("No candidates returned — response may be blocked or rate-limited")

    part = response.candidates[0].content.parts[0]
    if not part.inline_data or not part.inline_data.data:
        raise RuntimeError("No audio data in response")

    return part.inline_data.data


def _generate_tts_with_retry(client, text, voice_name, director_notes, max_retries=3):
    """Generate TTS with retry on rate limit (429) errors."""
    for attempt in range(max_retries):
        try:
            return generate_tts(client, text, voice_name, director_notes)
        except Exception as e:
            err = str(e)
            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                wait = (attempt + 1) * 30
                safe_print(f"      Rate limited, waiting {wait}s before retry {attempt + 1}/{max_retries}...")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError(f"TTS failed after {max_retries} retries")


def _pcm_duration(pcm_data: bytes, sample_rate: int = 24000, channels: int = 1) -> float:
    """Calculate duration of PCM data in seconds."""
    return len(pcm_data) / (sample_rate * channels * 2)


def _trim_leading_silence(pcm_data: bytes, threshold: int = 100) -> bytes:
    """Trim leading silence from 16-bit PCM data.
    Prevents ~15 frame (~0.5s) delay caused by TTS startup silence."""
    import struct
    for offset in range(0, len(pcm_data) - 1, 2):
        val = abs(struct.unpack_from("<h", pcm_data, offset)[0])
        if val > threshold:
            return pcm_data[offset:]
    return pcm_data


def _chain_atempo(speed: float) -> str:
    """Build ffmpeg atempo filter string, chaining filters for speeds outside 0.5-2.0."""
    if 0.5 <= speed <= 2.0:
        return f"atempo={speed:.4f}"
    remaining = speed
    filters = []
    while remaining > 2.0:
        filters.append("atempo=2.0")
        remaining /= 2.0
    if abs(remaining - 1.0) > 0.001:
        filters.append(f"atempo={remaining:.4f}")
    return ",".join(filters)


def _time_stretch_pcm(pcm_data: bytes, speed: float, sample_rate: int, ffmpeg_path: str) -> bytes:
    """Speed up/down PCM audio using ffmpeg atempo filter(s). 1.0=normal, >1.0=faster."""
    atempo_filter = _chain_atempo(speed)
    cmd = [
        ffmpeg_path, "-y",
        "-f", "s16le",
        "-ar", str(sample_rate),
        "-ac", "1",
        "-i", "pipe:0",
        "-af", atempo_filter,
        "-f", "s16le",
        "-ar", str(sample_rate),
        "-ac", "1",
        "-loglevel", "error",
        "pipe:1",
    ]
    result = subprocess.run(cmd, capture_output=True, input=pcm_data)
    if result.returncode != 0:
        raise RuntimeError(f"atempo time-stretch failed: {result.stderr}")
    return result.stdout


def _build_tagged_text(entry_text: str) -> str:
    """Pass-through — tone tags are already embedded in the SRT text."""
    return entry_text


def _process_one_segment(entry, i, total, lang, client, voice_name, director_notes,
                          sample_rate, ffmpeg_path, wav_dir, srt_path):
    """Process a single TTS segment — used by both sequential and parallel paths."""
    idx = entry["index"]
    start_s = entry["start_seconds"]
    end_s = entry["end_seconds"]
    text = entry["text"]
    window_duration = end_s - start_s

    wav_filename = wav_segment_name(lang, i)
    wav_path = os.path.join(wav_dir, wav_filename)

    # Skip if WAV exists and is newer than SRT
    if wav_is_valid(wav_path):
        if os.path.getmtime(wav_path) >= os.path.getmtime(srt_path):
            import wave
            with wave.open(wav_path, "rb") as wf:
                actual_duration = wf.getnframes() / wf.getframerate()
            safe_print(f"    [{i + 1}/{total}] {idx}: {actual_duration:.1f}s — SKIP (exists)")
            return (wav_path, start_s, actual_duration), True
        else:
            safe_print(f"    [{i + 1}/{total}] {idx}: {window_duration:.1f}s — REGENERATE (SRT changed)")

    tagged_text = _build_tagged_text(text)
    safe_print(f"    [{i + 1}/{total}] {idx}: {window_duration:.1f}s — {text[:60]}...")

    pcm = _generate_tts_with_retry(client, tagged_text, voice_name, director_notes)
    pcm = _trim_leading_silence(pcm)

    actual_duration = _pcm_duration(pcm, sample_rate)
    safe_print(f"      Raw: {actual_duration:.2f}s (window: {window_duration:.2f}s)")

    if actual_duration > window_duration + 0.01:
        speed = actual_duration / window_duration
        safe_print(f"      Speeding up: {speed:.2f}x -> {window_duration:.2f}s")
        pcm = _time_stretch_pcm(pcm, speed, sample_rate, ffmpeg_path)
        actual_duration = window_duration

    pcm_to_wav(pcm, wav_path, rate=sample_rate, channels=config.CHANNELS)
    return (wav_path, start_s, actual_duration), False


class RateLimiter:
    """Thread-safe rate limiter enforcing minimum interval between calls."""
    def __init__(self, rpm: int):
        self._min_interval = 60.0 / rpm if rpm > 0 else 0.0
        self._last_call = 0.0
        self._lock = threading.Lock()

    def acquire(self):
        with self._lock:
            now = time.time()
            wait = self._last_call + self._min_interval - now
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.time()


def generate_voiceover(srt_path: str, lang: str, client: genai.Client, ffmpeg_path: str,
                       wav_dir: str, on_progress: Optional[Callable[[int, int, str], None]] = None) -> list:
    """Generate per-segment time-stretched WAV files from an SRT file.
    Each segment is stretched to exactly fill its SRT window — no gaps, no overlap.
    Returns list of (wav_path, start_seconds, window_duration) tuples.

    Args:
        on_progress: Optional callback(completed, total, status) for progress tracking.
            status is one of: "init", "cached", "generating", "done", "error"
    """
    entries = parse_srt(srt_path)
    total = len(entries)
    if not entries:
        raise ValueError(f"No entries found in {srt_path}")

    director_notes = config.DIRECTOR_NOTES.get(lang, config.DIRECTOR_NOTES["hu"])
    voice = _get_voice_for_lang(client, lang)
    sample_rate = config.SAMPLE_RATE

    os.makedirs(wav_dir, exist_ok=True)

    if on_progress:
        on_progress(0, total, "init")

    safe_print(f"  Generating {total} segments for {lang}...")
    segments = []

    for i, entry in enumerate(entries):
        try:
            seg, was_cached = _process_one_segment(entry, i, total, lang, client, voice,
                                                    director_notes, sample_rate, ffmpeg_path,
                                                    wav_dir, srt_path)
            segments.append(seg)
            if on_progress:
                on_progress(i + 1, total, "cached" if was_cached else "done")
        except Exception as e:
            safe_print(f"    [{i + 1}/{total}] TTS failed: {e}")
            if on_progress:
                on_progress(i + 1, total, "error")
            raise

        if not was_cached:
            time.sleep(3)

    if not segments:
        raise RuntimeError("No audio segments generated")

    safe_print(f"  Generated {len(segments)} WAV segments for {lang}")
    return segments


def generate_voiceover_parallel(srt_path: str, lang: str, client: genai.Client, ffmpeg_path: str,
                                 wav_dir: str, max_workers: int = 3, rpm_limit: int = 10,
                                 on_progress: Optional[Callable[[int, int, str], None]] = None) -> list:
    """Generate WAV segments in parallel using a thread pool with rate limiting.

    Args:
        max_workers: Maximum concurrent TTS API calls.
        rpm_limit: Requests-per-minute limit enforced by a rate limiter.
        on_progress: Optional callback(completed, total, status) — thread-safe.
    """
    entries = parse_srt(srt_path)
    total = len(entries)
    if not entries:
        raise ValueError(f"No entries found in {srt_path}")

    director_notes = config.DIRECTOR_NOTES.get(lang, config.DIRECTOR_NOTES["hu"])
    voice = _get_voice_for_lang(client, lang)
    sample_rate = config.SAMPLE_RATE

    os.makedirs(wav_dir, exist_ok=True)

    safe_print(f"  Generating {total} segments for {lang} (parallel, {max_workers} workers, {rpm_limit} RPM)...")

    rate_limiter = RateLimiter(rpm_limit)
    segments_lock = threading.Lock()
    segments = []
    completed = [0]
    errors = []

    def process_segment(i: int, entry: dict):
        rate_limiter.acquire()
        result, was_cached = _process_one_segment(entry, i, total, lang, client, voice,
                                                   director_notes, sample_rate, ffmpeg_path,
                                                   wav_dir, srt_path)
        with segments_lock:
            segments.append(result)
            completed[0] += 1
            if on_progress:
                on_progress(completed[0], total, "cached" if was_cached else "done")
        return result

    if on_progress:
        on_progress(0, total, "init")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_segment, i, entry): i for i, entry in enumerate(entries)}
        for future in as_completed(futures):
            i = futures[future]
            try:
                future.result()
            except Exception as e:
                safe_print(f"    [{i + 1}/{total}] TTS failed: {e}")
                with segments_lock:
                    completed[0] += 1
                    errors.append((i, str(e)))
                    if on_progress:
                        on_progress(completed[0], total, "error")

    if errors:
        safe_print(f"  {len(errors)} segment(s) failed: {[f'seg {e[0]}' for e in errors[:5]]}")

    if not segments:
        raise RuntimeError("No audio segments generated")

    segments.sort(key=lambda s: s[1])  # sort by start_seconds for chronological order
    safe_print(f"  Generated {len(segments)} WAV segments for {lang} ({len(errors)} failed)")
    return segments, errors


def main():
    parser = argparse.ArgumentParser(description="Phase 4: SRT -> WAV Voiceover Segments")
    parser.add_argument("--input-dir", default=config.OUTPUT_DIR, help="Directory containing master_*.srt files")
    parser.add_argument("--output-dir", default=config.OUTPUT_DIR, help="Output directory for WAV segments")
    parser.add_argument("--langs", default=None, help="Comma-separated language codes (default: hu,de,es,fr)")
    parser.add_argument("--parallel", action="store_true", help="Use parallel TTS generation")
    parser.add_argument("--workers", type=int, default=3, help="Max parallel workers (default: 3)")
    parser.add_argument("--rpm", type=int, default=10, help="Requests per minute limit (default: 10)")
    args = parser.parse_args()

    if not config.vertex_api_key:
        safe_print("ERROR: VERTEX_API_KEY not set. Check your .env file.")
        sys.exit(1)

    langs = args.langs.split(",") if args.langs else ["hu"] + config.TARGET_LANGS
    for lang in langs:
        if lang not in config.LANG_NAMES:
            safe_print(f"ERROR: Unknown language code: {lang}")
            sys.exit(1)

    client = config.create_vertex_client()
    ffmpeg_path = find_ffmpeg()

    os.makedirs(args.output_dir, exist_ok=True)

    safe_print("=" * 60)
    safe_print("  Phase 4: TTS Voiceover Generation (WAV Segments)")
    safe_print(f"  Languages: {', '.join(langs)}")
    safe_print(f"  Mode: {'parallel' if args.parallel else 'sequential'}")
    if args.parallel:
        safe_print(f"  Workers: {args.workers}, RPM: {args.rpm}")
    safe_print("=" * 60)

    for lang in langs:
        srt_path = os.path.join(args.input_dir, f"master_{lang}.srt")
        wav_dir = os.path.join(args.output_dir, config.WAV_SEGMENTS_DIR)

        if not os.path.isfile(srt_path):
            safe_print(f"\n  SKIP: {srt_path} not found")
            continue

        safe_print(f"\n  Processing {lang}...")
        try:
            if args.parallel:
                generate_voiceover_parallel(srt_path, lang, client, ffmpeg_path, wav_dir,
                                             max_workers=args.workers, rpm_limit=args.rpm)
            else:
                generate_voiceover(srt_path, lang, client, ffmpeg_path, wav_dir)
        except Exception as e:
            safe_print(f"  ERROR [{lang}]: {e}")
            continue

    safe_print(f"\n{'=' * 60}")
    safe_print(f"  Phase 4 complete")
    safe_print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
