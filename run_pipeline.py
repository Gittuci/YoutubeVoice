#!/usr/bin/env python3
"""Orchestrator — runs pipeline phases 2→5 in sequence."""

import os
import sys
import argparse

from google import genai
from openai import OpenAI

from pipeline import config


def run_phase2(url: str, output_dir: str, temp_dir: str, verbose: bool = False):
    """Phase 2: Download YouTube video + analyze → master_hu.srt"""
    from pipeline.eyes import download_video, analyze_video, _validate_srt

    if not config.google_api_key:
        raise RuntimeError("GOOGLE_API_KEY not set")

    client = genai.Client(api_key=config.google_api_key)
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(temp_dir, exist_ok=True)

    print("=" * 60)
    print("  Phase 2: Video → SRT Analysis")
    print(f"  URL: {url}")
    print("=" * 60)

    temp_video_path = os.path.join(temp_dir, "video.mp4")
    print(f"\n  Downloading video from YouTube...")
    actual_path = download_video(url, temp_video_path)
    print(f"    Downloaded: {actual_path}")

    try:
        srt_text = analyze_video(actual_path, client)
        srt_text = _validate_srt(srt_text)
        output_path = os.path.join(output_dir, "master_hu.srt")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(srt_text)
        print(f"\n    SRT saved: {output_path}")
    finally:
        if os.path.isfile(actual_path):
            os.unlink(actual_path)

    return os.path.join(output_dir, "master_hu.srt")


def run_phase3(input_dir: str, output_dir: str, verbose: bool = False):
    """Phase 3: Translate master_hu.srt → de/es/fr SRTs"""
    from pipeline.brains import load_master_srt, translate_language
    import time

    if not config.deepseek_api_key:
        raise RuntimeError("DEEPSEEK_API_KEY not set")

    deepseek_client = OpenAI(
        base_url=config.DEEPSEEK_BASE_URL,
        api_key=config.deepseek_api_key,
    )
    gemini_client = None
    if config.google_api_key:
        gemini_client = genai.Client(api_key=config.google_api_key)

    master_path = os.path.join(input_dir, "master_hu.srt")
    if not os.path.isfile(master_path):
        raise FileNotFoundError(f"Master SRT not found: {master_path}")

    print("\n" + "=" * 60)
    print("  Phase 3: SRT Translation")
    print(f"  Input: {master_path}")
    print(f"  Targets: {', '.join(config.TARGET_LANGS)}")
    print("=" * 60)

    master_srt = load_master_srt(master_path)

    outputs = []
    for lang in config.TARGET_LANGS:
        translated = translate_language(master_srt, lang, deepseek_client, gemini_client)
        output_path = os.path.join(output_dir, f"master_{lang}.srt")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(translated)
        print(f"    Saved: {output_path}")
        outputs.append(output_path)
        time.sleep(1)

    return outputs


def run_phase4(input_dir: str, output_dir: str, verbose: bool = False):
    """Phase 4: Generate TTS voiceover MP3s from SRTs"""
    import time
    from pipeline.voice import find_ffmpeg, generate_voiceover

    if not config.google_api_key:
        raise RuntimeError("GOOGLE_API_KEY not set")

    client = genai.Client(api_key=config.google_api_key)
    ffmpeg_path = find_ffmpeg()

    print("\n" + "=" * 60)
    print("  Phase 4: TTS Voiceover Generation")
    print("=" * 60)

    langs = ["hu"] + config.TARGET_LANGS
    outputs = []

    for lang in langs:
        srt_path = os.path.join(input_dir, f"master_{lang}.srt")
        mp3_path = os.path.join(output_dir, f"voiceover_{lang}.mp3")

        if not os.path.isfile(srt_path):
            print(f"\n  SKIP: {srt_path} not found")
            continue

        print(f"\n  Processing {lang}...")
        generate_voiceover(srt_path, lang, client, ffmpeg_path, mp3_path)
        outputs.append(mp3_path)
        time.sleep(1)

    return outputs


def run_phase5(input_dir: str, output_dir: str, video_path: str = None, verbose: bool = False):
    """Phase 5: Verify alignment, optionally mux with video"""
    from pipeline.assembly import find_ffmpeg, verify_alignment, mux_video_audio

    ffmpeg_path = find_ffmpeg()

    print("\n" + "=" * 60)
    print("  Phase 5: Audio-Video Assembly")
    print("=" * 60)

    langs = ["hu"] + config.TARGET_LANGS
    results = {}

    for lang in langs:
        print(f"\n  Processing {lang}...")
        mp3_path = os.path.join(input_dir, f"voiceover_{lang}.mp3")
        srt_path = os.path.join(input_dir, f"master_{lang}.srt")

        if not os.path.isfile(mp3_path) or not os.path.isfile(srt_path):
            print(f"    SKIP: missing files for {lang}")
            continue

        try:
            aligned = verify_alignment(mp3_path, srt_path, lang, ffmpeg_path)
            results[lang] = {"mp3": mp3_path, "aligned": aligned}

            if video_path and os.path.isfile(video_path):
                video_output = os.path.join(output_dir, f"video_{lang}.mp4")
                mux_video_audio(video_path, mp3_path, video_output, ffmpeg_path)
                results[lang]["video"] = video_output
                size_kb = os.path.getsize(video_output) / 1024
                print(f"    Video saved: {video_output} ({size_kb:.1f} KB)")
        except Exception as e:
            print(f"    ERROR [{lang}]: {e}")
            results[lang] = {"mp3": mp3_path, "aligned": False, "error": str(e)}

    return results


def main():
    parser = argparse.ArgumentParser(description="Foltvilag Multi-Language Video Voiceover Pipeline")
    parser.add_argument("--url", required=True, help="YouTube video URL")
    parser.add_argument("--output", default=config.OUTPUT_DIR, help="Output directory")
    parser.add_argument("--skip-phase", default="", help="Comma-separated phases to skip (e.g. '2,5')")
    parser.add_argument("--with-video", action="store_true", help="Mux voiceovers with video in Phase 5")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()

    skip = set(args.skip_phase.split(",")) if args.skip_phase else set()

    print("=" * 60)
    print("  Foltvilag Pipeline")
    print(f"  URL: {args.url}")
    print(f"  Output: {args.output}")
    print("=" * 60)

    os.makedirs(args.output, exist_ok=True)
    os.makedirs(config.TEMP_DIR, exist_ok=True)

    temp_video_path = os.path.join(config.TEMP_DIR, "video.mp4")

    if "2" not in skip:
        try:
            run_phase2(args.url, args.output, config.TEMP_DIR, args.verbose)
        except Exception as e:
            print(f"\n  Phase 2 FAILED: {e}")
            sys.exit(1)
    else:
        print("\n  Skipping Phase 2")

    if "3" not in skip:
        try:
            run_phase3(args.output, args.output, args.verbose)
        except Exception as e:
            print(f"\n  Phase 3 FAILED: {e}")
            sys.exit(1)
    else:
        print("\n  Skipping Phase 3")

    if "4" not in skip:
        try:
            run_phase4(args.output, args.output, args.verbose)
        except Exception as e:
            print(f"\n  Phase 4 FAILED: {e}")
            sys.exit(1)
    else:
        print("\n  Skipping Phase 4")

    if "5" not in skip:
        try:
            video_arg = temp_video_path if args.with_video else None
            results = run_phase5(args.output, args.output, video_arg, args.verbose)
        except Exception as e:
            print(f"\n  Phase 5 FAILED: {e}")
            sys.exit(1)
    else:
        print("\n  Skipping Phase 5")

    print(f"\n{'=' * 60}")
    print(f"  Pipeline complete!")
    print(f"  Outputs in: {os.path.abspath(args.output)}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
