"""Phase 4 — TTS Generation: SRT files → MP3 voiceovers via Gemini TTS."""

import io
import os
import sys
import time
import subprocess
import argparse

from google import genai
from google.genai import types

from pipeline import config
from pipeline.utils import parse_srt, find_ffmpeg, safe_print


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
    prompt = (
        f"### DIRECTOR'S NOTES\n{director_notes}\n\n"
        f"#### TRANSCRIPT\n{text}"
    )

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
    import time as _time
    for attempt in range(max_retries):
        try:
            return generate_tts(client, text, voice_name, director_notes)
        except Exception as e:
            err = str(e)
            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                wait = (attempt + 1) * 30
                safe_print(f"      Rate limited, waiting {wait}s before retry {attempt + 1}/{max_retries}...")
                _time.sleep(wait)
            else:
                raise
    raise RuntimeError(f"TTS failed after {max_retries} retries")


def _pcm_duration(pcm_data: bytes, sample_rate: int = 24000, channels: int = 1) -> float:
    """Calculate duration of PCM data in seconds."""
    return len(pcm_data) / (sample_rate * channels * 2)


def _generate_silence(duration_s: float, sample_rate: int = 24000, channels: int = 1) -> bytes:
    """Generate silent PCM data for the given duration."""
    num_samples = int(duration_s * sample_rate * channels)
    return b"\x00" * (num_samples * 2)


def _pcm_to_mp3_bytes(pcm_data: bytes, ffmpeg_path: str, sample_rate: int = 24000) -> bytes:
    """Convert PCM to MP3 via ffmpeg pipe, return bytes."""
    cmd = [
        ffmpeg_path, "-y",
        "-f", "s16le",
        "-ar", str(sample_rate),
        "-ac", "1",
        "-i", "pipe:0",
        "-codec:a", "libmp3lame",
        "-b:a", config.MP3_BITRATE,
        "-ar", str(sample_rate),
        "-ac", "1",
        "-loglevel", "error",
        "-f", "mp3",
        "pipe:1",
    ]
    result = subprocess.run(cmd, capture_output=True, input=pcm_data)
    if result.returncode != 0:
        raise RuntimeError(f"PCM-to-MP3 conversion failed: {result.stderr}")
    return result.stdout


def _build_tagged_text(entry_text: str, is_first: bool) -> str:
    """
    Insert audio tags into narration text for expression control.
    - Opening entry: start with [enthusiasm]
    - Normal entries: no leading tag
    - Important tips: add [warm] before tip
    """
    tagged = entry_text
    if is_first:
        tagged = f"[enthusiasm] {tagged}"
    return tagged


def generate_voiceover(srt_path: str, lang: str, client: genai.Client, ffmpeg_path: str,
                       output_path: str) -> str:
    """Generate a full voiceover MP3 from an SRT file for a given language."""
    entries = parse_srt(srt_path)
    if not entries:
        raise ValueError(f"No entries found in {srt_path}")

    director_notes = config.DIRECTOR_NOTES.get(lang, config.DIRECTOR_NOTES_HU)
    voice = _get_voice_for_lang(client, lang)
    sample_rate = config.SAMPLE_RATE

    segments = []

    safe_print(f"  Generating {len(entries)} segments for {lang}...")

    for i, entry in enumerate(entries):
        idx = entry["index"]
        start_s = entry["start_seconds"]
        end_s = entry["end_seconds"]
        text = entry["text"]
        window_duration = end_s - start_s

        tagged_text = _build_tagged_text(text, i == 0)

        safe_print(f"    [{i + 1}/{len(entries)}] {idx}: {window_duration:.1f}s — {text[:60]}...")

        try:
            pcm = _generate_tts_with_retry(client, tagged_text, voice, director_notes)
        except Exception as e:
            safe_print(f"      TTS failed: {e}")
            raise

        actual_duration = _pcm_duration(pcm, sample_rate)
        safe_print(f"      Audio: {actual_duration:.2f}s (window: {window_duration:.2f}s)")

        if actual_duration > window_duration:
            target_samples = int(window_duration * sample_rate * config.CHANNELS * 2)
            pcm = pcm[:target_samples]
            segment_duration = window_duration
        else:
            segment_duration = actual_duration

        segments.append((pcm, segment_duration, entry))
        time.sleep(6)  # 10 req/min limit

    if not segments:
        raise RuntimeError("No audio segments generated")

    safe_print(f"\n  Concatenating {len(segments)} segments with time alignment...")
    aligned_pcm = align_and_concat(segments, sample_rate)

    safe_print(f"  Converting to MP3...")
    mp3_bytes = _pcm_to_mp3_bytes(aligned_pcm, ffmpeg_path, sample_rate)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(mp3_bytes)

    total_duration = _pcm_duration(aligned_pcm, sample_rate)
    safe_print(f"  Voiceover saved: {output_path} ({total_duration:.1f}s)")
    return output_path


def align_and_concat(segments, sample_rate):
    """
    Concatenate audio segments with proper time alignment and silence gaps.
    Applies fade-in on segment boundaries to avoid clicks.
    """
    if not segments:
        return b""

    concat_input = io.BytesIO()
    prev_end = None
    fade_time = 0.01

    for pcm, duration, entry in segments:
        start_s = entry["start_seconds"]

        if prev_end is not None and start_s > prev_end:
            gap = start_s - prev_end
            silence = _generate_silence(gap, sample_rate)
            concat_input.write(silence)

        if fade_time > 0 and len(pcm) > int(fade_time * sample_rate * config.CHANNELS * 2):
            fade_samples = int(fade_time * sample_rate * config.CHANNELS * 2)
            pcm_array = bytearray(pcm)
            for s in range(fade_samples):
                factor = float(s) / fade_samples
                pos = s * 2
                sample = int.from_bytes(pcm_array[pos:pos + 2], "little", signed=True)
                sample = int(sample * factor)
                pcm_array[pos:pos + 2] = sample.to_bytes(2, "little", signed=True)
            pcm = bytes(pcm_array)

        concat_input.write(pcm)
        prev_end = start_s + duration

    return concat_input.getvalue()


def main():
    parser = argparse.ArgumentParser(description="Phase 4: SRT -> MP3 Voiceover")
    parser.add_argument("--input-dir", default=config.OUTPUT_DIR, help="Directory containing master_*.srt files")
    parser.add_argument("--output-dir", default=config.OUTPUT_DIR, help="Output directory for MP3s")
    parser.add_argument("--langs", default=None, help="Comma-separated language codes (default: hu,de,es,fr)")
    args = parser.parse_args()

    if not config.google_api_key:
        safe_print("ERROR: GOOGLE_API_KEY not set. Check your .env file.")
        sys.exit(1)

    langs = args.langs.split(",") if args.langs else ["hu"] + config.TARGET_LANGS

    client = genai.Client(api_key=config.google_api_key)
    ffmpeg_path = find_ffmpeg()

    os.makedirs(args.output_dir, exist_ok=True)

    safe_print("=" * 60)
    safe_print("  Phase 4: TTS Voiceover Generation")
    safe_print(f"  Languages: {', '.join(langs)}")
    safe_print("=" * 60)

    for lang in langs:
        srt_path = os.path.join(args.input_dir, f"master_{lang}.srt")
        mp3_path = os.path.join(args.output_dir, f"voiceover_{lang}.mp3")

        if not os.path.isfile(srt_path):
            safe_print(f"\n  SKIP: {srt_path} not found")
            continue

        safe_print(f"\n  Processing {lang}...")
        try:
            generate_voiceover(srt_path, lang, client, ffmpeg_path, mp3_path)
        except Exception as e:
            safe_print(f"  ERROR [{lang}]: {e}")
            continue

    safe_print(f"\n{'=' * 60}")
    safe_print(f"  Phase 4 complete")
    safe_print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
