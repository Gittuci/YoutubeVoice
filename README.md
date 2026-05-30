# Foltvilag — Multi-Language Video Voiceover Pipeline

Automatically generates multi-language voiceovers for mute YouTube instructional videos.
Takes a YouTube URL, produces time-aligned Hungarian narration, translates it to
German/Spanish/French, generates time-stretched WAV voiceover segments with Gemini TTS
(via Vertex AI), and exports FCPXML for DaVinci Resolve import.

---

## Blueprint (Architecture)

### File Inventory

```
├── .env.example           # Template for API keys (commit-safe)
├── .gitignore             # Excludes .env, output/, temp/, media files
├── requirements.txt       # google-genai, openai, yt-dlp, python-dotenv
├── poc_tts.py             # Phase 1 proof-of-concept (standalone TTS test, Vertex AI)
├── run_pipeline.py        # Orchestrator: runs phases 2→5
└── pipeline/
    ├── __init__.py         # Package marker
    ├── config.py           # Centralized settings, .env loader, voice map, model names
    ├── utils.py            # Shared: find_ffmpeg, PCM/WAV, parse_srt, build_srt, strip_markdown_fences
    ├── eyes.py             # Phase 2: YouTube download → Gemini vision → Hungarian SRT
    ├── brains.py           # Phase 3: SRT translation (DeepSeek + Gemini fallback)
    ├── voice.py            # Phase 4: SRT → TTS → time-stretched WAV segments
    └── fcpxml.py           # Phase 5: FCPXML generator for DaVinci Resolve
```

### Phase Modules

| Phase | Module | Input | Output | API Used |
|-------|--------|-------|--------|----------|
| 2 | pipeline/eyes.py | YouTube URL | output/master_hu.srt | Gemini 2.5 Flash (vision, Vertex AI) |
| 3 | pipeline/brains.py | master_hu.srt | master_{de,es,fr}.srt | DeepSeek (primary) / Gemini (fallback, Vertex AI) |
| 4 | pipeline/voice.py | master_{hu,de,es,fr}.srt | output/wav_segments/{lang}_seg_XXXX.wav | Gemini 3.1 Flash TTS (Vertex AI) |
| 5 | pipeline/fcpxml.py | WAV segments + SRTs + video | output/fcpxml_{lang}.fcpxml | ffprobe (local) |

### Data Flow

```
YouTube URL
    |
    v  [Phase 2: eyes.py]
yt-dlp download → Gemini File API upload → video analysis (Vertex AI)
    |
    v
output/master_hu.srt  (Hungarian narration, timestamped)
    |
    v  [Phase 3: brains.py]
DeepSeek API → translate → validate timestamps → fallback to Gemini (Vertex AI)
    |
    v
output/master_de.srt, master_es.srt, master_fr.srt
    |
    v  [Phase 4: voice.py]
Parse SRT → voice validation → Gemini TTS per segment → time-stretch → save as WAV
    |
    v
output/wav_segments/{lang}_seg_0001.wav, {lang}_seg_0002.wav, ...
    |
    v  [Phase 5: fcpxml.py]
Parse SRT + read WAVs + probe video → FCPXML with gapped audio on timeline
    |
    v
output/fcpxml_de.fcpxml, fcpxml_es.fcpxml, fcpxml_fr.fcpxml, fcpxml_hu.fcpxml
    → Import into DaVinci Resolve
```

### Key Design Decisions

- **Vertex AI routing** — All Gemini clients use `vertexai=True` with `VERTEX_API_KEY`,
  project `foltvilag-enterprise-audio`, and location `us-central1`.
- **TTS model** — `gemini-3.1-flash-tts-preview` generates raw L16 PCM audio.
  Individual segments are saved as WAV files using the `wave` module.
- **Time-stretching** — Segments longer than their SRT window are sped up via ffmpeg
  atempo filter (0.5-2.0 range). Beyond 2.0×, truncation is used as a fallback.
- **Voice validation** — Before generating per-language voiceovers, a lightweight API
  call confirms the voice name is valid. Falls back through a priority chain.
- **Translation validation** — Entry count and timestamps are compared byte-for-byte
  against the master SRT. DeepSeek is the primary translator; Gemini (Vertex AI) is
  the fallback after 3 failed retries.
- **FCPXML output** — Video is placed on Track 1 (muted via `adjust-volume amount="-inf"`),
  time-stretched WAV chunks are placed on the same track at exact SRT timestamps using
  `<gap>` elements. Compatible with DaVinci Resolve.
- **Error resilience** — The orchestrator gracefully skips languages that fail during
  Phase 4 (TTS) rather than aborting the entire run.

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
   VERTEX_API_KEY=your-vertex-ai-api-key-here
   DEEPSEEK_API_KEY=your-deepseek-api-key-here
   ```
   Note: Vertex AI requires a Google Cloud project with the Vertex AI API enabled.
   The default project is `foltvilag-enterprise-audio` (us-central1).

4. **DaVinci Resolve** — The FCPXML output is designed for DaVinci Resolve import.
   Final Cut Pro also supports the FCPXML 1.12 format.

5. **Disk space** — ~200-500 MB for temp video download. Output WAVs are ~5-50 MB each.

---

## Quick Start (Full Pipeline)

```
python run_pipeline.py --url "https://www.youtube.com/watch?v=VIDEO_ID"
```

This runs all phases sequentially. Expected output:

```
output/
├── master_hu.srt              # Hungarian SRT from video analysis
├── master_de.srt              # German translation
├── master_es.srt              # Spanish translation
├── master_fr.srt              # French translation
├── wav_segments/
│   ├── hu_seg_0000.wav        # Hungarian voiceover segment 0
│   ├── hu_seg_0001.wav        # Hungarian voiceover segment 1
│   ├── ...
│   ├── de_seg_0000.wav        # German voiceover segment 0
│   ├── ...
│   ├── es_seg_0000.wav        # Spanish voiceover segment 0
│   └── fr_seg_0000.wav        # French voiceover segment 0
├── fcpxml_hu.fcpxml           # Hungarian FCPXML for DaVinci Resolve
├── fcpxml_de.fcpxml           # German FCPXML
├── fcpxml_es.fcpxml           # Spanish FCPXML
└── fcpxml_fr.fcpxml           # French FCPXML
```

To skip already-completed phases:

```
python run_pipeline.py --url "..." --skip-phase 2,3
```

---

## Step-by-Step Testing Guide

### Step 0: Verify environment

```
# Check Python
python --version    # Should be 3.11+

# Check .env has both keys
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print('VERTEX:', bool(os.getenv('VERTEX_API_KEY'))); print('DEEPSEEK:', bool(os.getenv('DEEPSEEK_API_KEY')))"

# Check all imports (no errors expected)
python -c "import pipeline.config; import pipeline.utils; import pipeline.eyes; import pipeline.brains; import pipeline.voice; import pipeline.fcpxml; print('All imports OK')"

# Check ffmpeg
python -c "from pipeline.utils import find_ffmpeg; print('ffmpeg:', find_ffmpeg())"
```

### Step 1: Test PoC TTS (validates Vertex AI API key + ffmpeg)

```
# Generates poc_audio.mp3 with voice "Despina" (English test phrase)
python poc_tts.py

# Expected: poc_audio.mp3 created, ~30-80 KB, plays audio
# If this fails, check your VERTEX_API_KEY and Vertex AI project setup
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
# Most time-consuming phase — generates WAV segments for all languages
python -m pipeline.voice --input-dir output --output-dir output
```

**What to check:**
- output/wav_segments/ contains {language}_seg_XXXX.wav files
- Each file plays audio
- Duration approximately fits SRT window

### Step 5: Test Phase 5 — FCPXML Generation (needs Phase 4 output)

```
# Generate FCPXML for one language
python -m pipeline.fcpxml --lang de --srt output/master_de.srt --wav-dir output/wav_segments --video temp/video.mp4 --output output/fcpxml_de.fcpxml
```

**What to check:**
- output/fcpxml_de.fcpxml is valid XML
- Import into DaVinci Resolve: video is muted, WAV chunks are placed at correct timestamps

### Step 6: End-to-end orchestrator test

```
# Full pipeline (may take 10-30 min total)
python run_pipeline.py --url "https://www.youtube.com/watch?v=VIDEO_ID"

# Skip already-completed phases
python run_pipeline.py --url "..." --skip-phase 2,3
```

---

## Configuration Reference

Edit pipeline/config.py to change:

- **Vertex AI**: VERTEX_PROJECT (default: `foltvilag-enterprise-audio`), VERTEX_LOCATION (default: `us-central1`)
- **TTS model**: GEMINI_TTS_MODEL (default: `gemini-3.1-flash-tts-preview`)
- **Vision model**: GEMINI_VISION_MODEL (default: `gemini-2.5-flash`)
- **DeepSeek**: DEEPSEEK_MODEL (default: `deepseek-chat`), DEEPSEEK_BASE_URL (default: `https://api.deepseek.com`)
- **Voice names**: VOICE_MAP dict (language → primary/fallback voice pair)
- **Target languages**: TARGET_LANGS list (excludes Hungarian which is source)
- **Audio settings**: SAMPLE_RATE (24000), CHANNELS (1)
- **Output**: OUTPUT_DIR (default: `output`), WAV_SEGMENTS_DIR (default: `wav_segments`)
- **Director's Notes**: DIRECTOR_NOTES_{HU,DE,ES,FR} — controls TTS speaking style

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| 500 INTERNAL on TTS | Vertex AI quota or model unavailable | Check quota in Google Cloud Console; verify model name |
| No candidates returned | Content filter blocked response | Simplify/rephrase the prompt text |
| Video processing timed out | Large video or API queue | Wait and retry; video <500 MB recommended |
| FFmpeg conversion failed | ffmpeg not found | `winget install ffmpeg` or add to PATH |
| DEEPSEEK_API_KEY not set | Missing .env key | Add DEEPSEEK_API_KEY to .env |
| VERTEX_API_KEY not set | Missing .env key | Add VERTEX_API_KEY to .env |
| Translation timestamp mismatch | DeepSeek hallucinated | Built-in retry + Gemini fallback handles this |
| Phase 4 skips a language | TTS voice validation failed | Try a different voice in config.VOICE_MAP |
| SRT validation failed | Gemini responded with non-SRT text | Retry with stricter prompt (automatic 2 retries) |
| FCPXML import fails in Resolve | WAV files moved or renamed | Use absolute paths; keep wav_segments/ directory intact |
| ffprobe not found | Missing ffprobe executable | Install ffmpeg fully (`winget install ffmpeg`) |

---

## Costs (approximate)

| Phase | API | Cost driver | Estimate |
|-------|-----|------------|----------|
| 2 — Gemini Vision | Video upload + analysis prompt | ~$0.02-0.10 per 5-min video |
| 3 — DeepSeek | ~1-2K tokens per language translation | ~$0.002-0.005 per language |
| 4 — Gemini TTS (Vertex AI) | ~20-40 TTS segments per language | ~$0.05-0.15 per language |
| Total per video | | | ~$0.30-0.80 |
