# Foltvilag — Multi-Language Video Voiceover Pipeline

Automatically generates multi-language voiceovers for mute YouTube instructional videos.
Takes a YouTube URL, produces time-aligned Hungarian narration, translates it to
German/Spanish/French, and generates MP3 voiceovers with Gemini TTS.

---

## Blueprint (Architecture)

### File Inventory

```
├── .env.example           # Template for API keys (commit-safe)
├── .gitignore             # Excludes .env, output/, temp/, media files
├── requirements.txt       # google-genai, openai, yt-dlp, ffmpeg-python, moviepy, python-dotenv
├── poc_tts.py             # Phase 1 proof-of-concept (standalone TTS test)
├── run_pipeline.py        # Orchestrator: runs phases 2->5
└── pipeline/
    ├── __init__.py         # Package marker
    ├── config.py           # Centralized settings, .env loader, voice map, model names
    ├── utils.py            # Shared: find_ffmpeg, PCM/MP3/WAV, parse_srt, build_srt, strip_markdown_fences
    ├── eyes.py             # Phase 2: YouTube download -> Gemini vision -> Hungarian SRT
    ├── brains.py           # Phase 3: SRT translation (DeepSeek + Gemini fallback)
    ├── voice.py            # Phase 4: SRT -> TTS audio segments -> aligned MP3
    └── assembly.py         # Phase 5: MP3/SRT alignment verification, video+audio mux
```

### Phase Modules

| Phase | Module | Input | Output | API Used |
|-------|--------|-------|--------|----------|
| 2 | pipeline/eyes.py | YouTube URL | output/master_hu.srt | Gemini 2.5 Flash (vision) |
| 3 | pipeline/brains.py | master_hu.srt | master_{de,es,fr}.srt | DeepSeek (primary) / Gemini (fallback) |
| 4 | pipeline/voice.py | master_{hu,de,es,fr}.srt | voiceover_{hu,de,es,fr}.mp3 | Gemini 3.1 Flash TTS |
| 5 | pipeline/assembly.py | MP3s + SRTs | Alignment report; optional video_{lang}.mp4 | ffmpeg (local) |

### Data Flow

```
YouTube URL
    |
    v  [Phase 2: eyes.py]
yt-dlp download -> Gemini File API upload -> video analysis
    |
    v
output/master_hu.srt  (Hungarian narration, timestamped)
    |
    v  [Phase 3: brains.py]
DeepSeek api -> translate -> validate timestamps -> fallback to Gemini
    |
    v
output/master_de.srt, master_es.srt, master_fr.srt
    |
    v  [Phase 4: voice.py]
Parse SRT -> voice validation -> Gemini TTS per segment -> align & concat
    |
    v
output/voiceover_hu.mp3, voiceover_de.mp3, voiceover_es.mp3, voiceover_fr.mp3
    |
    v  [Phase 5: assembly.py]
Verify MP3 duration vs SRT -> optional ffmpeg mux -> video_{lang}.mp4
```

### Key Design Decisions

- **PCM pipeline** — Gemini TTS returns raw L16 PCM. We pipe directly to ffmpeg
  for MP3 encoding (no intermediate WAV files).
- **Voice validation** — Before generating per-language voiceovers, a lightweight
  API call confirms the voice name is valid. Falls back through a priority chain.
- **Translation validation** — Entry count and timestamps are compared
  byte-for-byte against the master SRT. DeepSeek is the primary translator;
  Gemini is the fallback after 3 failed retries.
- **Segment alignment** — Each TTS segment is trimmed or padded to fit its SRT
  window. Between-segment silence gaps are inserted, and fade-in is applied
  at boundaries to eliminate clicks.
- **Error resilience** — The orchestrator gracefully skips languages that fail
  during Phase 4 (TTS) rather than aborting the entire run.

---

## Prerequisites

1. **Python 3.11+** with packages from requirements.txt:
   ```
   pip install -r requirements.txt
   ```

2. **ffmpeg** on PATH or installed via `winget install ffmpeg`.
   Common locations are auto-detected (LocalAppData, ProgramFiles).

3. **API keys** in a .env file (copy from .env.example):
   ```
   GOOGLE_API_KEY=your-google-gemini-api-key-here
   DEEPSEEK_API_KEY=your-deepseek-api-key-here
   ```
   Note: Gemini TTS (gemini-3.1-flash-tts-preview) requires a paid API key.
   Free-tier keys will receive HTTP 500. gemini-2.5-flash-preview-tts is a
   working fallback model name.

4. **Disk space**: ~200-500 MB for temp video download. Output MP3s are ~5-20 MB each.

---

## Quick Start (Full Pipeline)

```
python run_pipeline.py --url "https://www.youtube.com/watch?v=VIDEO_ID"
```

This runs all phases sequentially. Expected output:

```
output/
├── master_hu.srt       # Hungarian SRT from video analysis
├── master_de.srt       # German translation
├── master_es.srt       # Spanish translation
├── master_fr.srt       # French translation
├── voiceover_hu.mp3    # Hungarian voiceover
├── voiceover_de.mp3    # German voiceover
├── voiceover_es.mp3    # Spanish voiceover
└── voiceover_fr.mp3    # French voiceover
```

To also generate muxed MP4 videos per language:

```
python run_pipeline.py --url "https://www.youtube.com/watch?v=VIDEO_ID" --with-video
```

This adds `output/video_{hu,de,es,fr}.mp4` files.

---

## Step-by-Step Testing Guide

### Step 0: Verify environment

```
# Check Python
python --version    # Should be 3.11+

# Check .env has both keys
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print('GOOGLE:', bool(os.getenv('GOOGLE_API_KEY'))); print('DEEPSEEK:', bool(os.getenv('DEEPSEEK_API_KEY')))"

# Check all imports (no errors expected)
python -c "import pipeline.config; import pipeline.utils; import pipeline.eyes; import pipeline.brains; import pipeline.voice; import pipeline.assembly; print('All imports OK')"

# Check ffmpeg
python -c "from pipeline.utils import find_ffmpeg; print('ffmpeg:', find_ffmpeg())"
```

### Step 1: Test PoC TTS (validates Gemini API key + ffmpeg)

```
# Generates poc_audio.mp3 with voice "Despina" (English test phrase)
python poc_tts.py

# Expected: poc_audio.mp3 created, ~30-80 KB, plays audio
# If this fails, your GOOGLE_API_KEY is likely free-tier or TTS model unavailable
```

### Step 2: Test Phase 2 — Video analysis (one-shot, ~2-5 min)

```
# Pick any short YouTube video (<5 min recommended for first test)
python -m pipeline.eyes --url "https://www.youtube.com/watch?v=VIDEO_ID" --output output
```

**What to check:**
- output/master_hu.srt exists
- Open it — entries should be numbered with valid HH:MM:SS,mmm timestamps
- Count entries: should be 5-20+ for a typical video
- Read Hungarian text — should describe what's happening

### Step 3: Test Phase 3 — Translation (needs Phase 2 output)

```
# Requires output/master_hu.srt from Step 2
python -m pipeline.brains --input output/master_hu.srt --output-dir output
```

**What to check:**
- output/master_{de,es,fr}.srt exist
- Each has same entry count as master_hu.srt
- Timestamps match the master exactly
- Text is in the target language (not Hungarian)

### Step 4: Test Phase 4 — TTS Voiceover (needs Phase 2+3 output)

```
# Most time-consuming phase — generates all 4 voiceovers
python -m pipeline.voice --input-dir output --output-dir output
```

**What to check:**
- All 4 voiceover_{lang}.mp3 files exist and play audio
- Duration roughly matches last SRT timestamp (+-10%)
- No clicks/pops at segment boundaries

### Step 5: Test Phase 5 — Assembly (needs Phase 4 output)

```
# Audio-only verification (default)
python -m pipeline.assembly --input-dir output --output-dir output

# With video muxing (needs temp/video.mp4)
python -m pipeline.assembly --input-dir output --output-dir output --with-video temp/video.mp4
```

**What to check:**
- Console shows per-language duration comparison
- If --with-video: video_{lang}.mp4 files play with synced audio

### Step 6: End-to-end orchestrator test

```
# Full pipeline (may take 10-30 min total)
python run_pipeline.py --url "https://www.youtube.com/watch?v=VIDEO_ID"

# Skip already-completed phases
python run_pipeline.py --url "..." --skip-phase 2,3

# Generate muxed videos too
python run_pipeline.py --url "..." --with-video
```

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| 500 INTERNAL on TTS | Free-tier API key | Upgrade to paid key, or switch model to gemini-2.5-flash-preview-tts |
| No candidates returned | Content filter blocked response | Simplify/rephrase the prompt text |
| Video processing timed out | Large video or API queue | Wait and retry; video <500 MB recommended |
| FFmpeg conversion failed | ffmpeg not found | winget install ffmpeg or add to PATH |
| DEEPSEEK_API_KEY not set | Missing .env key | Add DEEPSEEK_API_KEY to .env |
| Translation timestamp mismatch | DeepSeek hallucinated | Built-in retry + Gemini fallback handles this |
| Phase 4 skips a language | TTS voice validation failed | Try a different voice in config.VOICE_MAP |
| SRT validation failed | Gemini responded with non-SRT text | Retry with stricter prompt (automatic 2 retries) |

---

## Configuration Reference

Edit pipeline/config.py to change:

- TTS model: GEMINI_TTS_MODEL (default: gemini-3.1-flash-tts-preview)
- Vision model: GEMINI_VISION_MODEL (default: gemini-2.5-flash)
- Voice names: VOICE_MAP dict (language -> primary/fallback voice pair)
- Target languages: TARGET_LANGS list (excludes Hungarian which is source)
- Audio settings: SAMPLE_RATE (24000), MP3_BITRATE (128k)
- Director's Notes: DIRECTOR_NOTES_{HU,DE,ES,FR} — controls TTS speaking style

## Costs (approximate)

| Phase | API | Cost driver | Estimate |
|-------|-----|------------|----------|
| 2 — Gemini Vision | Video upload + analysis prompt | ~$0.02-0.10 per 5-min video |
| 3 — DeepSeek | ~1-2K tokens per language translation | ~$0.002-0.005 per language |
| 4 — Gemini TTS | ~20-40 TTS segments per language | ~$0.05-0.15 per language |
| Total per video | | | ~$0.30-0.80 |
