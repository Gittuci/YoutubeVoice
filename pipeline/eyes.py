"""Phase 2 — Video Analysis: YouTube video → SRT via Gemini vision."""

import os
import sys
import time
import argparse
import yt_dlp

from google import genai
from google.genai import types

from pipeline import config
from pipeline.utils import parse_srt


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


def _clean_srt_response(text: str) -> str:
    """Strip markdown fenced code blocks and leading/trailing whitespace."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def analyze_video(video_path: str, client: genai.Client) -> str:
    """Upload video to Gemini and get Hungarian SRT analysis."""
    print(f"  Uploading {os.path.basename(video_path)} to Gemini File API...")
    video_file = client.files.upload(
        file=video_path,
        config=types.FileConfig(display_name="youtube_video"),
    )

    print("  Waiting for video processing...")
    timeout = 120
    deadline = time.time() + timeout
    while video_file.state != "ACTIVE":
        if time.time() > deadline:
            raise TimeoutError(f"Video processing timed out after {timeout}s. State: {video_file.state}")
        time.sleep(2)
        video_file = client.files.get(name=video_file.name)
    print(f"  Video ready (state={video_file.state})")

    prompt = """You are watching a mute patchwork/quilt instructional video using EZ-Log and EZpiecer templates.
Only hands and templates are visible — no face, no lip movement.

Analyze this video carefully and describe each distinct visual step shown on screen,
including what the hands are doing at each moment.

For each step, output an SRT entry with:
  - The exact timestamp range (HH:MM:SS,mmm --> HH:MM:SS,mmm) when that action is visible.
  - Instructional, friendly Hungarian narration text explaining the step for the viewer.
  - Each entry must fit within its timestamp — keep text concise enough to be spoken naturally.

Output valid SRT format only. No commentary, no markdown. Just the SRT entries."""

    print("  Sending analysis prompt to Gemini...")
    response = client.models.generate_content(
        model=config.GEMINI_VISION_MODEL,
        contents=[video_file, prompt],
    )

    if not response.candidates:
        raise RuntimeError("No candidates returned — response may be blocked or rate-limited")

    text = response.text or ""
    text = _clean_srt_response(text)
    return text


def _validate_srt(text: str, max_retries: int = 2) -> str:
    """Validate SRT text by parsing. Retry with stricter prompt on failure."""
    for attempt in range(max_retries + 1):
        try:
            entries = parse_srt_from_text(text)
            if not entries:
                raise ValueError("No SRT entries parsed")
            print(f"  Parsed {len(entries)} SRT entries")
            return text
        except Exception as e:
            if attempt < max_retries:
                print(f"  SRT parse attempt {attempt + 1} failed: {e}. Retrying...")
                text = _refine_srt(text)
            else:
                raise RuntimeError(f"SRT validation failed after {max_retries} retries: {e}")


def _refine_srt(text: str) -> str:
    """Strip non-SRT content more aggressively."""
    lines = text.split("\n")
    filtered = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("`"):
            filtered.append(line)
    return "\n".join(filtered)


def parse_srt_from_text(text: str):
    """Parse SRT from raw text given that parse_srt reads from a file."""
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".srt", delete=False, encoding="utf-8") as f:
        f.write(text)
        tmp_path = f.name
    try:
        entries = parse_srt(tmp_path)
    finally:
        os.unlink(tmp_path)
    return entries


def main():
    parser = argparse.ArgumentParser(description="Phase 2: Video → SRT analysis")
    parser.add_argument("--url", required=True, help="YouTube video URL")
    parser.add_argument("--output", default=config.OUTPUT_DIR, help="Output directory")
    args = parser.parse_args()

    if not config.google_api_key:
        print("ERROR: GOOGLE_API_KEY not set. Check your .env file.")
        sys.exit(1)

    os.makedirs(args.output, exist_ok=True)
    os.makedirs(config.TEMP_DIR, exist_ok=True)

    client = genai.Client(api_key=config.google_api_key)

    print("=" * 60)
    print("  Phase 2: Video → SRT Analysis")
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
