#!/usr/bin/env python3
"""Orchestrator — runs pipeline phases 2→5 in sequence."""

import os
import sys
import argparse

from openai import OpenAI

from pipeline import config


def run_phase1_5(input_path: str, output_dir: str, language: str = "hu",
                  transcriber: str = "gemini", verbose: bool = False):
    """Phase 1.5: Audio transcription → SRT with tone/emotion tags."""
    from pipeline.ears import run_transcription

    print("\n" + "=" * 60)
    print("  Phase 1.5: Audio Transcription (Tone + Emotion)")
    print(f"  Input: {input_path}")
    print(f"  Transcriber: {transcriber}")
    print("=" * 60)

    srt_path = run_transcription(input_path, output_dir, transcriber, language)
    print(f"    SRT with tone tags: {srt_path}")
    return srt_path


def run_phase2(url: str, output_dir: str, temp_dir: str, vision_srt_name: str = "master_hu.srt",
               verbose: bool = False):
    """Phase 2: Download YouTube video + analyze → SRT.
    Returns (srt_path, video_path).
    When vision_srt_name is changed (e.g. master_hu_vision.srt), the primary
    SRT is produced separately by Phase 1.5 transcription.
    """
    from pipeline.eyes import download_video, analyze_video, _validate_srt

    if not config.vertex_api_key:
        raise RuntimeError("VERTEX_API_KEY not set")

    client = config.create_vertex_client()
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

    srt_output = os.path.join(output_dir, vision_srt_name)
    try:
        srt_text = analyze_video(actual_path, client)
        srt_text = _validate_srt(srt_text)
        with open(srt_output, "w", encoding="utf-8") as f:
            f.write(srt_text)
        print(f"\n    SRT saved: {srt_output}")
    finally:
        print(f"    Video preserved at: {actual_path}")

    return srt_output, actual_path


def run_phase3(input_dir: str, output_dir: str, target_langs: list, reference_lang: str, verbose: bool = False):
    """Phase 3: Translate master_hu.srt → reference_lang SRT → target_lang SRTs"""
    from pipeline.brains import load_master_srt, translate_language
    import time

    if not config.deepseek_api_key:
        raise RuntimeError("DEEPSEEK_API_KEY not set")

    deepseek_client = OpenAI(
        base_url=config.DEEPSEEK_BASE_URL,
        api_key=config.deepseek_api_key,
    )
    gemini_client = None
    if config.vertex_api_key:
        gemini_client = config.create_vertex_client()

    master_path = os.path.join(input_dir, "master_hu.srt")
    if not os.path.isfile(master_path):
        raise FileNotFoundError(f"Master SRT not found: {master_path}")

    source_lang = config.SOURCE_LANG
    source_lang_name = config.LANG_NAMES.get(source_lang, "Hungarian")

    print("\n" + "=" * 60)
    print("  Phase 3: SRT Translation")
    print(f"  Input: {master_path}")
    print(f"  Source: {source_lang_name} ({source_lang})")
    print(f"  Reference: {config.LANG_NAMES.get(reference_lang, reference_lang)} ({reference_lang})")
    print(f"  Targets: {', '.join(target_langs)}")
    print("=" * 60)

    master_srt = load_master_srt(master_path)
    all_outputs = []
    reference_srt = None

    if reference_lang != source_lang:
        print(f"\n  Step 3a: Translating {source_lang_name} → {config.LANG_NAMES.get(reference_lang, reference_lang)} (reference)...")
        reference_srt = translate_language(master_srt, reference_lang, deepseek_client, gemini_client, source_lang_name)
        ref_path = os.path.join(output_dir, f"master_{reference_lang}.srt")
        with open(ref_path, "w", encoding="utf-8") as f:
            f.write(reference_srt)
        print(f"    Saved reference: {ref_path}")
        all_outputs.append(ref_path)
        time.sleep(1)
    else:
        reference_srt = master_srt

    if target_langs:
        print(f"\n  Step 3b: Translating from {config.LANG_NAMES.get(reference_lang, reference_lang)} to targets...")
        ref_lang_name = config.LANG_NAMES.get(reference_lang, reference_lang)

        for lang in target_langs:
            if lang == reference_lang:
                print(f"    [{lang}] Already generated as reference, skipping")
                continue
            if lang == source_lang:
                print(f"    [{lang}] Source language, skipping")
                continue

            translated = translate_language(reference_srt, lang, deepseek_client, gemini_client, ref_lang_name)
            output_path = os.path.join(output_dir, f"master_{lang}.srt")
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(translated)
            print(f"    Saved: {output_path}")
            all_outputs.append(output_path)
            time.sleep(1)

    return all_outputs


def run_phase4(input_dir: str, output_dir: str, langs: list, verbose: bool = False):
    """Phase 4: Generate TTS WAV voiceover segments from SRTs
    Returns dict of {lang: list of (wav_path, start_seconds, duration)}.
    """
    import time
    from pipeline.utils import find_ffmpeg
    from pipeline.voice import generate_voiceover

    if not config.vertex_api_key:
        raise RuntimeError("VERTEX_API_KEY not set")

    client = config.create_vertex_client()
    ffmpeg_path = find_ffmpeg()

    print("\n" + "=" * 60)
    print("  Phase 4: TTS Voiceover Generation (WAV Segments)")
    print(f"  Languages: {', '.join(langs)}")
    print("=" * 60)

    wav_dir = os.path.join(output_dir, config.WAV_SEGMENTS_DIR)
    all_segments = {}

    for lang in langs:
        srt_path = os.path.join(input_dir, f"master_{lang}.srt")

        if not os.path.isfile(srt_path):
            print(f"\n  SKIP: {srt_path} not found")
            continue

        print(f"\n  Processing {lang}...")
        try:
            segments = generate_voiceover(srt_path, lang, client, ffmpeg_path, wav_dir)
            all_segments[lang] = segments
        except Exception as e:
            print(f"  ERROR [{lang}]: {e}")
        time.sleep(1)

    return all_segments


def run_phase5(output_dir: str, video_path: str, all_segments: dict, langs: list, verbose: bool = False):
    """Phase 5: Generate FCPXML files for DaVinci Resolve import"""
    from pipeline.utils import find_ffmpeg, ensure_output_video
    from pipeline.fcpxml import build_fcpxml

    ffmpeg_path = find_ffmpeg()

    video_path = ensure_output_video(output_dir, video_path)

    print("\n" + "=" * 60)
    print("  Phase 5: FCPXML Generation")
    print(f"  Languages: {', '.join(langs)}")
    print("=" * 60)

    results = {}

    for lang in langs:
        print(f"\n  Processing {lang}...")
        srt_path = os.path.join(output_dir, f"master_{lang}.srt")
        wav_segments = all_segments.get(lang)

        if not wav_segments:
            print(f"    SKIP: no segments for {lang}")
            continue

        try:
            fcpxml_path = os.path.join(output_dir, f"fcpxml_{lang}.fcpxml")
            build_fcpxml(video_path, srt_path, lang, wav_segments, fcpxml_path, ffmpeg_path)
            results[lang] = fcpxml_path
            size_kb = os.path.getsize(fcpxml_path) / 1024
            print(f"    FCPXML saved: {fcpxml_path} ({size_kb:.1f} KB)")
        except Exception as e:
            print(f"    ERROR [{lang}]: {e}")
            results[lang] = None

    return results


def main():
    parser = argparse.ArgumentParser(description="Foltvilag Multi-Language Video Voiceover Pipeline")
    parser.add_argument("--url", default=None, help="YouTube video URL")
    parser.add_argument("--output", default=config.OUTPUT_DIR, help="Output directory")
    parser.add_argument("--langs", default=None, help="Comma-separated target language codes to generate (default: de,es,fr)")
    parser.add_argument("--reference-lang", default=config.REFERENCE_LANG, help=f"Reference/pivot language for translations (default: {config.REFERENCE_LANG})")
    parser.add_argument("--skip-phase", default="", help="Comma-separated phases to skip (e.g. '2,5')")
    parser.add_argument("--transcribe", action="store_true", help="Enable audio transcription (Phase 1.5)")
    parser.add_argument("--audio-path", default=None, help="Standalone audio file for transcription (skip video download)")
    parser.add_argument("--transcriber", default=config.AUDIO_TRANSCRIBER, help=f"Transcriber model (default: {config.AUDIO_TRANSCRIBER})")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()

    if not args.url and not args.audio_path:
        parser.error("Either --url or --audio-path must be provided")

    skip = set(args.skip_phase.split(",")) if args.skip_phase else set()

    target_langs = args.langs.split(",") if args.langs else config.TARGET_LANGS
    for lang in target_langs:
        if lang not in config.LANG_NAMES:
            print(f"ERROR: Unknown language code in --langs: {lang}")
            sys.exit(1)
    reference_lang = args.reference_lang
    if reference_lang not in config.LANG_NAMES:
        print(f"ERROR: Unknown reference language code: {reference_lang}")
        sys.exit(1)
    source_lang = config.SOURCE_LANG

    all_langs = [source_lang]
    if reference_lang != source_lang and reference_lang not in all_langs:
        all_langs.append(reference_lang)
    for lang in target_langs:
        if lang not in all_langs:
            all_langs.append(lang)

    print("=" * 60)
    print("  Foltvilag Pipeline")
    if args.url:
        print(f"  URL: {args.url}")
    if args.audio_path:
        print(f"  Audio: {args.audio_path}")
    print(f"  Output: {args.output}")
    print(f"  Transcribe: {'yes' if args.transcribe or args.audio_path else 'no'}")
    print(f"  Source: {config.LANG_NAMES.get(source_lang, source_lang)} ({source_lang})")
    print(f"  Reference: {config.LANG_NAMES.get(reference_lang, reference_lang)} ({reference_lang})")
    print(f"  Targets: {', '.join(target_langs)}")
    print(f"  All outputs: {', '.join(all_langs)}")
    print(f"  Vertex AI: {config.VERTEX_PROJECT} ({config.VERTEX_LOCATION})")
    print("=" * 60)

    os.makedirs(args.output, exist_ok=True)
    os.makedirs(config.TEMP_DIR, exist_ok=True)

    video_path = None
    all_segments = {}
    transcribe_did_run = False

    # Phase 1.5 or Phase 2 (transcription path)
    if args.audio_path and not args.url:
        if "1.5" not in skip and "2" not in skip:
            try:
                run_phase1_5(args.audio_path, args.output, source_lang, args.transcriber, args.verbose)
                transcribe_did_run = True
            except Exception as e:
                print(f"\n  Phase 1.5 FAILED: {e}")
                sys.exit(1)
    elif args.url:
        if "2" not in skip:
            use_transcribe = args.transcribe and "1.5" not in skip

            if use_transcribe:
                try:
                    from pipeline.eyes import download_video, analyze_video, _validate_srt
                    temp_video_path = os.path.join(config.TEMP_DIR, "video.mp4")
                    video_path = download_video(args.url, temp_video_path)
                    print(f"    Downloaded: {video_path}")

                    run_phase1_5(video_path, args.output, source_lang, args.transcriber, args.verbose)
                    transcribe_did_run = True

                    client = config.create_vertex_client()
                    print("=" * 60)
                    print("  Phase 2: Video → SRT Analysis")
                    print(f"  URL: {args.url}")
                    print("=" * 60)
                    srt_text = analyze_video(video_path, client)
                    srt_text = _validate_srt(srt_text)
                    vision_path = os.path.join(args.output, "master_hu_vision.srt")
                    with open(vision_path, "w", encoding="utf-8") as f:
                        f.write(srt_text)
                    print(f"    Vision SRT saved: {vision_path}")
                except Exception as e:
                    print(f"\n  Phase 2+1.5 FAILED: {e}")
                    sys.exit(1)
            else:
                try:
                    _, video_path = run_phase2(args.url, args.output, config.TEMP_DIR,
                                                verbose=args.verbose)
                except Exception as e:
                    print(f"\n  Phase 2 FAILED: {e}")
                    sys.exit(1)
        else:
            print("\n  Skipping Phase 2")
    else:
        print("\n  No video or audio input provided, skipping Phases 1.5/2")

    if "3" not in skip:
        try:
            run_phase3(args.output, args.output, target_langs, reference_lang, args.verbose)
        except Exception as e:
            print(f"\n  Phase 3 FAILED: {e}")
            sys.exit(1)
    else:
        print("\n  Skipping Phase 3")

    if "4" not in skip:
        try:
            all_segments = run_phase4(args.output, args.output, all_langs, args.verbose)
        except Exception as e:
            print(f"\n  Phase 4 FAILED: {e}")
            sys.exit(1)
    else:
        print("\n  Skipping Phase 4")

    if "5" not in skip:
        try:
            if not video_path:
                video_path = os.path.join(config.TEMP_DIR, "video.mp4")
            if not os.path.isfile(video_path):
                print(f"\n  Phase 5 FAILED: video file not found at {video_path}")
                print(f"  Run Phase 2 first or place a video at {video_path}")
                sys.exit(1)
            run_phase5(args.output, video_path, all_segments, all_langs, args.verbose)
        except Exception as e:
            print(f"\n  Phase 5 FAILED: {e}")
            sys.exit(1)
    else:
        print("\n  Skipping Phase 5")

    print(f"\n{'=' * 60}")
    print(f"  Pipeline complete!")
    if transcribe_did_run:
        vision_path = os.path.join(args.output, "master_hu_vision.srt")
        if os.path.isfile(vision_path):
            print(f"  Audio SRT: {os.path.join(args.output, 'master_hu.srt')}")
            print(f"  Vision SRT: {vision_path}")
    print(f"  Outputs in: {os.path.abspath(args.output)}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
