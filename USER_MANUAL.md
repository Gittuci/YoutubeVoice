# Foltvilag — User Manual

Comprehensive guide for using the multi-language video voiceover pipeline. Covers setup, Web UI, CLI, best practices, troubleshooting, and file structure.

---

## 1. Overview

Foltvilag takes a **mute YouTube instructional video**, generates a **Hungarian narration** with timestamps, translates it to **multiple languages**, produces **timed TTS voiceover WAV segments**, and exports **FCPXML files** for import into **DaVinci Resolve**.

### The 5-Phase Pipeline

| Phase | Name | Input | Output |
|-------|------|-------|--------|
| 1 (PoC) | Verify | API keys + ffmpeg | `poc_audio.mp3` (test) |
| 2 | Video & SRT | YouTube URL | `output/video.mp4`, `output/master_hu.srt` |
| 3 | Translation | `master_hu.srt` | `output/master_{de,es,fr}.srt` |
| 4 | Voiceover | SRT files | `output/wav_segments/{lang}_seg_XXXX.wav` |
| 5 | FCPXML | WAVs + SRTs | `output/fcpxml_{lang}.fcpxml` |

### Two Interfaces

- **Web UI** (`streamlit run webui/app.py`) — Interactive browser-based control with progress bars, previews, and audio playback.
- **CLI** (`python run_pipeline.py`, `python -m pipeline.{eyes,brains,voice,fcpxml}`) — Scriptable, terminal-only pipeline.

---

## 2. Prerequisites & Setup

### 2.1 Python & Dependencies

- **Python 3.11+** required.

```bash
pip install -r requirements.txt
```

### 2.2 ffmpeg

Required for video download, audio time-stretching, and WAV/MP3 processing.

**Windows:**
```bash
winget install ffmpeg
```

Common install locations (`C:\Users\<user>\AppData\Local\ffmpeg\`, `C:\Program Files\ffmpeg\`) are auto-detected. If not found, add ffmpeg to your system PATH.

### 2.3 API Keys

Copy `.env.example` to `.env` and fill in both keys:

```
VERTEX_API_KEY=your-vertex-ai-api-key-here
DEEPSEEK_API_KEY=your-deepseek-api-key-here
```

| Key | Used By | Purpose |
|-----|---------|---------|
| `VERTEX_API_KEY` | Phases 2, 3 (fallback), 4 | Gemini Vision (video analysis), Gemini TTS, Gemini translation fallback |
| `DEEPSEEK_API_KEY` | Phase 3 (primary) | SRT translation (primary provider) |

### 2.4 Vertex AI Project Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project or use an existing one
3. Enable the **Vertex AI API**
4. Generate an API key from **APIs & Services → Credentials**
5. The default project name is `foltvilag-enterprise-audio` (us-central1). Edit `pipeline/config.py` to change `VERTEX_PROJECT` and `VERTEX_LOCATION` if needed.

### 2.5 DaVinci Resolve

The FCPXML output is designed for **DaVinci Resolve** (also compatible with Final Cut Pro). Install DaVinci Resolve (free version works) for final timeline import.

### 2.6 Disk Space

- ~200–500 MB for temporary video downloads
- ~5–50 MB per WAV voiceover segment
- Total output: 50–300 MB per language

### 2.7 Verify Everything Works (Step 0)

Run the proof-of-concept test before any pipeline phase:

```bash
python poc_tts.py
```

**Expected output:** `poc_audio.mp3` (or `poc_audio.wav`) created in the project root, ~30–80 KB, playable audio.  
If this fails, check your `VERTEX_API_KEY` and ffmpeg installation.

You can also verify individual components:

```bash
# Check Python version
python --version    # Should be 3.11+

# Check .env keys
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print('VERTEX:', bool(os.getenv('VERTEX_API_KEY'))); print('DEEPSEEK:', bool(os.getenv('DEEPSEEK_API_KEY')))"

# Check all imports
python -c "import pipeline.config; import pipeline.utils; import pipeline.eyes; import pipeline.brains; import pipeline.voice; import pipeline.fcpxml; print('All imports OK')"

# Check ffmpeg
python -c "from pipeline.utils import find_ffmpeg; print('ffmpeg:', find_ffmpeg())"
```

---

## 3. Intended Workflow

Phases must run in order (2 → 3 → 4 → 5). Each phase depends on files from the previous one.

### Phase 1 (PoC): Verify Everything

```bash
python poc_tts.py
```
Confirms Vertex AI API key, Gemini TTS model, and ffmpeg all work. Run this once after setup.

### Phase 2: Video Download → Analysis → Hungarian SRT

```
YouTube URL → yt-dlp download → Gemini Vision analysis → output/master_hu.srt
```

- Downloads the video to `temp/video.mp4`
- Uploads to Gemini File API
- Analyzes video content and generates Hungarian narration with timestamps
- Writes SRT with entries like `00:00:01,000 --> 00:00:04,000` + Hungarian text

### Phase 3: SRT Translation (DeepSeek → Gemini Fallback)

```
output/master_hu.srt → DeepSeek translation → output/master_{de,es,fr}.srt
```

- Translates Hungarian master SRT to target languages
- **English is the reference/pivot language** — Hungarian → English first, then English → target languages
- Primary translator: DeepSeek API. Fallback: Gemini (Vertex AI) after 3 retries
- Validates entry count (±1 tolerance) and timestamps match the master
- Auto-repairs missing SRT index numbers

### Phase 4: TTS Voiceover Generation (WAV Segments)

```
SRT files → Gemini TTS per segment → time-stretch → output/wav_segments/{lang}_seg_XXXX.wav
```

- Parses SRT entries
- Generates TTS audio for each segment via Gemini TTS (Vertex AI)
- Speeds up audio if it exceeds the SRT window (ffmpeg atempo filter)
- Skips already-generated WAVs (caching based on file modification time vs SRT)
- **Parallel mode** available: concurrent TTS API calls with rate limiting

### Phase 5: FCPXML Export → DaVinci Resolve

```
WAV segments + SRT + video → ffprobe → FCPXML → DaVinci Resolve import
```

- Probes video for dimensions, frame rate, duration
- Creates self-contained FCPXML with video on Track 1 (muted) and WAV voiceover clips at exact timestamps
- Compatible with DaVinci Resolve (FCPXML 1.12 format)

### Data Flow Diagram

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
output/wav_segments/{lang}_seg_0000.wav, {lang}_seg_0001.wav, ...
    |
    v  [Phase 5: fcpxml.py]
Parse SRT + read WAVs + probe video → FCPXML with voiceover clips at exact SRT timestamps
    |
    v
output/video.mp4 + fcpxml_hu.fcpxml, fcpxml_de.fcpxml, ...
    → Import into DaVinci Resolve (self-contained project)
```

---

## 4. Web UI Guide

Launch the web interface:

```bash
pip install -r requirements-ui.txt
streamlit run webui/app.py
```

Opens at `http://localhost:8501`. The UI has a **sidebar** (status, language selector, progress) and **4 phase pages** (Video, Subtitles, Voiceover, FCPXML).

### 4.1 Dashboard (`app.py`)

The landing page shows an overview of the pipeline.

**Sidebar:**
- **API Status:** Colored dots showing Vertex AI, DeepSeek, and ffmpeg availability
  - 🟢 Green = key/executable found and working
  - 🔴 Red = missing or broken
- **Project Files:** Counts of SRT files, WAV segments, and FCPXML files in `output/`
- **Target Languages:** Multi-select for which languages to generate (default: de, es, fr)
- **Phase Progress:** Checkmarks (✅/⬜) for Phases 2–5 based on session state
- **Running Indicator:** ⏳ Running: `<phase>` shown during active operations

**Main Area:**
- **YouTube URL input** — enter a video URL here; shared across all pages
- **Reset Session button** — clears all session state (video, SRTs, TTS, FCPXML) and reloads
- **Output Files table** — lists all files in `output/` with size and type

### 4.2 Video Page (`pages/1_Video.py`)

Executes Phase 2: download and analyze a YouTube video.

**Buttons:**
1. **Download Video** — downloads from YouTube using yt-dlp
   - **Guard:** Requires YouTube URL to be entered, disabled otherwise
   - Shows a `st.status()` container with download progress
2. **Analyze Video** — runs Gemini Vision analysis to generate Hungarian SRT
   - **Guard:** Requires video to be downloaded first, disabled otherwise
   - Shows analysis progress and validates SRT output

**Displays:**
- **Video Info** — resolution, frame rate, duration (from ffprobe)
- **SRT Preview** — expandable table of SRT entries with index, timestamps, and Hungarian text

**Post-completion:** Both buttons become disabled with ✅ success indicators.

### 4.3 Subtitles Page (`pages/2_Subtitles.py`)

Executes Phase 3: translate the Hungarian master SRT.

**Displays:**
- **Master SRT info** — file path and entry count
- **Preview** — expandable master SRT table

**Controls:**
- **Target languages multi-select** — choose which languages to translate to (excludes Hungarian)
- **Translate Selected Languages button** — runs translation in sequence
  - **Guard:** Requires at least one language selected
  - Translates English (reference) first, then selected target languages
  - Shows progress bar across all languages

**Existing Translations:**
- Expandable cards for each translated SRT (`master_{lang}.srt`)
- Preview table with entries
- **Delete button** per language — removes the SRT file and clears session state

### 4.4 Voiceover Page (`pages/3_Voiceover.py`)

Executes Phase 4: generate TTS voiceover WAV segments.

**Language Selector:**
- Only shows languages that have SRT files in `output/`

**Segment Preview:**
- Table of all segments for the selected language
- WAV Status column: ✅ (exists) or ⬜ (missing), with WAV duration when available

**Status Bar:**
- "m of n WAVs cached (X%)" progress bar showing pre-existing WAV segments

**Generation Settings:**

| Setting | Default | Range | Description |
|---------|---------|-------|-------------|
| Parallel generation | ✅ On | — | Toggle between parallel and sequential mode |
| Max workers | 3 | 1–5 | Concurrent TTS API calls (parallel mode only) |
| RPM limit | 10 | 1–60 | Maximum requests per minute (parallel mode only) |

**Generate Voiceover button:**
- **Guard:** Disabled if already complete for the selected language
- **Parallel mode:** Shows real-time progress bar updated every 1.5s via background thread polling. The `st.status()` container and progress bar stay visible throughout.
- **Sequential mode:** Shows results only after all segments complete (captures all output at once via `run_with_logs`).

**Generated WAV Segments:**
- Lists first 20 WAV files with duration
- Each has a playable audio player (for files < 10 MB)

**Per-Language Dashboard:**
- Grid of all languages with ✅ Done / ⬜ Pending status

### 4.5 FCPXML Page (`pages/4_FCPXML.py`)

Executes Phase 5: export FCPXML for DaVinci Resolve.

**Language Selector:**
- Only shows languages with completed TTS voiceovers

**Generate FCPXML button:**
- **Guard:** Disabled if FCPXML already generated for that language
- Copies video to `output/` for a self-contained project
- Builds FCPXML with video on Track 1 (muted) and WAV clips at exact timestamps

**Download Button:**
- Appears after generation — downloads the `.fcpxml` file

**Timeline Visualization:**
- Colored horizontal bars showing segment placement on the timeline
- Hover tooltips show segment text
- Shows first 100 segments

**Import Instructions:**
1. Open DaVinci Resolve
2. File → Import → Timeline (select `.fcpxml`)
3. Video appears on Track 1 (muted), WAV voiceover clips at correct timestamps
4. Adjust audio levels and export as needed

**Generated Files:**
- Expandable listing of all generated FCPXML files with XML preview (first 2000 chars)

---

## 5. CLI Guide

### 5.1 Full Pipeline (Orchestrator)

```bash
python run_pipeline.py --url "https://www.youtube.com/watch?v=VIDEO_ID"
```

Runs phases 2→5 in sequence. Output lands in `output/`.

**Flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `--url` | *(required)* | YouTube video URL |
| `--output` | `output` | Output directory |
| `--langs` | `de,es,fr` | Comma-separated target language codes |
| `--reference-lang` | `en` | Reference/pivot language for translations |
| `--skip-phase` | *(none)* | Comma-separated phases to skip (e.g. `2,3`) |
| `--verbose` | off | Verbose output |

**Examples:**
```bash
# Specific target languages, skip already-completed phases
python run_pipeline.py --url "..." --langs de,fr --skip-phase 2,3

# Different reference language
python run_pipeline.py --url "..." --reference-lang fr
```

### 5.2 Individual Phases

**Phase 2 — Video & SRT:**
```bash
python -m pipeline.eyes --url "https://www.youtube.com/watch?v=VIDEO_ID" --output output
```
Downloads video to `temp/video.mp4`, analyzes with Gemini Vision, writes `output/master_hu.srt`.

**Phase 3 — Translation:**
```bash
python -m pipeline.brains --input output/master_hu.srt --output-dir output
```
Translates Hungarian SRT to all target languages. Uses DeepSeek (primary) with Gemini fallback.

**Phase 4 — Voiceover:**
```bash
# Sequential (default)
python -m pipeline.voice --input-dir output --output-dir output

# Parallel mode
python -m pipeline.voice --input-dir output --output-dir output --parallel --workers 3 --rpm 10

# Specific languages only
python -m pipeline.voice --input-dir output --output-dir output --langs hu,de
```

Flags for `pipeline.voice`:

| Flag | Default | Description |
|------|---------|-------------|
| `--input-dir` | `output` | Directory containing `master_*.srt` files |
| `--output-dir` | `output` | Output directory for WAV segments |
| `--langs` | `hu,de,es,fr` | Comma-separated language codes |
| `--parallel` | off | Enable parallel TTS generation |
| `--workers` | 3 | Max concurrent TTS API calls (parallel only) |
| `--rpm` | 10 | Requests per minute limit (parallel only) |

**Phase 5 — FCPXML:**
```bash
python -m pipeline.fcpxml --lang de \
    --srt output/master_de.srt \
    --wav-dir output/wav_segments \
    --video output/video.mp4 \
    --output output/fcpxml_de.fcpxml
```

### 5.3 PoC Test

```bash
python poc_tts.py
```
Validates Vertex AI API key, Gemini TTS model, and ffmpeg by generating a test audio file.

---

## 6. DOs and DON'Ts

### DO:

1. **Run `python poc_tts.py` first** — Validates API keys and ffmpeg before any pipeline phase runs. This is your "step zero" health check.

2. **Check the sidebar API status dots** — In the Web UI, ensure Vertex AI, DeepSeek, and ffmpeg all show 🟢 green before running phases. A 🔴 red dot means a missing key or broken installation.

3. **Complete phases in order (2 → 3 → 4 → 5)** — Each phase depends on files from the previous one. Skipping Phase 2 means no video and no master SRT for any other phase.

4. **Wait for each operation to fully complete** — Buttons disable during active operations and re-enable only after completion. The "⏳ Running" indicator in the sidebar confirms something is in progress.

5. **Use the "Reset Session" button if something gets stuck** — Resets all 12 session state keys to their defaults, clears progress indicators, and reloads the page. Does not delete output files.

6. **Use parallel TTS mode for many segments** — With 20+ segments, parallel mode (3 workers at 10 RPM) is significantly faster than sequential mode. The progress bar updates in real-time every 1.5 seconds.

7. **Keep the terminal window open** — Closing the terminal kills the Streamlit server and any running background threads (parallel TTS). If you close it mid-generation, the operation is lost.

8. **Save FCPXML files immediately** — Use the **Download button** on the FCPXML page to save the generated `.fcpxml` file. The file in `output/` is safe, but downloading gives you a local backup.

### DON'T:

1. **DON'T refresh the browser page during an active operation** — The pipeline *continues running* in the background (the `is_running` guard prevents restarting), but you **LOSE** the visual progress bar, status indicators, and log output. The background thread keeps working, but you're blind to its progress. If you accidentally refresh, wait for the operation to finish (you'll know when buttons re-enable on the next page load).

2. **DON'T open two browser tabs** — Streamlit creates **separate sessions per tab**. Tab 1's `is_running=True` does NOT propagate to Tab 2. Clicking buttons in Tab 2 during an active operation in Tab 1 can start **duplicate TTS calls or API requests** competing for the same output files.

3. **DON'T close the terminal** — Kills the Streamlit server and all background threads. Any in-progress parallel TTS generation is immediately terminated.

4. **DON'T delete output files manually mid-pipeline** — Subsequent phases depend on files from previous phases:
   - Deleting `output/master_hu.srt` breaks Phase 3 (no source to translate)
   - Deleting `output/master_{lang}.srt` breaks Phase 4 (no timestamps for TTS)
   - Deleting WAV segments breaks Phase 5 (no audio clips for FCPXML)

5. **DON'T run CLI and Web UI simultaneously** — Both write to the same `output/` directory. Concurrent operations from two interfaces cause **file conflicts and potentially corrupted results**.

6. **DON'T skip Phase 2** — The video file and master Hungarian SRT are required by every other phase. Without Phase 2, the pipeline cannot proceed.

7. **DON'T ignore rate limit errors** — If you see `RESOURCE_EXHAUSTED` or `429` errors:
   - Wait a few minutes before retrying
   - In parallel mode, lower `max_workers` (e.g., from 3 to 1) and reduce `rpm_limit` (e.g., from 10 to 5)
   - The built-in retry mechanism waits 30s × attempt number before retrying

---

## 7. Session State Reference

The Web UI tracks pipeline progress via 12 session state keys in `st.session_state`. These keys persist across page navigation but reset on browser close (or "Reset Session").

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `video_path` | `str` / `None` | `None` | Path to downloaded video (Phase 2 output) |
| `video_copy_path` | `str` / `None` | `None` | Path to video copy in `output/` (FCPXML uses this) |
| `srt_path` | `str` / `None` | `None` | Path to master Hungarian SRT (Phase 2 output) |
| `translated_langs` | `set` | `set()` | Language codes with completed translations (Phase 3) |
| `tts_complete` | `dict` | `{}` | `{lang: True}` for languages with completed voiceovers (Phase 4) |
| `fcpxml_generated` | `dict` | `{}` | `{lang: True}` for languages with generated FCPXML (Phase 5) |
| `is_running` | `bool` | `False` | Guard flag — prevents starting a new operation while one is active |
| `current_run` | `str` / `None` | `None` | Label shown in sidebar (e.g., "Phase 4: TTS — de") |
| `log_captured` | `list` | `[]` | Captured pipeline log output |
| `ffmpeg_path` | `str` / `None` | auto | Path to ffmpeg executable (auto-detected on session init) |
| `selected_langs` | `set` | `{"de","es","fr"}` | User's target language selections |
| `youtube_url` | `str` | `""` | Shared YouTube URL across all pages |

### How `is_running` Works

Every page checks `st.session_state.is_running` at the top. If `True`:

1. A warning banner shows: "A process is already running: `<current_run>`"
2. `st.stop()` halts page rendering — **all buttons, inputs, and progress bars are frozen**
3. When the operation completes, `is_running` is set to `False` and the page re-renders with buttons enabled

This prevents duplicate API calls but means you can't interact with the UI during an operation, even to navigate between pages.

### Why Buttons Disable After Completion

After each phase succeeds, the corresponding button is permanently disabled for that language:
- **Video page:** Download and Analyze buttons show ✅ and become disabled
- **Subtitles page:** Translated languages are tracked in `translated_langs` — the Translate button is still available (it skips already-translated languages)
- **Voiceover page:** Generate button disables for languages in `tts_complete`
- **FCPXML page:** Generate button disables for languages in `fcpxml_generated`

To re-run a phase, use **Reset Session** to clear all progress state.

### What "Reset Session" Does

1. Re-initializes all 12 state keys to their defaults
2. Re-detects ffmpeg path
3. Calls `st.rerun()` to reload the page

**Does NOT** delete any output files (`output/` remains intact). This means you can reset, re-enter the same YouTube URL, and re-run phases — existing output files will be reused where possible (WAV caching, SRT validation).

---

## 8. Troubleshooting

### General Issues

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| 500 INTERNAL on TTS | Vertex AI quota or model unavailable | Check quota in Google Cloud Console; verify model name |
| No candidates returned | Content filter blocked response | Simplify/rephrase the prompt text |
| Video processing timed out | Large video or API queue | Wait and retry; video <500 MB recommended |
| FFmpeg conversion failed | ffmpeg not found | `winget install ffmpeg` or add to PATH |
| DEEPSEEK_API_KEY not set | Missing .env key | Add DEEPSEEK_API_KEY to .env |
| VERTEX_API_KEY not set | Missing .env key | Add VERTEX_API_KEY to .env |
| Translation timestamp mismatch | DeepSeek hallucinated | Built-in retry + Gemini fallback handles this |
| Phase 4 skips a language | TTS voice validation failed | Try a different voice in `pipeline/config.py` → `VOICE_MAP` |
| SRT validation failed | Gemini responded with non-SRT text | Retry with stricter prompt (automatic 2 retries) |
| FCPXML import fails in Resolve | WAV files moved or renamed | Use absolute paths; keep `wav_segments/` directory intact |
| ffprobe not found | Missing ffprobe executable | Install ffmpeg fully (`winget install ffmpeg`) |

### Web-UI-Specific Issues

**"A process is already running" message:**
- An operation is still in progress. Wait for it to complete. The `is_running` guard prevents starting new operations.
- If the page was refreshed during an operation, the background thread may still be running — wait 1–2 minutes and the guard should release naturally.
- If stuck indefinitely, click **Reset Session** to force-clear the flag.

**API key red dot in sidebar:**
- 🔴 **Vertex AI:** `VERTEX_API_KEY` is missing or empty in `.env`. Copy `.env.example` to `.env` and add your key.
- 🔴 **DeepSeek:** `DEEPSEEK_API_KEY` is missing or empty — same fix.
- 🔴 **ffmpeg:** ffmpeg not found on PATH or in common locations. `winget install ffmpeg` or add to PATH.

**WAV generation stuck / no progress:**
- In **parallel mode:** Check the terminal for rate limit errors (429 / RESOURCE_EXHAUSTED). Reduce `max_workers` and `rpm_limit`.
- In **sequential mode:** Large segments may take 30–60 seconds each. Be patient — check the terminal for per-segment progress logs.
- Verify the Vertex AI client is working by re-running `python poc_tts.py`.

**Translation validation failures:**
- DeepSeek may return translated text with altered timestamps. The built-in validation retries up to 3 times, then falls back to Gemini.
- If all retries fail, the language is skipped with an error message. You can re-run translation for that language individually.

**Progress bar disappeared after refresh:**
- You refreshed during an active parallel TTS operation. The background thread is still running but the UI lost its reference to the progress container. The operation will complete naturally — wait and check `output/wav_segments/` for new WAV files.

**Duplicate operations from two tabs:**
- If you opened a second tab and clicked a button during an active operation, two operations may be competing. Close one tab immediately. Check `output/` for corrupted or duplicate files. If files appear corrupted, delete them and re-run from the last known-good phase.

---

## 9. File Structure Reference

### Output Directory (`output/`)

All pipeline output lands here. A complete run produces:

```
output/
├── video.mp4                  # Downloaded video (copied for self-contained project)
├── master_hu.srt              # Hungarian SRT from video analysis (Phase 2)
├── master_en.srt              # English reference translation (Phase 3)
├── master_de.srt              # German translation (Phase 3)
├── master_es.srt              # Spanish translation (Phase 3)
├── master_fr.srt              # French translation (Phase 3)
├── wav_segments/
│   ├── hu_seg_0000.wav        # Hungarian voiceover segment 0
│   ├── hu_seg_0001.wav        # Hungarian voiceover segment 1
│   ├── de_seg_0000.wav        # German voiceover segment 0
│   ├── es_seg_0000.wav        # Spanish voiceover segment 0
│   └── fr_seg_0000.wav        # French voiceover segment 0
├── fcpxml_hu.fcpxml           # Hungarian FCPXML project file
├── fcpxml_de.fcpxml           # German FCPXML project file
├── fcpxml_es.fcpxml           # Spanish FCPXML project file
└── fcpxml_fr.fcpxml           # French FCPXML project file
```

### File Types

| Extension | Format | Contents | Created By |
|-----------|--------|----------|------------|
| `.srt` | SubRip Subtitle | Timestamped text entries (numbered, HH:MM:SS,mmm format) | Phase 2, 3 |
| `.wav` | WAV Audio (24 kHz, 16-bit, mono) | TTS-generated voiceover audio for one segment | Phase 4 |
| `.fcpxml` | FCPXML 1.12 (XML) | DaVinci Resolve project with video + placed audio clips | Phase 5 |

### WAV Naming Convention

WAV files use zero-based indexing: `{lang}_seg_{index:04d}.wav`

| Example | Meaning |
|---------|---------|
| `hu_seg_0000.wav` | Hungarian, first segment (index 0, SRT entry #1) |
| `de_seg_0005.wav` | German, sixth segment (index 5, SRT entry #6) |
| `fr_seg_0012.wav` | French, thirteenth segment (index 12, SRT entry #13) |

### Caching Behavior

WAV segments are cached — if a WAV file exists and is newer than its source SRT file, it is skipped during regeneration. Deleting an SRT file invalidates all WAVs for that language (they will be regenerated). Deleting individual WAV files causes only those specific segments to regenerate.

---

## 10. Costs

All costs are approximate and depend on video length, segment count, and API pricing.

| Phase | API | Cost Driver | Estimate |
|-------|-----|------------|----------|
| 2 — Gemini Vision | Video upload + analysis prompt | ~$0.02–0.10 per 5-min video | Vertex AI |
| 3 — DeepSeek | ~1–2K tokens per language translation | ~$0.002–0.005 per language | DeepSeek API |
| 4 — Gemini TTS (Vertex AI) | ~20–40 TTS segments per language | ~$0.05–0.15 per language | Vertex AI |
| **Total per video** | | | **~$0.30–0.80** |

### Parallel Mode Cost Note

Parallel TTS mode generates more requests per minute (e.g., 3 concurrent workers at 10 RPM), but the **total number of segments is the same** as sequential mode. Total cost is **identical** — parallel mode only affects speed, not the number of API calls.

Rate limiting (`rpm_limit`) may slow down parallel generation, but this only affects wall-clock time, not cost.

---

## Configuration Reference

Edit `pipeline/config.py` to change pipeline settings:

| Setting | Default | Description |
|---------|---------|-------------|
| `VERTEX_PROJECT` | `foltvilag-enterprise-audio` | Google Cloud project name |
| `VERTEX_LOCATION` | `us-central1` | Vertex AI region |
| `GEMINI_TTS_MODEL` | `gemini-3.1-flash-tts-preview` | TTS model for voiceover |
| `GEMINI_VISION_MODEL` | `gemini-2.5-flash` | Vision model for video analysis |
| `DEEPSEEK_MODEL` | `deepseek-chat` | DeepSeek translation model |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | DeepSeek API endpoint |
| `VOICE_MAP` | See below | Per-language voice name priority pairs |
| `TARGET_LANGS` | `["de","es","fr"]` | Default target languages |
| `SOURCE_LANG` | `"hu"` | Source language (Hungarian) |
| `REFERENCE_LANG` | `"en"` | Pivot language for translation |
| `SAMPLE_RATE` | `24000` | TTS output sample rate (Hz) |
| `CHANNELS` | `1` | TTS output channels (mono) |
| `OUTPUT_DIR` | `"output"` | Output directory |
| `WAV_SEGMENTS_DIR` | `"wav_segments"` | Subdirectory for WAV segments |

### Voice Map

| Language | Primary Voice | Fallback Voice |
|----------|--------------|----------------|
| `hu` (Hungarian) | Despina | Aoede |
| `en` (English) | Aoede | Despina |
| `de` (German) | Kore | Gacrux |
| `es` (Spanish) | Laomedeia | Sulafat |
| `fr` (French) | Vindemiatrix | Callirrhoe |

Voices are validated before generation — if the primary voice fails, the fallback is tried, then a universal fallback chain (Despina → Aoede → Kore → Charon).
