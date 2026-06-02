# Foltvilag — Multi-Language Video Voiceover Pipeline

Automatically generates multi-language voiceovers for mute YouTube instructional videos.
Takes a YouTube URL, produces time-aligned Hungarian narration, translates it to
German/Spanish/French, generates time-stretched WAV voiceover segments with Gemini TTS
(via Vertex AI), and exports FCPXML for DaVinci Resolve import.

> **📖 User manual:** See [USER_MANUAL.md](USER_MANUAL.md) for the complete guide — setup instructions,
> Web UI guide (every page/button/indicator), CLI reference, DOs & DON'Ts, troubleshooting,
> file structure, and costs.

---

## Blueprint (Architecture)

### File Inventory

```
├── .env.example           # Template for API keys (commit-safe)
├── .gitignore             # Excludes .env, output/, temp/, media files
├── requirements.txt       # google-genai, openai, yt-dlp, python-dotenv
├── poc_tts.py             # Phase 1 proof-of-concept (standalone TTS test, Vertex AI)
├── run_pipeline.py        # Orchestrator: runs phases 2→5
├── prompts/               # Prompt templates (TTS, translation, expression tags, etc.)
│   ├── video_analysis.txt
│   ├── tts_generation.txt
│   ├── translate_system.txt
│   ├── translate_gemini.txt
│   ├── expression_tags.txt
│   └── director_notes_{hu,en,de,es,fr}.txt
└── pipeline/
    ├── __init__.py         # Package marker
    ├── config.py           # Centralized settings, .env loader, voice map, model names
    ├── utils.py            # Shared: find_ffmpeg, PCM/WAV, parse_srt, insert_srt_indices, etc.
    ├── eyes.py             # Phase 2: YouTube download → Gemini vision → Hungarian SRT
    ├── brains.py           # Phase 3: SRT translation (DeepSeek + Gemini fallback)
    ├── voice.py            # Phase 4: SRT → TTS → speed-adjusted WAV segments
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
Parse SRT + read WAVs + probe video → FCPXML with voiceover clips at exact SRT timestamps
    |
    v
output/video.mp4 + fcpxml_hu.fcpxml, fcpxml_de.fcpxml, ...
    → Import into DaVinci Resolve (self-contained project)
```

### Key Design Decisions

- **Vertex AI routing** — All Gemini clients use `vertexai=True` with `VERTEX_API_KEY`,
  project `foltvilag-enterprise-audio`, and location `us-central1`.
- **TTS model** — `gemini-3.1-flash-tts-preview` generates raw L16 PCM audio.
  Individual segments are saved as WAV files using the `wave` module.
- **Speed adjustment** — Segments longer than their SRT window are sped up via ffmpeg
  `atempo` filter (chained for speeds > 2.0×). Segments shorter than their window
  are left at natural speed — no artificial slow-down stretching.
- **TTS prompts** — Director notes (per-language speaking style), TTS generation
  templates, and expression tags are loaded from external prompt files in `prompts/`.
- **Voice validation** — Before generating per-language voiceovers, a lightweight API
  call confirms the voice name is valid. Falls back through a priority chain.
- **Translation validation** — Entry count (±1 tolerance) and timestamps are compared
  against the master SRT. Missing SRT index numbers are auto-repaired via
  `insert_srt_indices()`. DeepSeek is the primary translator; Gemini (Vertex AI) is
  the fallback after 3 failed retries.
- **FCPXML output** — Original video is placed on Track 1 (muted) and copied into the
  `output/` directory for a self-contained project. WAV voiceover clips are placed at
  exact SRT start timestamps with no cumulative drift. Fade-in filter applied to each
  clip. Compatible with DaVinci Resolve.
- **WAV caching** — Existing WAV segments skip regeneration if newer than their SRT
  file. Cached segments read actual WAV duration rather than assuming the SRT window
  length.
- **Error resilience** — The orchestrator gracefully skips languages that fail during
  Phase 4 (TTS) rather than aborting the entire run.

---

## Quick Start

```
# Step 0 — Verify everything works
python poc_tts.py

# Full pipeline
python run_pipeline.py --url "https://www.youtube.com/watch?v=VIDEO_ID"

# Web UI
pip install -r requirements-ui.txt
streamlit run webui/app.py
```

See [USER_MANUAL.md](USER_MANUAL.md) for detailed step-by-step testing, Web UI guide, CLI
flags, troubleshooting, and best practices.

---
