"""Shared utilities: WAV wrapping, MP3 conversion, SRT parsing, ffmpeg detection."""

import os
import shutil
import wave
import subprocess
import re
from typing import List, Union


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


def pcm_to_wav(pcm_data: bytes, output_path: str, rate: int = 24000, channels: int = 1) -> str:
    """Wrap raw L16 PCM data in a WAV container."""
    sample_width = 2
    with wave.open(output_path, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm_data)
    return output_path


def wav_to_mp3(wav_path: str, mp3_path: str, sample_rate: int = 24000, ffmpeg_path: str = "ffmpeg") -> str:
    """Convert WAV to MP3 using ffmpeg."""
    cmd = [
        ffmpeg_path, "-y",
        "-i", wav_path,
        "-codec:a", "libmp3lame",
        "-b:a", "128k",
        "-ar", str(sample_rate),
        "-ac", "1",
        "-loglevel", "error",
        mp3_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg conversion failed: {result.stderr}")
    return mp3_path


def pcm_to_mp3(pcm_data: bytes, mp3_path: str, sample_rate: int = 24000, ffmpeg_path: str = "ffmpeg") -> str:
    """Pipe raw L16 PCM directly to ffmpeg for MP3 conversion (no intermediate WAV)."""
    cmd = [
        ffmpeg_path, "-y",
        "-f", "s16le",
        "-ar", str(sample_rate),
        "-ac", "1",
        "-i", "pipe:0",
        "-codec:a", "libmp3lame",
        "-b:a", "128k",
        "-ar", str(sample_rate),
        "-ac", "1",
        "-loglevel", "error",
        mp3_path,
    ]
    result = subprocess.run(cmd, capture_output=True, input=pcm_data)
    if result.returncode != 0:
        raise RuntimeError(f"PCM-to-MP3 conversion failed: {result.stderr}")
    return mp3_path


# SRT entry timestamp pattern: 00:00:01,000 --> 00:00:04,000
SRT_TS_RE = re.compile(
    r"(\d+)\s*\n\s*"
    r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*"
    r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*\n\s*"
    r"(.+?)(?=\n\n|\n*\Z)",
    re.MULTILINE | re.DOTALL,
)


def ts_to_seconds(h: int, m: int, s: int, ms: int) -> float:
    """Convert SRT timestamp components to seconds."""
    return h * 3600 + m * 60 + s + ms / 1000.0


def seconds_to_ts(total_seconds: float) -> str:
    """Convert seconds to SRT timestamp string."""
    ms = round((total_seconds - int(total_seconds)) * 1000)
    total_seconds += ms // 1000
    ms %= 1000
    h = int(total_seconds // 3600)
    m = int((total_seconds % 3600) // 60)
    s = int(total_seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def parse_srt(source: Union[str, bytes]) -> List[dict]:
    """
    Parse an SRT file path or text content into a list of entries.
    Each entry: {index, start_seconds, end_seconds, text}
    """
    if os.path.isfile(source):
        with open(source, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        content = source

    entries = []
    for m in SRT_TS_RE.finditer(content):
        idx = int(m.group(1))
        start = ts_to_seconds(
            int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5))
        )
        end = ts_to_seconds(
            int(m.group(6)), int(m.group(7)), int(m.group(8)), int(m.group(9))
        )
        text = m.group(10).strip().replace("\n", " ")
        entries.append({
            "index": idx,
            "start_seconds": start,
            "end_seconds": end,
            "text": text,
        })
    return entries


def build_srt(entries: List[dict]) -> str:
    """Build an SRT string from a list of parsed entries."""
    lines = []
    for e in entries:
        start_ts = seconds_to_ts(e["start_seconds"])
        end_ts = seconds_to_ts(e["end_seconds"])
        lines.append(str(e["index"]))
        lines.append(f"{start_ts} --> {end_ts}")
        lines.append(e["text"])
        lines.append("")
    return "\n".join(lines)


def strip_markdown_fences(text: str) -> str:
    """Strip markdown fenced code blocks (```...```) from text."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text
