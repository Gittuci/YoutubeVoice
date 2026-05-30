"""Phase 5 — FCPXML Generator: Build DaVinci Resolve-compatible FCPXML from WAV segments."""

import os
import sys
import argparse
import subprocess
import json
import wave
from xml.etree import ElementTree as ET

from pipeline import config
from pipeline.utils import parse_srt, find_ffmpeg


def _get_video_info(video_path: str, ffmpeg_path: str) -> dict:
    """Extract video dimensions, frame rate, and duration via ffprobe."""
    ffmpeg_dir = os.path.dirname(ffmpeg_path)
    ffprobe = os.path.join(ffmpeg_dir, "ffprobe.exe" if ffmpeg_path.endswith(".exe") else "ffprobe")
    if not os.path.isfile(ffprobe):
        import shutil
        ffprobe = shutil.which("ffprobe")
    if not ffprobe or not os.path.isfile(ffprobe):
        raise FileNotFoundError("ffprobe not found alongside ffmpeg")

    cmd = [
        ffprobe, "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate,duration",
        "-of", "json",
        video_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")

    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    if not streams:
        raise RuntimeError("No video stream found")

    stream = streams[0]
    width = stream.get("width", 1920)
    height = stream.get("height", 1080)

    r_frame_rate = stream.get("r_frame_rate", "30000/1001")
    num, den = r_frame_rate.split("/")
    frame_rate = float(num) / float(den)

    duration = float(stream.get("duration", 0))
    if duration == 0:
        cmd2 = [
            ffprobe, "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path,
        ]
        result2 = subprocess.run(cmd2, capture_output=True, text=True)
        if result2.returncode == 0 and result2.stdout.strip():
            duration = float(result2.stdout.strip())

    return {
        "width": width,
        "height": height,
        "frame_rate": frame_rate,
        "duration": duration,
        "r_frame_rate": r_frame_rate,
    }


def _format_fcpxml_time(seconds: float, timebase: int) -> str:
    """Format seconds as FCPXML rational time (e.g., '75/30s' for 2.5s at 30fps)."""
    ticks = int(round(seconds * timebase))
    return f"{ticks}/{timebase}s"


def build_fcpxml(video_path: str, srt_path: str, lang: str, wav_segments: list,
                 output_path: str, ffmpeg_path: str) -> str:
    """Build an FCPXML file from video, SRT timestamps, and WAV audio segments.

    Uses frame-based rational time — audio clips are anchored directly to the
    spine at exact frame offsets, eliminating cumulative gap-drift.

    Args:
        video_path: Path to the original video file.
        srt_path: Path to the per-language SRT file.
        lang: Language code (e.g. 'de', 'es', 'fr').
        wav_segments: List of (wav_path, start_seconds, duration) tuples.
        output_path: Path where the .fcpxml file will be written.
        ffmpeg_path: Path to ffmpeg executable.

    Returns:
        The output_path of the generated FCPXML file.
    """
    video_info = _get_video_info(video_path, ffmpeg_path)
    video_duration = video_info["duration"]
    frame_rate = video_info["frame_rate"]
    frame_rate_int = int(round(frame_rate))

    abs_video_path = os.path.abspath(video_path).replace("\\", "/")
    format_id = "r1"
    video_asset_id = "r2"

    ET.register_namespace("", "http://www.apple.com/finalcutpro/fcpxml/1.2")
    root = ET.Element("fcpxml", {"version": "1.12"})
    resources = ET.SubElement(root, "resources")

    format_elem = ET.SubElement(resources, "format", {
        "id": format_id,
        "name": f"FFVideoFormat{frame_rate_int}p{video_info['height']}",
        "frameDuration": f"1001/30000s" if video_info["r_frame_rate"] == "30000/1001" else f"1/{frame_rate_int}s",
        "width": str(video_info["width"]),
        "height": str(video_info["height"]),
        "colorSpace": "1-1-1 (Rec. 709)",
    })

    vid_dur_frames = _format_fcpxml_time(video_duration, frame_rate_int)
    vid_asset = ET.SubElement(resources, "asset", {
        "id": video_asset_id,
        "name": os.path.basename(video_path),
        "src": f"file:///{abs_video_path}",
        "start": f"0/{frame_rate_int}s",
        "duration": vid_dur_frames,
        "hasAudio": "1",
        "audioChannels": "2",
        "audioRate": "48000",
    })

    wav_assets = []
    audio_sample_rate = config.SAMPLE_RATE
    for i, (wav_path, start_s, seg_duration) in enumerate(wav_segments):
        asset_id = f"r3_wav_{i + 1}"
        abs_wav = os.path.abspath(wav_path).replace("\\", "/")
        wav_dur_str = _format_fcpxml_time(seg_duration, audio_sample_rate)
        wav_asset = ET.SubElement(resources, "asset", {
            "id": asset_id,
            "name": os.path.basename(wav_path),
            "src": f"file:///{abs_wav}",
            "start": f"0/{audio_sample_rate}s",
            "duration": wav_dur_str,
            "hasAudio": "1",
            "audioChannels": "1",
            "audioRate": str(audio_sample_rate),
        })
        wav_assets.append((asset_id, start_s, seg_duration, os.path.basename(wav_path)))

    lang_name = config.LANG_NAMES.get(lang, lang.upper())
    library = ET.SubElement(root, "library", {
        "location": f"file:///{os.path.abspath(output_path).replace(chr(92), '/')}",
    })
    event = ET.SubElement(library, "event", {"name": f"Foltvilag_{lang.upper()}"})
    project = ET.SubElement(event, "project", {"name": f"Voiceover_{lang.upper()}"})
    sequence = ET.SubElement(project, "sequence", {
        "format": format_id,
        "duration": vid_dur_frames,
    })
    spine = ET.SubElement(sequence, "spine")

    video_audio_samples = int(round(video_duration * 48000))
    vid_clip = ET.SubElement(spine, "asset-clip", {
        "ref": video_asset_id,
        "offset": f"0/{frame_rate_int}s",
        "name": "original_video",
        "start": f"0/{frame_rate_int}s",
        "duration": vid_dur_frames,
        "audioRole": "dialogue",
        "audioStart": "0/48000s",
        "audioDuration": f"{video_audio_samples}/48000s",
    })
    ET.SubElement(vid_clip, "adjust-volume", {"amount": "-inf"})

    for asset_id, start_s, seg_duration, wav_name in wav_assets:
        offset_str = _format_fcpxml_time(start_s, frame_rate_int)
        wav_dur_str = _format_fcpxml_time(seg_duration, audio_sample_rate)
        ET.SubElement(spine, "asset-clip", {
            "ref": asset_id,
            "offset": offset_str,
            "name": wav_name,
            "start": f"0/{audio_sample_rate}s",
            "duration": wav_dur_str,
        })

    tree = ET.ElementTree(root)
    ET.indent(tree, space="    ")
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    tree.write(output_path, encoding="UTF-8", xml_declaration=True)
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Phase 5: Generate FCPXML for DaVinci Resolve")
    parser.add_argument("--lang", required=True, help="Language code (e.g. de, es, fr)")
    parser.add_argument("--srt", required=True, help="Path to per-language SRT file")
    parser.add_argument("--wav-dir", required=True, help="Directory containing WAV segments")
    parser.add_argument("--video", required=True, help="Path to original video file")
    parser.add_argument("--output", required=True, help="Output .fcpxml file path")
    args = parser.parse_args()

    ffmpeg_path = find_ffmpeg()

    if not os.path.isfile(args.srt):
        print(f"ERROR: SRT file not found: {args.srt}")
        sys.exit(1)

    if not os.path.isfile(args.video):
        print(f"ERROR: Video file not found: {args.video}")
        sys.exit(1)

    entries = parse_srt(args.srt)
    if not entries:
        print(f"ERROR: No SRT entries found in {args.srt}")
        sys.exit(1)

    wav_segments = []
    for i, entry in enumerate(entries):
        wav_filename = f"{args.lang}_seg_{i:04d}.wav"
        wav_path = os.path.join(args.wav_dir, wav_filename)
        if not os.path.isfile(wav_path):
            print(f"WARNING: WAV segment not found: {wav_path}, skipping")
            continue
        with wave.open(wav_path, "rb") as wf:
            framerate = wf.getframerate()
            nframes = wf.getnframes()
            wav_dur = nframes / framerate if framerate > 0 else 0.0
        wav_segments.append((wav_path, entry["start_seconds"], wav_dur))

    print("=" * 60)
    print("  Phase 5: FCPXML Generation")
    print(f"  Language: {args.lang}")
    print(f"  SRT: {args.srt}")
    print(f"  WAV segments: {len(wav_segments)}/{len(entries)}")
    print(f"  Video: {args.video}")
    print("=" * 60)

    output_path = build_fcpxml(args.video, args.srt, args.lang, wav_segments, args.output, ffmpeg_path)

    size_kb = os.path.getsize(output_path) / 1024
    print(f"\n  FCPXML saved: {output_path} ({size_kb:.1f} KB)")
    print(f"{'=' * 60}")
    print(f"  Phase 5 complete")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
