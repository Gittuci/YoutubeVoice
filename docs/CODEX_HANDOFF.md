# Codex Handoff

This is the current investigation and session handoff. Read [agent instructions](../AGENTS.md), the [engineering backlog](../TODO.md), the [architecture](ARCHITECTURE.md), and the [decision record](DECISIONS.md) for durable guidance. `.kilo/plans/` is historical material.

## Project purpose

YoutubeVoice is a Python pipeline for producing multilingual instructional voiceovers for patchwork, English Paper Piecing (EPP), Foundation Paper Piecing (FPP), sewing, sashiko, and textile-art videos. It must support both mute demonstrations and, later, videos with Hungarian speech. Target languages are English, German, Spanish, and French; output is intended for DaVinci Resolve through FCPXML.

## Investigation status

The inherited application remains SRT-oriented; production code has not been refactored during these controlled tests. The tested architecture and future Hungarian-speech design are described in [ARCHITECTURE.md](ARCHITECTURE.md). The accepted product choices are in [DECISIONS.md](DECISIONS.md), and unresolved engineering work is tracked only in [TODO.md](../TODO.md).

Provider credentials are machine-specific. The initial laptop used repository-local `vertex-key.json` for Vertex service-account/ADC authentication; the RTX workstation also has an ElevenLabs credential in its local `.env`. Neither credential is stored in Git. Billing status and remaining credits were not queried.

### Output retention state

At the user's request on 2026-09-27, every local and tracked file below `output/` was deleted except `output/video.mp4`. The video remains tracked and its SHA-256 remains `6582AC24DF91F6CBD89F71FCBFAC7E7C7421BAE9489E71C5734F3CDA0887D7FB`. The test descriptions, settings, review outcomes, placements, and hashes below are retained as the durable record, but their referenced `output/test_runs/` paths no longer exist in the current checkout. Some older baseline files remain recoverable from Git history before the cleanup commit; the later Resolve and English run artifacts were never pushed and must be recreated by a future controlled run if needed.

### Restart point after the accepted English test (2026-09-27)

The permanent documentation structure is now [AGENTS.md](../AGENTS.md), [ARCHITECTURE.md](ARCHITECTURE.md), [DECISIONS.md](DECISIONS.md), and [TODO.md](../TODO.md). `README.md` and `USER_MANUAL.md` have legacy-document warnings; they describe inherited behavior and do not override those files. Historical `.kilo/plans/` material remains untouched. The documentation work did not change application code or run another media/provider test.

On another machine, first run `git pull --ff-only origin main`, then read the authoritative files and this handoff. Re-verify the `output/video.mp4` hash below before any media work. The Hungarian Resolve/FCPXML P0 gate and the first controlled English localization/TTS/synchronization test are complete. The next safe action is either to resume the paused YouTube replacement only after confirming the exact destructive/publish scope, or to begin a separately approved direct Hungarian-to-German localization test. Do not use a preview MP4 as source media, and do not make a new live provider call without the approval required by [AGENTS.md](../AGENTS.md).

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

The offline Hungarian Resolve gate and controlled English workflow are complete. Work stopped before any YouTube mutation. Resume from the paused replacement plan at the end of this file only after explicit action-time confirmation, or continue with the next independently approved target language from [TODO.md](../TODO.md). No production pipeline migration has been made for the tested architecture.

### Completed P0 delivery result (2026-09-27, laptop)

An offline delivery package was built under `output/test_runs/2026-09-27_111835/resolve_delivery/` without provider calls. It contains four newly derived PCM WAV narration clips, the accepted Hungarian SRT, an FCPXML 1.12 timeline, and a manifest. Static preflight passed: every referenced media path resolves, the FCPXML references the authoritative `output/video.mp4` hash rather than a preview, and all narration/caption intervals stay within 86.355011 seconds.

The package was imported successfully into DaVinci Resolve 21.1.0.17 in project `YoutubeVoice_FCPXML_P0_20260927`. The user confirmed that all media was online, the timeline contained the authoritative `video.mp4`, four narration clips, and nine Hungarian subtitle clips, and no warning/error dialog appeared. The full-timeline screenshot showed the four narration clips in the accepted action windows; Resolve displayed frame-rounded durations at 29.97 fps. For accurate synchronization, Resolve required the imported SRT item to be placed at 1.000 second, aligned with the beginning of `hu_01.wav`, rather than at the beginning of the video. Treat this as an observed Resolve import-placement requirement for the current SRT artifact. Log review confirmed the import and project save. Resolve logged `skipping the addition of compound clip having non-standard frame rate or empty`, but the intended timeline contents were complete, so this was treated as a non-blocking warning and no compatibility correction was required. See `output/test_runs/2026-09-27_111835/resolve_import_result.json`, `resolve_import_log_excerpt.txt`, and the delivery manifest. The P0 offline delivery/import gate is complete.

Native Windows application automation remains unavailable in both the original Codex session and a concurrent ChatGPT desktop test: only Chrome and the in-app browser were exposed. The Computer Use plugin is installed, but its native Windows pipe was unavailable. A clean test should fully quit VS Code and Codex/ChatGPT processes, restart Windows, then start one desktop-hosted Codex session and ask it to list native Windows apps. This automation issue does not affect the successful Resolve import result.

An internal Resolve Free utility was added under `scripts/resolve/`. Resolve 21 Free exposed only its Lua console and did not enumerate the installed Python script, so `YoutubeVoice_Import_Test.lua` is the primary utility; the Python version is retained as a reference. The Lua utility was successfully executed inside Resolve 21.1 Free on 2026-09-27 using the `YVTest.lua` console launcher. It saved the open project, created an isolated timestamped project, requested 29.97 fps and 640x360, imported the accepted FCPXML, and validated the authoritative video plus all four narration clips and placements. Its final status was `success_pending_manual_subtitle_placement`, with zero provider calls. Resolve's default safe internal-Lua environment blocks the standard `io` library, so the Console status and saved timestamped Resolve project are the execution record rather than a script-written JSON report. Resolve also did not accept the SRT through `MediaPool:ImportMedia`; import `captions_hu.srt` manually and place it at 1.000 second aligned with `hu_01.wav`. See `scripts/resolve/README.md` and `output/test_runs/2026-09-27_111835/resolve_internal_lua_result.json`.

## Accepted controlled English workflow (2026-09-27)

The first direct Hungarian-to-English controlled workflow is complete. It used one approved localization call and one approved TTS call; neither was retried. Production pipeline code remains unchanged.

### Direct English localization

- Provider/model: Vertex AI `gemini-3.8-flash`
- Authentication/profile: repository service account/ADC
- Project/location: `foltvilag-enterprise-audio`, `eu`
- Calls: one direct Hungarian-to-English localization call; English was not used as a pivot for another language
- Usage: 3,096 input tokens and 1,811 output tokens
- Estimated usage cost: USD `$0.010024575`; actual billing was not queried
- Result: the user approved the English script after retaining “for now” to express that the reusable template is removed later and removing “outer” from “outer seam allowance”

The request, raw response, candidate, and approved result are preserved under `output/test_runs/2026-09-27_143936/`. The approved text remains the authoritative source for this English test.

The `output/` tree is intentionally ignored, and all files from this run were deleted after their results were documented. The exact English provider and delivery artifacts are therefore unavailable in the current checkout. Recreating them requires a new controlled run and, where a live provider call is necessary, fresh approval under [AGENTS.md](../AGENTS.md).

### English narration

- Provider/model: ElevenLabs `eleven_v3`
- Voice ID: `XrExE9yKIg1WjnnlVkGX`
- Language: English (`en`)
- Settings: stability `0.5`, similarity boost `0.75`, style `0.0`, speaker boost enabled, seed `20260926`
- Calls: one, containing 641 characters; no provider retry
- Raw MP3: 39.55 seconds, SHA-256 `C655DF1E2DFF553BC87478B5B99D90072106D477538BCDC7C836C31C6E00B33C`
- Normalized WAV: 39.52 seconds, 24 kHz mono, approximately `-16.04 LUFS` and `-1.50 dBTP`, SHA-256 `3511C1CEEE1911A26C944C531AA8EC30D08CAB297C84212F74EC8E3ECA156A2E`
- Processing: no trimming or speed adjustment

FFmpeg was not available on `PATH` during the first local normalization attempt. The already-paid provider result was preserved and normalized locally with `imageio_ffmpeg`; `run_english_tts_test.py --resume-local-only` supports that recovery without another provider call. The user heard no meaningful difference between raw and normalized versions and accepted the voice.

### English synchronization and delivery

The current laptop did not contain `D:\AI_Models\Whisper\faster-whisper-large-v3` or the `faster_whisper` package. No model was downloaded and no package was installed. Instead, the accepted continuous take was segmented at six clean measured silence boundaries that map exactly to its seven approved sentences. Four narration units and 13 readable caption phrases were placed within the authoritative 86.355011-second source. This is explicitly silence-aligned sentence timing, not word-level ASR timing.

Key artifacts and hashes:

- Placed upload WAV: `english_sync/voiceover_en_placed.wav`, SHA-256 `D0A7C0C4CF02A156381CF6C56DF8A646C3D39CDDCCA016473E442E95079AB96E`
- English SRT: `english_sync/captions_en.srt`, SHA-256 `3D2B92752A833807067BDAC65DA7FE1DB4AB96C14ABFFF64195F364ABD6DF272`
- Soft-subtitle preview: SHA-256 `8F1C84DB0EB3840D9A50E82841509B6B475B66E729B8A4A83834E877D17AAFB4`
- Burned-subtitle preview: SHA-256 `4DDF5179B68CBE68230788B4F84986E557F2C9BDBDF5FB1145D14DC6759014D9`
- Resolve FCPXML: `resolve_delivery_en/youtubevoice_en.fcpxml`, SHA-256 `503DAFFB69EF2CB27AA3FFDAD7C366DD28F278F1A15FBB5C21711729B6A0D56B`

Offline validation passed for the authoritative source hash, four narration units, interval bounds, non-overlapping captions, media-path resolution, and the rule that FCPXML uses `output/video.mp4` rather than a preview. Both previews were 86.36 seconds; the selectable preview contained the English subtitle stream, and the burned preview decoded successfully. The user watched the burned preview and accepted the narration, synchronization, and subtitles. These derived files and the one-off build script were subsequently deleted under the output-retention cleanup above.

## Paused YouTube replacement plan

No YouTube content was deleted, uploaded, replaced, or published. A read-only inspection of YouTube Studio for `https://youtu.be/4sXe2lpaPqA` found:

- source language Hungarian with the original Hungarian audio published;
- a separate Hungarian descriptive audio track published manually;
- Hungarian subtitles present;
- English (United States) uploaded audio published and one manual subtitle published;
- French audio and one French subtitle published.

The proposed scope, still requiring explicit confirmation immediately before destructive/public actions and regeneration of the deleted upload files, is:

1. Keep the original Hungarian audio unchanged.
2. Replace only the Hungarian descriptive audio with `output/test_runs/2026-09-27_001434/voiceover_placed.wav` and replace its subtitles with `captions_hu.srt` from the same run.
3. Replace the English (United States) audio with `output/test_runs/2026-09-27_143936/english_sync/voiceover_en_placed.wav` and replace its manual subtitle with `english_sync/captions_en.srt`.
4. Leave all French audio and subtitles unchanged.

Deleting existing language assets and publishing replacements are separate consequential actions. Reinspect the current Studio state and obtain action-time confirmation before each destructive or public mutation. The original video/primary Hungarian audio cannot be replaced while retaining the same YouTube URL; this plan changes only supported additional-language assets.
