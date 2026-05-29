"""Phase 5 — Assembly: Verify and optionally mux voiceover MP3s with video."""

import os
import sys
import shutil
import subprocess
import argparse
import struct

from pipeline import config
from pipeline.utils import parse_srt


def find_ffmpeg() -> str:
    """Find ffmpeg executable. Returns path or raises FileNotFoundError."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return ffmpeg
    explicit = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "ffmpeg", "bin", "ffmpeg.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "ffmpeg", "ffmpeg.exe"),
        os.path.join(os.environ.get("ProgramFiles", ""), "ffmpeg", "bin", "ffmpeg.exe"),
    ]
    for p in explicit:
        if os.path.isfile(p):
            try:
                result = subprocess.run([p, "-version"], capture_output=True)
                if result.returncode == 0:
                    return p
            except (FileNotFoundError, OSError):
                continue
    raise FileNotFoundError(
        "ffmpeg not found. Install with: winget install ffmpeg\n"
        "Or download from: https://ffmpeg.org/download.html"
    )


def get_mp3_duration(mp3_path: str, ffmpeg_path: str) -> float:
    """Get duration of an MP3 file in seconds using ffprobe or ffmpeg."""
    ffprobe = ffmpeg_path.replace("ffmpeg.exe", "ffprobe.exe").replace("ffmpeg", "ffprobe")
    if not os.path.isfile(ffprobe):
        ffprobe = shutil.which("ffprobe") or ffmpeg_path

    cmd = [
        ffprobe, "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        mp3_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")

    try:
        return float(result.stdout.strip())
    except ValueError:
        cmd2 = [
            ffmpeg_path, "-i", mp3_path,
            "-f", "null", "-",
        ]
        result2 = subprocess.run(cmd2, capture_output=True, text=True)
        for line in result2.stderr.split("\n"):
            if "Duration:" in line:
                parts = line.strip().split("Duration: ")[1].split(",")[0].split(":")
                h, m, s = int(parts[0]), int(parts[1]), float(parts[2])
                return h * 3600 + m * 60 + s
        raise RuntimeError("Could not determine MP3 duration")


def verify_alignment(mp3_path: str, srt_path: str, lang: str, ffmpeg_path: str) -> bool:
    """Verify that MP3 duration matches SRT end timestamp."""
    entries = parse_srt(srt_path)
    if not entries:
        print(f"  [{lang}] No SRT entries found")
        return False

    last_end = entries[-1]["end_seconds"]
    mp3_duration = get_mp3_duration(mp3_path, ffmpeg_path)

    diff_pct = abs(mp3_duration - last_end) / max(last_end, 0.001) * 100

    print(f"  [{lang}] MP3: {mp3_duration:.1f}s, SRT ends: {last_end:.1f}s ({diff_pct:.1f}% diff)")
    if diff_pct > 10:
        print(f"  [{lang}] WARNING: duration mismatch >10%")
        return False
    return True


def mux_video_audio(video_path: str, mp3_path: str, output_path: str, ffmpeg_path: str) -> str:
    """Mux video with MP3 audio into an MP4 file using ffmpeg."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    cmd = [
        ffmpeg_path, "-y",
        "-i", video_path,
        "-i", mp3_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", config.MP3_BITRATE,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
        "-loglevel", "error",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg mux failed: {result.stderr}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Phase 5: Audio-Video Assembly")
    parser.add_argument("--input-dir", default=config.OUTPUT_DIR, help="Directory with voiceover MP3s and SRTs")
    parser.add_argument("--output-dir", default=config.OUTPUT_DIR, help="Output directory")
    parser.add_argument("--with-video", default=None, help="Original video path to mux with (enables video mode)")
    parser.add_argument("--langs", default=None, help="Comma-separated language codes")
    args = parser.parse_args()

    langs = args.langs.split(",") if args.langs else ["hu"] + config.TARGET_LANGS

    ffmpeg_path = find_ffmpeg()

    print("=" * 60)
    print("  Phase 5: Audio-Video Assembly")
    print(f"  Languages: {', '.join(langs)}")
    print("=" * 60)

    results = {}
    for lang in langs:
        print(f"\n  Processing {lang}...")
        mp3_path = os.path.join(args.input_dir, f"voiceover_{lang}.mp3")
        srt_path = os.path.join(args.input_dir, f"master_{lang}.srt")

        if not os.path.isfile(mp3_path):
            print(f"    SKIP: {mp3_path} not found")
            continue
        if not os.path.isfile(srt_path):
            print(f"    SKIP: {srt_path} not found")
            continue

        try:
            aligned = verify_alignment(mp3_path, srt_path, lang, ffmpeg_path)
            results[lang] = {"mp3": mp3_path, "aligned": aligned}

            if args.with_video and os.path.isfile(args.with_video):
                video_output = os.path.join(args.output_dir, f"video_{lang}.mp4")
                mux_video_audio(args.with_video, mp3_path, video_output, ffmpeg_path)
                results[lang]["video"] = video_output
                size_kb = os.path.getsize(video_output) / 1024
                print(f"    Video saved: {video_output} ({size_kb:.1f} KB)")
        except Exception as e:
            print(f"    ERROR [{lang}]: {e}")
            results[lang] = {"mp3": mp3_path, "aligned": False, "error": str(e)}

    print(f"\n{'=' * 60}")
    print(f"  Phase 5 complete")
    print(f"{'=' * 60}")
    if results:
        print(f"\n  Summary:")
        for lang, info in sorted(results.items()):
            status = "OK" if info.get("aligned") else "FAIL"
            files = [os.path.basename(f) for k, f in info.items() if k in ("mp3", "video")]
            print(f"    [{lang}] {status} — {', '.join(files)}")


if __name__ == "__main__":
    main()
