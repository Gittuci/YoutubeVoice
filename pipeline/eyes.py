"""Phase 2 -- Video Analysis: YouTube video -> SRT via Gemini vision."""

import os
import sys
import argparse
import re
import yt_dlp

from google import genai
from google.genai import types

from pipeline import config
from pipeline.utils import parse_srt, strip_markdown_fences


def download_video(url: str, output_path: str) -> str:
    """Download a YouTube video to the given path using yt-dlp."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    basename = os.path.splitext(output_path)[0]
    ydl_opts = {
        "format": "mp4[height<=720]",
        "outtmpl": f"{basename}.%(ext)s",
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        output_path = ydl.prepare_filename(info)
    return output_path


def analyze_video(video_path: str, client: genai.Client) -> str:
    """Analyze video via Vertex AI Gemini (inline bytes, no File API upload)."""
    print(f"  Reading {os.path.basename(video_path)} into memory...")
    with open(video_path, "rb") as f:
        video_bytes = f.read()

    video_part = types.Part.from_bytes(data=video_bytes, mime_type="video/mp4")

    prompt = """You are watching a mute patchwork/quilt instructional video using EZ-Log and EZpiecer templates.
Only hands and templates are visible -- no face, no lip movement.

Analyze this video carefully and describe each distinct visual step shown on screen,
including what the hands are doing at each moment.

For each step, output an SRT entry with:
  - The exact timestamp range (HH:MM:SS,mmm --> HH:MM:SS,mmm) when that action is visible.
  - Instructional, friendly Hungarian narration text explaining the step for the viewer.
  - Each entry must fit within its timestamp -- keep text concise enough to be spoken naturally.

Output valid SRT format only. No commentary, no markdown. Just the SRT entries."""

    print("  Sending analysis prompt to Gemini...")
    response = client.models.generate_content(
        model=config.GEMINI_VISION_MODEL,
        contents=[video_part, prompt],
    )

    if not response.candidates:
        raise RuntimeError("No candidates returned -- response may be blocked or rate-limited")

    text = response.text or ""
    return text


def _validate_srt(text: str, max_retries: int = 2) -> str:
    """Validate SRT text by parsing. Applies repair/refine before each attempt."""
    raw = text
    for attempt in range(max_retries + 1):
        cleaned = strip_markdown_fences(text)
        cleaned = _repair_srt_timestamps(cleaned)
        cleaned = _refine_srt(cleaned)
        try:
            entries = parse_srt(cleaned)
            if not entries:
                raise ValueError("No SRT entries parsed")
            print(f"  Parsed {len(entries)} SRT entries")
            return cleaned
        except Exception as e:
            if attempt == 0:
                print(f"  --- RAW response preview ({len(raw)} chars) ---")
                print(raw[:500])
                print(f"  --- END RAW PREVIEW ---")
            if attempt < max_retries:
                print(f"  SRT parse attempt {attempt + 1} failed: {e}. Retrying...")
            else:
                print(f"  --- DEBUG: Cleaned text ({len(cleaned)} chars) ---")
                print(cleaned[:1000])
                print(f"  --- END DEBUG ---")
                raise RuntimeError(f"SRT validation failed after {max_retries} retries: {e}")


def _refine_srt(text: str) -> str:
    """Strip non-SRT content more aggressively. Preserves blank lines (SRT separators)."""
    lines = text.split("\n")
    filtered = []
    for line in lines:
        stripped = line.strip()
        if not stripped or (not stripped.startswith("#") and not stripped.startswith("`")):
            filtered.append(line)
    return "\n".join(filtered)


def _repair_srt_timestamps(text: str) -> str:
    """Fix common Gemini timestamp formatting errors (e.g., 0000:41,500 -> 00:00:41,500)."""
    text = re.sub(
        r'^(\d{4}):(\d{2}),(\d{3})',
        r'00:\2,\3',
        text,
        flags=re.MULTILINE,
    )
    return text


def main():
    parser = argparse.ArgumentParser(description="Phase 2: Video -> SRT analysis")
    parser.add_argument("--url", required=True, help="YouTube video URL")
    parser.add_argument("--output", default=config.OUTPUT_DIR, help="Output directory")
    args = parser.parse_args()

    if not config.vertex_api_key:
        print("ERROR: VERTEX_API_KEY not set. Check your .env file.")
        sys.exit(1)

    os.makedirs(args.output, exist_ok=True)
    os.makedirs(config.TEMP_DIR, exist_ok=True)

    client = config.create_vertex_client()

    print("=" * 60)
    print("  Phase 2: Video -> SRT Analysis")
    print(f"  URL: {args.url}")
    print("=" * 60)

    temp_video_path = os.path.join(config.TEMP_DIR, "video.mp4")
    print(f"\nDownloading video from YouTube...")
    actual_path = download_video(args.url, temp_video_path)
    print(f"  Downloaded: {actual_path}")

    try:
        srt_text = analyze_video(actual_path, client)
        srt_text = _validate_srt(srt_text)

        output_path = os.path.join(args.output, "master_hu.srt")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(srt_text)
        print(f"\n  SRT saved: {output_path}")
        print(f"{'=' * 60}")
        print(f"  Phase 2 complete: {output_path}")
        print(f"{'=' * 60}")
    finally:
        if os.path.isfile(actual_path):
            os.unlink(actual_path)
            print(f"  Cleaned up: {actual_path}")


if __name__ == "__main__":
    main()
