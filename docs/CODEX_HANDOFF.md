# Codex Handoff

This is the current investigation and session handoff. Read [agent instructions](../AGENTS.md), the [engineering backlog](../TODO.md), the [architecture](ARCHITECTURE.md), and the [decision record](DECISIONS.md) for durable guidance. `.kilo/plans/` is historical material.

## Project purpose

YoutubeVoice is a Python pipeline for producing multilingual instructional voiceovers for patchwork, English Paper Piecing (EPP), Foundation Paper Piecing (FPP), sewing, sashiko, and textile-art videos. It must support both mute demonstrations and, later, videos with Hungarian speech. Target languages are English, German, Spanish, and French; output is intended for DaVinci Resolve through FCPXML.

## Investigation status

The inherited application remains SRT-oriented; production code has not been refactored during these controlled tests. The tested architecture and future Hungarian-speech design are described in [ARCHITECTURE.md](ARCHITECTURE.md). The accepted product choices are in [DECISIONS.md](DECISIONS.md), and unresolved engineering work is tracked only in [TODO.md](../TODO.md).

Provider credentials are machine-specific. The initial laptop used repository-local `vertex-key.json` for Vertex service-account/ADC authentication; the RTX workstation also has an ElevenLabs credential in its local `.env`. Neither credential is stored in Git. Billing status and remaining credits were not queried.

### Restart point after documentation consolidation (2026-09-27)

The permanent documentation structure is now [AGENTS.md](../AGENTS.md), [ARCHITECTURE.md](ARCHITECTURE.md), [DECISIONS.md](DECISIONS.md), and [TODO.md](../TODO.md). `README.md` and `USER_MANUAL.md` have legacy-document warnings; they describe inherited behavior and do not override those files. Historical `.kilo/plans/` material remains untouched. The documentation work did not change application code or run another media/provider test.

In a new session, read those four authoritative files and this handoff, then start with the P0 offline DaVinci Resolve delivery/FCPXML import gate in [TODO.md](../TODO.md). Re-verify the `output/video.mp4` hash below. Use the committed ElevenLabs Natural run and synchronization manifest as the Hungarian baseline; regenerate derived WAVs/previews with `output/test_runs/2026-09-27_001434/render_synced_preview.py` if needed. Do not use a preview MP4 as source media. No new live provider call is needed for this gate.

## Controlled tests completed on 2026-09-26

The first controlled video-understanding, Hungarian narration, TTS, timing-preview, and subtitle tests have now been completed and accepted by the user as a sufficient workflow/service baseline. These tests were performed with one-off scripts and artifacts under `output/test_runs/`; production pipeline code was not modified.

### Authoritative source media

- Input: `output/video.mp4`
- SHA-256: `6582AC24DF91F6CBD89F71FCBFAC7E7C7421BAE9489E71C5734F3CDA0887D7FB`
- Duration: `86.355011` seconds
- Video: H.264, 640x360, 30000/1001 fps
- Audio: AAC stereo, 44.1 kHz; no useful spoken narration was detected
- The source is the same video as `https://youtu.be/4sXe2lpaPqA`.
- This file remains the only authoritative video input. Do not use generated previews as source media.

The video is force-added to Git despite the repository's broad media/output ignore rules so the RTX 3090 machine can reproduce the same tests. Do not begin tracking arbitrary files under `output/`.

### Video-understanding test

- Provider/model: Vertex AI `gemini-3.8-flash`
- Authentication: repository service account/ADC
- Project: `foltvilag-enterprise-audio`
- Location: `eu`
- Successful model calls: one
- Usage: 8,869 input tokens, 4,780 response tokens, 354 reasoning tokens
- Usage-based estimated cost: USD `$0.02590425`; actual Cloud Billing charge was not queried
- Primary result: structured action/evidence analysis, not SRT
- Result was independently checked against sampled video frames

The main visible workflow was correctly identified: align a transparent rigid hexagonal template with a larger fabric hexagon, secure it with two pins, fold the fabric margin over successive template edges, secure overlapping corner folds with hand stitches while rotating the piece, cut/finish the thread, remove the pins, and show the prepared unit.

Important corrections made during independent review:

- The fabric's right side versus wrong side is not visually provable.
- A future joining step must not be stated as visible fact.
- `fércelés` / `sarokrögzítés` / `az él lesimítása` are better terms than `körbevarrás` / `élélezés` for what is shown.
- Calling the workflow EPP is contextually reasonable, but the pixels alone prove a rigid-template folding and hand-basting workflow; keep that distinction reviewable.

Accepted structured fixtures are committed under `output/test_runs/2026-09-26_170438/`:

- `reviewed_video_analysis.json`
- `reviewed_hungarian_narration.json`
- `independent_review.json`
- `run_summary.json`

### Reviewed Hungarian narration and Vertex TTS comparison

The reviewed narration contains four coherent units. It avoids arbitrary subtitle-sized fragments and unsupported measurements or future steps.

TTS test configuration:

- Provider/model: Vertex AI `gemini-2.5-pro-tts`
- Voice: `Despina`
- Location: `europe-west1`
- Successful synthesis calls: one coherent full-script request
- Usage: 340 input text tokens and 1,352 output audio tokens
- Usage-based estimated cost: USD `$0.02738`; actual Cloud Billing charge was not queried
- Raw duration: `54.090958` seconds
- Speed adjustment: exactly `1.00x`
- No leading-silence trimming or time stretching was applied
- Normalized audition: approximately `-16.17 LUFS`, `-1.44 dBTP`

The user listened to the result and judged it good enough for current pipeline/workflow/service testing. More expressive voices will be compared later.

Committed baseline artifacts under `output/test_runs/2026-09-26_174358/`:

- `request.json` (contains no secret values)
- `response_metadata.json`
- `test_report.json`
- `reviewed_hungarian_narration.json` is retained in the preceding analysis run
- `tts_audition_normalized.wav` is the accepted cloud-audio comparison baseline

Recommended natural-speed placements for the four narration units:

| Unit | Start | End | Duration |
|---|---:|---:|---:|
| 1 | 1.000 | 12.659 | 11.659 s |
| 2 | 16.000 | 32.725 | 16.725 s |
| 3 | 47.000 | 59.463 | 12.463 s |
| 4 | 73.111 | 86.355 | 13.244 s |

These placements fit without acceleration. The fourth unit starts about 0.39 seconds earlier than the initial suggestion and ends at the source-video boundary.

### Timing preview and subtitles

A local FFmpeg preview was generated with source audio omitted, accepted Hungarian narration placed at the times above, and the original H.264 video stream copied without re-encoding. The user judged this preview very good.

Hungarian captions were then aligned to measured speech pauses rather than assigning one long caption to each action window. The accepted caption baseline contains nine entries, all within the 86.355-second source duration.

Committed subtitle fixture:

- `output/test_runs/2026-09-26_180852/captions_hu.srt`
- `output/test_runs/2026-09-26_180852/subtitle_manifest.json`

Rendered preview MP4 files are intentionally not committed; they are derived artifacts and can be regenerated from the source video, narration audio, placements, and SRT.

### Accepted ElevenLabs Hungarian baseline (2026-09-27)

The user-created ElevenLabs Voice Design voice is accessible through the Free-plan API. A prior assumption that it would be unavailable was disproved by successful synthesis. Community Voice Library restrictions must not be generalized to voices already saved or created in `My Voices`.

Accepted configuration:

- Provider/model: ElevenLabs `eleven_v3`
- Voice ID: `ZDiQKEyPWb5ry0OWw7Ll`
- Language: Hungarian (`hu`)
- Output request format: `mp3_44100_128`
- Stability: `0.5`
- Similarity boost: `0.75`
- Style: `0.0`
- Speaker boost: enabled
- Seed: `20260926`
- Text: the exact reviewed four-unit Hungarian narration, synthesized as one coherent script
- Raw and final speed: exactly `1.00x`; no time stretching
- Normalized format: 24 kHz mono PCM WAV, approximately `-16 LUFS`

The accepted Natural take is 40.32 seconds long. Its normalized SHA-256 is `BFDA0A1B260F17E30D94ECF0A0EEE6F8DA3251C6A5463C332AF46CC9E3B49EB0`. A Creative comparison used stability `0.0` plus a `[warmly]` cue and lasted 39.12 seconds. The user heard no meaningful advantage from Creative and selected Natural. Pronunciation, pace, and overall delivery were accepted, and the user judged ElevenLabs better than Google/Vertex for this sample.

Committed provider artifacts are under `output/test_runs/2026-09-27_000442/`:

- `eleven_v3_natural_raw.mp3`
- `eleven_v3_natural_normalized.wav`
- `run_manifest.json`

The continuous Natural take was aligned locally. A discovered `faster-whisper-large-v3` model at `D:\AI_Models\Whisper\faster-whisper-large-v3` produced word timings with CPU `int8`. GPU inference was not used because the existing Python runtime could not load `cublas64_12.dll`. Do not install/replace CUDA or NVIDIA system components merely to reproduce this alignment; the accepted timings are already persisted.

The continuous audio was split and placed without acceleration as follows:

| Unit | Source audio | Video start | Video end |
|---|---:|---:|---:|
| 1 | 0.000-9.450 | 1.000 | 10.450 |
| 2 | 9.450-21.210 | 16.000 | 27.760 |
| 3 | 21.210-30.030 | 47.000 | 55.820 |
| 4 | 30.030-40.320 | 73.111053 | 83.401 |

The synchronized preview contains nine captions aligned to measured speech timing. The user watched the burned-subtitle preview and judged the voice, video synchronization, and subtitles "great." This supersedes the earlier Google/Vertex audio as the preferred Hungarian quality baseline; retain the Google/Vertex result as a comparison fixture.

Reproducible synchronization artifacts are committed under `output/test_runs/2026-09-27_001434/`:

- `captions_hu.srt`
- `render_synced_preview.py`
- `run_manifest.json`

The renderer verifies both the authoritative video hash and accepted voice hash before doing any work. It regenerates the split WAVs, full placed WAV, selectable-subtitle MP4, and burned-subtitle MP4. Those derived media files are intentionally not committed.

At the last RTX verification, Python and pip resolved inside the repository-local `.venv` running Python 3.11. The environment itself is machine-specific and not committed.

Latest RTX workstation inspection:

- GPU: NVIDIA GeForce RTX 3090, 24,576 MiB reported VRAM
- NVIDIA driver reported by `nvidia-smi`: `616.92`
- Project interpreter: CPython `3.11.9` from `.venv`
- Project PyTorch: `2.10.0+cu130`, CUDA runtime `13.0`
- `torch.cuda.is_available()`: `True`; PyTorch identifies the RTX 3090 correctly
- `faster_whisper` is installed in `.venv`, but its GPU backend failed to load `cublas64_12.dll`; CPU `int8` was used for the completed alignment
- The Windows Python launcher command `py` is not installed; invoke `.venv\Scripts\python.exe` explicitly

### Model availability snapshot (2026-09-27)

- Video understanding used the current GA Vertex AI `gemini-3.8-flash` model.
- The tested Google comparison used Vertex AI `gemini-2.5-pro-tts`; the accepted Hungarian quality baseline is the ElevenLabs Natural take described above.
- The newest numbered TTS model available through Vertex AI is `gemini-3.1-flash-tts-preview`; it is a preview model and is available through the Vertex `global` endpoint.
- `gemini-3.8-flash-tts` is the current GA flagship for expressive/studio-grade TTS, supports Hungarian, and is presently documented through the Gemini Developer API rather than the ordinary Vertex model-location route used by this project.
- The availability claims above are a dated investigation snapshot and must be rechecked before a new provider test.

## Immediate continuation gate

The next test is the offline DaVinci Resolve delivery package and FCPXML import check, using the accepted ElevenLabs Hungarian take and authoritative video. The exact tasks and later multilingual sequence are maintained in [TODO.md](../TODO.md). No production pipeline changes have been made for the tested architecture.
