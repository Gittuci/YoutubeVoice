from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import imageio_ffmpeg
import numpy as np
import soundfile as sf


ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
VIDEO = ROOT / "output" / "video.mp4"
VOICE = ROOT / "output" / "test_runs" / "2026-09-27_000442" / "eleven_v3_natural_normalized.wav"
VIDEO_SHA256 = "6582AC24DF91F6CBD89F71FCBFAC7E7C7421BAE9489E71C5734F3CDA0887D7FB"
VOICE_SHA256 = "BFDA0A1B260F17E30D94ECF0A0EEE6F8DA3251C6A5463C332AF46CC9E3B49EB0"
VIDEO_DURATION = 86.355011

SPLITS = [
    {"unit": 1, "source_start": 0.00, "source_end": 9.45, "video_start": 1.000000},
    {"unit": 2, "source_start": 9.45, "source_end": 21.21, "video_start": 16.000000},
    {"unit": 3, "source_start": 21.21, "source_end": 30.03, "video_start": 47.000000},
    {"unit": 4, "source_start": 30.03, "source_end": 40.32, "video_start": 73.111053},
]

CAPTIONS = [
    (1.000, 4.340, "A kiszabott hatszög közepére igazítjuk\naz átlátszó sablont,"),
    (4.520, 7.540, "majd a nyílásokon át két gombostűvel\nrögzítjük,"),
    (7.580, 9.780, "hogy hajtogatás közben\nne csússzon el."),
    (16.170, 19.970, "A széleken maradt varrásráhagyást\nsorban a sablonra hajtjuk."),
    (20.130, 27.750, "A sarkoknál az egymásra kerülő textilrétegeket\napró kézi öltésekkel fogjuk össze;\na tű csak a textilen halad át."),
    (47.010, 49.710, "A darabot folyamatosan forgatva\nhaladunk körbe."),
    (49.850, 55.730, "Minden új oldalt a sablon élére simítunk,\nmajd a következő saroknál rögzítjük a hajtást."),
    (73.201, 78.121, "Amikor körbeértünk, elvágjuk a cérnát,\nés kihúzzuk a két rögzítőtűt."),
    (78.261, 83.161, "A sablon ekkor még a textilben marad,\na behajtott hatszögelem pedig elkészült."),
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def srt_time(seconds: float) -> str:
    millis = round(seconds * 1000)
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def run(command: list[str], cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def main() -> None:
    RUN.mkdir(parents=True, exist_ok=True)
    segments_dir = RUN / "segments"
    segments_dir.mkdir(exist_ok=True)

    actual_video_hash = sha256(VIDEO)
    actual_voice_hash = sha256(VOICE)
    if actual_video_hash != VIDEO_SHA256:
        raise RuntimeError(f"Authoritative video hash mismatch: {actual_video_hash}")
    if actual_voice_hash != VOICE_SHA256:
        raise RuntimeError(f"Voice source hash mismatch: {actual_voice_hash}")

    audio, sample_rate = sf.read(VOICE, dtype="float32", always_2d=False)
    if audio.ndim == 2:
        audio = audio.mean(axis=1)
    placed = np.zeros(round(VIDEO_DURATION * sample_rate), dtype=np.float32)
    segment_manifest = []
    fade_samples = max(1, round(0.005 * sample_rate))

    for item in SPLITS:
        source_start = round(item["source_start"] * sample_rate)
        source_end = min(round(item["source_end"] * sample_rate), len(audio))
        segment = audio[source_start:source_end].copy()
        fade_length = min(fade_samples, len(segment) // 2)
        if fade_length:
            segment[:fade_length] *= np.linspace(0.0, 1.0, fade_length, dtype=np.float32)
            segment[-fade_length:] *= np.linspace(1.0, 0.0, fade_length, dtype=np.float32)
        segment_path = segments_dir / f"hu_{item['unit']:02d}.wav"
        sf.write(segment_path, segment, sample_rate, subtype="PCM_16")
        video_start_sample = round(item["video_start"] * sample_rate)
        video_end_sample = video_start_sample + len(segment)
        if video_end_sample > len(placed):
            raise RuntimeError(f"Unit {item['unit']} exceeds the video duration")
        placed[video_start_sample:video_end_sample] += segment
        segment_manifest.append(
            {
                **item,
                "duration": len(segment) / sample_rate,
                "video_end": video_end_sample / sample_rate,
                "path": str(segment_path.relative_to(ROOT)),
                "sha256": sha256(segment_path),
            }
        )

    placed = np.clip(placed, -1.0, 1.0)
    placed_path = RUN / "voiceover_placed.wav"
    sf.write(placed_path, placed, sample_rate, subtype="PCM_16")

    srt_path = RUN / "captions_hu.srt"
    srt_parts = []
    for index, (start, end, text) in enumerate(CAPTIONS, 1):
        srt_parts.append(f"{index}\n{srt_time(start)} --> {srt_time(end)}\n{text}\n")
    srt_path.write_text("\n".join(srt_parts), encoding="utf-8-sig")

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    softsubs = RUN / "preview_hu_softsubs.mp4"
    run(
        [
            ffmpeg, "-y", "-i", str(VIDEO), "-i", str(placed_path), "-i", str(srt_path),
            "-map", "0:v:0", "-map", "1:a:0", "-map", "2:0",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-c:s", "mov_text",
            "-metadata:s:s:0", "language=hun", "-metadata:s:s:0", "title=Magyar",
            "-t", f"{VIDEO_DURATION:.6f}", "-movflags", "+faststart", str(softsubs),
        ]
    )

    burned = RUN / "preview_hu_burned.mp4"
    subtitle_filter = (
        "subtitles=captions_hu.srt:"
        "force_style='FontName=Arial,FontSize=20,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,Alignment=2,MarginV=18'"
    )
    run(
        [
            ffmpeg, "-y", "-i", str(VIDEO), "-i", str(placed_path),
            "-map", "0:v:0", "-map", "1:a:0", "-vf", subtitle_filter,
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k", "-t", f"{VIDEO_DURATION:.6f}",
            "-movflags", "+faststart", str(burned),
        ],
        cwd=RUN,
    )

    for rendered in (softsubs, burned):
        run([ffmpeg, "-v", "error", "-i", str(rendered), "-f", "null", "-"])

    manifest = {
        "purpose": "ElevenLabs Hungarian voice/video/subtitle synchronization preview",
        "production_code_modified": False,
        "video": {
            "path": str(VIDEO.relative_to(ROOT)),
            "sha256": actual_video_hash,
            "duration_seconds": VIDEO_DURATION,
        },
        "voice_source": {
            "path": str(VOICE.relative_to(ROOT)),
            "sha256": actual_voice_hash,
            "variant": "eleven_v3_natural",
            "speed_modified": False,
            "sample_rate": sample_rate,
        },
        "segments": segment_manifest,
        "captions": [
            {"index": i, "start": start, "end": end, "text": text}
            for i, (start, end, text) in enumerate(CAPTIONS, 1)
        ],
        "outputs": {},
    }
    for output in (placed_path, srt_path, softsubs, burned):
        manifest["outputs"][output.name] = {
            "path": str(output.relative_to(ROOT)),
            "sha256": sha256(output),
            "bytes": output.stat().st_size,
        }
    (RUN / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest["outputs"], indent=2))


if __name__ == "__main__":
    main()
