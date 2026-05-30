#!/usr/bin/env python3
"""
Phase 1 PoC — Gemini 3.1 Flash TTS Preview Audio Generation (Vertex AI)
Generates a single voiceover file using gemini-3.1-flash-tts-preview via Vertex AI.

Prerequisites:
    pip install google-genai python-dotenv
    Set VERTEX_API_KEY environment variable in .env
    ffmpeg must be on system PATH

Usage:
    python poc_tts.py
"""

import os
import subprocess
import sys
from pathlib import Path

from google import genai
from google.genai import types

from pipeline import config
from pipeline.utils import pcm_to_mp3, find_ffmpeg


def generate_tts(client: genai.Client, text: str, voice_name: str = "Despina", model: str = None) -> bytes:
    """
    Generate speech from text using Gemini TTS via Vertex AI.

    The prompt uses Director's Notes for overall tone and style,
    plus inline audio tags (e.g., [enthusiasm]) embedded in the transcript
    for sentence-level expression control.

    Returns raw L16 PCM bytes.
    """
    if model is None:
        model = config.GEMINI_TTS_MODEL
    prompt = f"""### DIRECTOR'S NOTES
Style: Warm, enthusiastic, instructional. The speaker is a friendly patchwork instructor demonstrating techniques with passion. The "Vocal Smile" — the listener should hear kindness and genuine excitement in every word.
Accent: Native English speaker.
Pace: Moderate, welcoming pace. Clear articulation.

#### TRANSCRIPT
{text}"""

    print(f"\n  Generating TTS with voice '{voice_name}'...")
    print(f"  Text: {text}")

    response = client.models.generate_content(
        model=model,
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

    mime_type = part.inline_data.mime_type or "audio/l16"
    print(f"  MIME type: {mime_type}")

    pcm_bytes = part.inline_data.data
    print(f"  PCM size: {len(pcm_bytes)} bytes ({len(pcm_bytes) / 24000 / 2:.2f}s)")
    return pcm_bytes


def main():
    model = config.GEMINI_TTS_MODEL
    print("=" * 60)
    print("  Foltvilag Phase 1 PoC — Gemini 3.1 Flash TTS Preview (Vertex AI)")
    print(f"  Model: {model}")
    print(f"  Project: {config.VERTEX_PROJECT}")
    print("=" * 60)

    if not config.vertex_api_key:
        print("ERROR: VERTEX_API_KEY not set. Check your .env file.")
        sys.exit(1)

    client = config.create_vertex_client()

    text = "[enthusiasm] Welcome to Foltvilag! Today I'll show you a new technique using the EZ-Log template."

    for attempt, voice in enumerate((["Despina", "Aoede"]), 1):
        try:
            print(f"\n--- Attempt {attempt}: voice = '{voice}' ---")
            pcm_data = generate_tts(client, text, voice_name=voice, model=model)

            try:
                ffmpeg_path = find_ffmpeg()
                mp3_path = "poc_audio.mp3"
                pcm_to_mp3(pcm_data, mp3_path, ffmpeg_path=ffmpeg_path)
                size_kb = Path(mp3_path).stat().st_size / 1024
                print(f"  MP3 saved: {mp3_path} ({size_kb:.1f} KB)")
                final_path = Path(mp3_path).resolve()
                print(f"\n{'=' * 60}")
                print(f"  SUCCESS: poc_audio.mp3 generated with voice '{voice}'")
                print(f"  File: {final_path}")
                print(f"{'=' * 60}")
            except (FileNotFoundError, RuntimeError) as e:
                import wave
                wav_path = "poc_audio.wav"
                with wave.open(wav_path, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(24000)
                    wf.writeframes(pcm_data)
                final_path = Path(wav_path).resolve()
                print(f"\n{'=' * 60}")
                print(f"  SUCCESS: poc_audio.wav generated with voice '{voice}'")
                print(f"  WARNING: MP3 conversion failed ({e}), WAV saved instead.")
                print(f"  File: {final_path}")
                print(f"{'=' * 60}")
            return

        except Exception as e:
            print(f"  Attempt {attempt} failed: {e}")
            if attempt < 2:
                print("  Retrying with next voice...")
            else:
                print("\n  All voice attempts failed.")
                raise


if __name__ == "__main__":
    main()
