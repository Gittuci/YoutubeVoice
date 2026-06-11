"""Phase 1.5 — Audio Transcription: Audio → SRT with tone/intonation markers."""

import os
import sys
import abc
import argparse
import subprocess
from typing import Optional

from google import genai
from google.genai import types

from pipeline import config
from pipeline.utils import find_ffmpeg, safe_print


class Transcriber(abc.ABC):
    """Abstract interface for speech-to-text transcription with tone/emotion tagging."""

    @abc.abstractmethod
    def transcribe(self, audio_path: str, language: str = "hu") -> str:
        """Transcribe audio into SRT text with inline tone tags.
        Returns raw SRT string ready to write to file.
        """
        ...


class GeminiAudioTranscriber(Transcriber):
    """Transcribe audio via Gemini Audio API (gemini-2.5-flash)."""

    def __init__(self, client: Optional[genai.Client] = None):
        self._client = client

    def _get_client(self) -> genai.Client:
        if self._client is not None:
            return self._client
        return config.create_vertex_client()

    def transcribe(self, audio_path: str, language: str = "hu") -> str:
        client = self._get_client()
        lang_name = config.LANG_NAMES.get(language, language)

        prompt = config.load_prompt("audio_transcription.txt")
        prompt = f"{prompt}\n\nThe audio language is {lang_name}."

        with open(audio_path, "rb") as f:
            audio_bytes = f.read()

        response = client.models.generate_content(
            model=config.GEMINI_AUDIO_MODEL,
            contents=[
                types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"),
                prompt,
            ],
        )

        if not response.candidates:
            raise RuntimeError("Transcription failed: no candidates returned from Gemini")

        text = response.text or ""
        return text


def get_transcriber(name: str = "gemini", **kwargs) -> Transcriber:
    """Factory: return a Transcriber by name."""
    name = name.lower()
    if name == "gemini":
        return GeminiAudioTranscriber(**kwargs)
    raise ValueError(f"Unknown transcriber: {name}")


def _check_audio_stream(video_path: str, ffmpeg_path: str) -> Optional[float]:
    """Check if video has an audio stream. Returns duration in seconds, or None."""
    try:
        result = subprocess.run(
            [ffmpeg_path, "-i", video_path, "-hide_banner"],
            capture_output=True, text=True,
        )
        stderr = result.stderr
        in_dur = "Duration:" in stderr and "Audio:" in stderr
        if not in_dur:
            return None
        duration_line = [l for l in stderr.split("\n") if "Duration:" in l]
        if duration_line:
            parts = duration_line[0].split("Duration:")[1].split(",")[0].strip()
            h, m, s = parts.split(":")
            return float(h) * 3600 + float(m) * 60 + float(s)
        return None
    except Exception:
        return None


def extract_audio(video_path: str, output_path: str, ffmpeg_path: Optional[str] = None) -> str:
    """Extract audio from a video file as 16kHz mono WAV.

    Args:
        video_path: Path to video file (mp4, webm, etc.)
        output_path: Path to write extracted WAV audio
        ffmpeg_path: Path to ffmpeg executable (auto-detected if None)

    Returns output_path on success.
    """
    if ffmpeg_path is None:
        ffmpeg_path = find_ffmpeg()

    duration = _check_audio_stream(video_path, ffmpeg_path)
    if duration is None:
        raise RuntimeError(f"No audio stream found in video: {video_path}")
    if duration < 1.0:
        raise RuntimeError(f"Audio duration too short ({duration:.1f}s) — skipping transcription")

    parent_dir = os.path.dirname(output_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    cmd = [
        ffmpeg_path, "-y",
        "-i", video_path,
        "-ac", "1",
        "-ar", "16000",
        "-f", "wav",
        "-loglevel", "error",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Audio extraction failed: {result.stderr}")

    return output_path


SUPPORTED_AUDIO_EXTS = {".wav", ".mp3", ".flac", ".ogg", ".opus", ".aac", ".m4a", ".webm"}


def _is_audio_file(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    return ext in SUPPORTED_AUDIO_EXTS


def _is_video_file(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    return ext in {".mp4", ".webm", ".mkv", ".mov", ".avi"}


def run_transcription(input_path: str, output_dir: str, transcriber_name: str = "gemini",
                      language: str = "hu", ffmpeg_path: Optional[str] = None) -> str:
    """Run transcription on an audio or video file, writing master_{lang}.srt.

    For video files, audio is extracted first as 16kHz mono WAV.
    For audio files, they are used directly (ffmpeg is used to convert to WAV if needed).

    Returns path to the written SRT file.
    """
    if ffmpeg_path is None:
        ffmpeg_path = find_ffmpeg()

    os.makedirs(output_dir, exist_ok=True)

    if _is_video_file(input_path):
        safe_print(f"  Extracting audio from video: {input_path}")
        audio_path = os.path.join(output_dir, "audio.wav")
        extract_audio(input_path, audio_path, ffmpeg_path)
        safe_print(f"    Extracted audio: {audio_path}")
        is_temp_audio = True
    elif _is_audio_file(input_path) or input_path.lower().endswith(".wav"):
        if input_path.lower().endswith(".wav"):
            audio_path = input_path
            is_temp_audio = False
        else:
            safe_print(f"  Converting audio to WAV: {input_path}")
            audio_path = os.path.join(output_dir, "audio.wav")
            cmd = [
                ffmpeg_path, "-y",
                "-i", input_path,
                "-ac", "1",
                "-ar", "16000",
                "-f", "wav",
                "-loglevel", "error",
                audio_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"Audio conversion failed: {result.stderr}")
            is_temp_audio = True
    else:
        raise ValueError(f"Unsupported input format: {input_path}")

    safe_print(f"  Transcribing audio with {transcriber_name}...")
    transcriber = get_transcriber(transcriber_name)
    srt_text = transcriber.transcribe(audio_path, language)

    if not srt_text or not srt_text.strip():
        raise RuntimeError("Transcription produced empty output")

    srt_path = os.path.join(output_dir, f"master_{language}.srt")
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt_text)

    safe_print(f"    SRT saved: {srt_path} ({len(srt_text)} chars)")

    if is_temp_audio and os.path.isfile(audio_path):
        try:
            os.remove(audio_path)
        except OSError:
            pass

    return srt_path


def main():
    parser = argparse.ArgumentParser(description="Phase 1.5: Audio → SRT Transcription")
    parser.add_argument("--input", required=True, help="Input video or audio file")
    parser.add_argument("--output", default=config.OUTPUT_DIR, help="Output directory")
    parser.add_argument("--transcriber", default=config.AUDIO_TRANSCRIBER, help="Transcriber: gemini (default)")
    parser.add_argument("--language", default="hu", help="Language code of the audio (default: hu)")
    args = parser.parse_args()

    if not config.vertex_api_key:
        safe_print("ERROR: VERTEX_API_KEY not set. Check your .env file.")
        sys.exit(1)

    safe_print("=" * 60)
    safe_print("  Phase 1.5: Audio Transcription")
    safe_print(f"  Input: {args.input}")
    safe_print(f"  Transcriber: {args.transcriber}")
    safe_print(f"  Language: {args.language}")
    safe_print("=" * 60)

    try:
        srt_path = run_transcription(args.input, args.output, args.transcriber, args.language)
        safe_print(f"\n  Transcription complete: {srt_path}")
    except Exception as e:
        safe_print(f"\n  Transcription failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
