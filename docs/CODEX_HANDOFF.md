# Codex Handoff

## Project purpose

YoutubeVoice is a Python pipeline for producing multilingual instructional voiceovers for patchwork, English Paper Piecing (EPP), Foundation Paper Piecing (FPP), sewing, sashiko, and textile-art videos. It must support both mute demonstrations and, later, videos with Hungarian speech. Target languages are English, German, Spanish, and French; output is intended for DaVinci Resolve through FCPXML.

Design priority, in order:

1. Natural, convincingly human speech
2. Correct instructional meaning
3. Professional domain terminology
4. Natural target-language phrasing
5. Timing fit

No live provider call or application-code change was made during the 2026 review described below.

## Confirmed current facts

### Implementation

- `run_pipeline.py` orchestrates transcription/video analysis, translation, TTS, and FCPXML export.
- `pipeline/eyes.py` sends inline video bytes to Vertex AI Gemini and asks for a Hungarian SRT.
- `pipeline/ears.py` extracts/converts audio and asks Gemini for an SRT with tone tags, but writes any nonempty response without the repair/parse validation used by the vision path.
- `pipeline/brains.py` uses DeepSeek first and Gemini as fallback. It currently translates Hungarian to an English pivot, then English to other targets.
- `pipeline/voice.py` generates one Gemini TTS WAV per SRT entry. Any utterance longer than its fixed SRT window is accelerated with FFmpeg `atempo`; the original duration and applied speed are not persisted.
- `pipeline/fcpxml.py` builds FCPXML 1.12 with muted source video and positioned WAV clips.
- `prompts/video_analysis.txt` is hardcoded for one specific EPP hexagon/EZpiecer demonstration and is not safe as a general patchwork, FPP, sashiko, sewing, or textile-art prompt.
- Python source parses and core pipeline imports succeed. FFmpeg/ffprobe are installed and working.
- There is no automated test suite, dependencies are unpinned, and there is no lock file or `pyproject.toml`.
- The Streamlit dashboard has an undefined `wav_dir` in `scan_output_dir()`, its full-pipeline button is a placeholder, and Streamlit is not installed in the current repository virtual environment.

### Authoritative test input and output state

- All old generated SRT, WAV, and FCPXML artifacts have been deleted.
- `output/video.mp4` is the only file currently under `output/` and is the authoritative test input.
- The video is approximately 86.355 seconds, 640x360, 29.97 fps, H.264 with a very quiet AAC stereo track. Visual inspection shows the intended EPP hexagon preparation/folding/basting workflow.
- No previous generated output should be treated as a quality, timing, cache, or Resolve-import baseline.

### Authentication

- The repository-root `vertex-key.json` exists and is a Google `service_account` credential for project `foltvilag-enterprise-audio`. Its private contents must never be printed, logged, documented, or committed.
- `pipeline/config.py` forces `GOOGLE_APPLICATION_CREDENTIALS` to that repository-local file and creates `genai.Client(vertexai=True, project="foltvilag-enterprise-audio", location="us-central1")`.
- `VERTEX_API_KEY` is present in `.env`, but is not passed to the Vertex client. CLI/UI code incorrectly uses its presence as a prerequisite/status gate.
- `DEEPSEEK_API_KEY` is present and is used by the OpenAI-compatible DeepSeek client.
- An ElevenLabs credential is configured in the repository-local `.env`; its value must never be printed, logged, documented, or committed. The key has text-to-speech and Voices read permission. The repository-local `.env` remains machine-specific and is not a portable credential mechanism.
- Billing status, remaining credits, service-account IAM roles, and live quotas were not queried and remain unknown.
- The intentional production authentication design is Vertex AI with service-account/ADC, not an accidental API-key setup. A Gemini Developer API mode, if added, must be a separate explicit provider profile.

### Current model/provider status as of September 2026

- `gemini-2.5-flash` remains usable, but Gemini 3.8 Flash is the current GA multimodal workhorse and the preferred candidate for new video analysis. On Vertex it is documented for `global`, `us`, and `eu`, not the current hardcoded `us-central1` endpoint.
- `gemini-3.1-flash-tts-preview` is now a legacy preview model in the Gemini Developer API. Gemini 3.8 Flash TTS is the current flagship Developer API TTS candidate for studio-grade fidelity, expression, and long-form stability.
- For the existing Vertex/service-account route, current Cloud/Vertex TTS candidates include Gemini 2.5 Pro TTS and Gemini 3.1 Flash TTS Preview through supported `global`, `us`, or `eu` endpoints. Hungarian is still preview in Gemini Cloud TTS; EN/DE/ES/FR are GA.
- DeepSeek discontinued the legacy `deepseek-chat` name in July 2026. The low-cost current replacement is `deepseek-flash`; `deepseek-v4-pro` is the higher-cost alternative.
- `faster-whisper` using multilingual large-v3 or turbo is the leading zero-marginal-cost Hungarian ASR candidate. The initial laptop review detected no NVIDIA GPU; the later RTX workstation state is recorded below.
- Gemini 3.5 Transcribe and Google Cloud Speech-to-Text Chirp 3 are useful cloud ASR comparisons. Cloud STT supports `hu-HU`; its first 60 minutes per month are currently free, while Hungarian Chirp 3 support is preview.
- ElevenLabs is now the accepted Hungarian TTS baseline for this sample. Eleven v3 was more convincing than the accepted Google/Vertex comparison. Professional Voice Cloning remains deferred; Dubbing v2 is relevant for future voice-preserving dubbing but is much more expensive than plain TTS.
- XTTS-v2 supports HU/EN/DE/ES/FR and cross-language local voice cloning, but should be treated as an experimental offline fallback until it wins a listening test and its licensing fits the intended use.

## Recommended 2026 architecture

Retain the Python/FFmpeg/Streamlit/FCPXML foundation, but replace SRT as the canonical internal state with a structured, versioned project document. SRT, WAV files, and FCPXML should become derived exports.

Recommended flow:

1. Ingest and probe media.
2. Classify whether useful source speech exists.
3. Build independent speech and visual timelines as applicable.
4. Fuse them into semantic instructional units.
5. Review/lock meaning and terminology.
6. Localize directly from Hungarian/source meaning to each target language.
7. Plan natural narration windows and fit text before TTS.
8. Generate/audition TTS in coherent utterance groups.
9. Place, mix, and normalize audio.
10. Derive SRT and FCPXML and validate them against media duration.

Each semantic unit should be able to store:

- spoken/source meaning and source evidence;
- visual actions, objects, tools, materials, and timestamps;
- teaching intent and importance (`required`, `useful`, `optional`);
- approved terminology and pronunciation hints;
- tone, emphasis, rhythm, and speaker identity;
- hard/soft timing bounds and safe placement flexibility;
- localized scripts and duration estimates;
- provider/model/voice, input hash, measured duration, placement, and any speed adjustment;
- confidence and human-review state.

For mute videos, use two passes: first extract a factual action timeline with confidence/evidence, then create instructional commentary using a selected domain profile. Do not ask the model to directly emit final SRT in the same pass that it is trying to understand the technique.

Use direct HU-to-target localization. English remains a target and may be a reviewer reference, but should not be the source for German, Spanish, or French. Add a versioned bilingual/multilingual termbase with approved and prohibited translations, product spellings, pronunciation hints, and technique applicability.

## Natural-speech-first timing policy

- Never force arbitrary acceleration merely to fill an SRT window.
- Generate complete sentences or short coherent utterance groups rather than isolated subtitle fragments.
- Fit duration in this order:
  1. remove nonessential wording;
  2. rewrite more concisely and idiomatically;
  3. improve segmentation or merge adjacent units;
  4. shift start/end placement within visually safe bounds;
  5. redistribute narration across nearby silence or ongoing actions;
  6. regenerate TTS;
  7. only then apply a small pitch-preserving speed adjustment.
- Suggested default: allow up to about `1.03x`; require an explicit warning/review above `1.05x`. Never silently exceed the configured ceiling.
- Preserve raw audio, raw duration, final duration, applied speed, and text revision in the manifest.
- Replace sample-threshold leading-silence trimming with safer VAD/padding so quiet consonants, breaths, and natural phrase onsets are not clipped.
- Normalize loudness and use short fades/crossfades, but retain natural pauses and phrase endings.
- For mute demonstrations, allow narration to overlap ongoing visible work when semantically safe; narration does not need to end at every subtitle boundary.

## Future Hungarian-speech multimodal workflow

When Hungarian speech exists:

- Speech is the primary semantic source.
- ASR should retain word/segment timestamps, confidence, speaker information, disfluencies as needed, and terminology candidates.
- Vision independently records visible actions, materials, tools, spatial references, and evidence timestamps.
- A fusion stage aligns speech with the visual timeline and resolves references such as "this," "here," or "the other side."
- Visual context may correct likely ASR/terminology errors or suggest additions, but every correction/addition should remain reviewable and traceable.

Support two explicit modes:

1. **Faithful dubbing:** preserve meaning, omissions, tone, emphasis, rhythm, pauses, and teaching style; use vision only for disambiguation and terminology.
2. **Enhanced instructional localization:** preserve essential meaning while adding concise, visually supported teaching information. Additions must be marked in structured metadata and be individually disableable.

For future voice preservation, benchmark ElevenLabs Dubbing v2/PVC against Gemini voice-replication options and local XTTS-v2. Do not assume cross-language cloning is accent-neutral; native listeners must evaluate every target language.

## Recommended provider policy

- Keep Vertex AI/service-account authentication as the default production path for multimodal analysis and Google Cloud models.
- Optionally add a separate Gemini Developer API profile for free-tier experiments. Do not conflate its API key, privacy terms, quotas, or models with Vertex.
- Prefer local faster-whisper for routine Hungarian transcription when its accuracy and runtime are acceptable; keep cloud ASR as an opt-in comparison/fallback.
- Keep DeepSeek as a low-cost translation candidate after updating to `deepseek-flash`, but select the final translator through a domain-specific HU/EN/DE/ES/FR benchmark.
- Final TTS must be chosen by blind native-listener evaluation per language. Primary candidates are Gemini 3.8 Flash TTS, Vertex Gemini 2.5 Pro TTS, and ElevenLabs. Cost is secondary at this stage.
- ElevenLabs Dubbing v2 should not be the default mute-video path because it is priced per source minute per target language; reserve it for speech-containing, voice-preserving work.

## Existing engineering issues to retain in scope

1. Fix the unused `VERTEX_API_KEY` gate and make project, location, and credential selection explicit without exposing secrets.
2. Add response validation and repair to audio transcription.
3. Replace the English pivot and validate terminology/prosody metadata, not only timestamps and entry counts.
4. Replace mtime-only WAV caching with content/config hashes and a persisted run manifest.
5. Detect/archive/remove orphaned outputs from prior revisions.
6. Reconstruct resume state from the manifest/filesystem; do not rely on Streamlit session state.
7. Make Phase 5 reconstruct valid cached audio inputs when Phase 4 is skipped.
8. Validate that all SRT/audio clips stay within video duration and that all FCPXML media paths resolve.
9. Test generated FCPXML by importing into the supported DaVinci Resolve version and reviewing its import log.
10. Pin dependencies and add offline unit/integration tests before live provider work.

## Controlled next test

Before any live call, tell the user the provider/model, credential/project/location, expected free or paid quota, estimated cost, and expected artifact, then obtain approval.

Recommended first live test:

- Provider/model: Vertex AI `gemini-3.8-flash`.
- Credential/project: repository service-account JSON, project `foltvilag-enterprise-audio`.
- Location: `global` for the test, without changing application code first.
- Input: authoritative `output/video.mp4`.
- Output: non-destructive structured analysis under `output/test_runs/`; do not overwrite the source video.
- Billing: paid Vertex Standard usage unless existing credits apply; credit/billing state is unknown.
- Estimated cost: roughly USD $0.015-$0.04 for this short sample, depending on media resolution, reasoning, and output length.
- Evaluate: visual understanding, action timing, teaching quality, unsupported claims, terminology, and whether every timestamp stays within 86.355 seconds.

Only after reviewing that result should translation and TTS calls be proposed. A later controlled run should also verify cache/resume behavior, runtime bottlenecks, FCPXML generation, and import into DaVinci Resolve.

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

### Accepted Hungarian narration and TTS baseline

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

The project uses only `C:\Projects\YoutubeVoice\.venv` for Python dependencies. At the last verification, both Python and pip resolved inside that environment; it used Python 3.11. A virtual environment itself is not portable and is not committed. On another machine, recreate `.venv` inside the repository and install dependencies there only. Do not install packages globally or modify NVIDIA drivers/CUDA system components without explicit approval.

Latest RTX workstation inspection:

- GPU: NVIDIA GeForce RTX 3090, 24,576 MiB reported VRAM
- NVIDIA driver reported by `nvidia-smi`: `616.92`
- Project interpreter: CPython `3.11.9` from `.venv`
- Project PyTorch: `2.10.0+cu130`, CUDA runtime `13.0`
- `torch.cuda.is_available()`: `True`; PyTorch identifies the RTX 3090 correctly
- `faster_whisper` is installed in `.venv`, but its GPU backend failed to load `cublas64_12.dll`; CPU `int8` was used for the completed alignment
- The Windows Python launcher command `py` is not installed; invoke `.venv\Scripts\python.exe` explicitly

### Current model distinction

- Video understanding used the current GA Vertex AI `gemini-3.8-flash` model.
- The accepted TTS baseline used Vertex AI `gemini-2.5-pro-tts`, selected as the quality-oriented regional Vertex option.
- The newest numbered TTS model available through Vertex AI is `gemini-3.1-flash-tts-preview`; it is a preview model and is available through the Vertex `global` endpoint.
- `gemini-3.8-flash-tts` is the current GA flagship for expressive/studio-grade TTS, supports Hungarian, and is presently documented through the Gemini Developer API rather than the ordinary Vertex model-location route used by this project.
- A future Gemini 3.8 Flash TTS experiment must be an explicit separate Gemini Developer API provider profile. Do not silently reuse or reinterpret Vertex ADC configuration.

## RTX 3090 continuation plan

The next machine is an HP OMEN workstation with an NVIDIA RTX 3090. The purpose of moving there is to test GPU-heavy local candidates without treating the current laptop's lack of NVIDIA hardware as a quality verdict.

### First steps on the OMEN

1. Clone/pull this commit and verify `output/video.mp4` against the authoritative SHA-256 above.
2. Read this handoff before installing or running models.
3. Inspect the existing NVIDIA driver, CUDA compatibility reported by the driver, VRAM, Python version, and free disk space. Do not replace drivers or install a CUDA toolkit blindly.
4. Create an isolated environment for local-model experiments; do not destabilize the existing application environment.
5. Store every new result in a new `output/test_runs/YYYY-MM-DD_HHMMSS/` directory with model, version, configuration, hashes, runtime, peak VRAM, and measured audio durations.
6. Preserve the accepted Vertex audio and structured narration as fixed baselines. Do not rewrite the Hungarian script during the first local TTS comparison.

### Local TTS benchmark

Start with the exact four-unit Hungarian narration in `reviewed_hungarian_narration.json`. Candidate local systems should be tested at natural speed and compared blindly against `tts_audition_normalized.wav`.

Record at minimum:

- model/repository and exact revision;
- license and commercial-use implications;
- voice/reference-audio requirements and consent constraints;
- generation seed and inference settings;
- per-unit and total runtime, real-time factor, and peak VRAM;
- raw sample rate/format and raw duration;
- any normalization, silence handling, or resampling;
- pronunciation of `varrásráhagyást`, `gombostűvel`, `textilrétegeket`, `rögzítőtűt`, and `hatszögelem`;
- native-speaker ratings for human likeness, Hungarian accent, warmth, prosody, consistency, and instructional suitability.

XTTS-v2 remains an experimental first candidate because it supports Hungarian and cross-language voice cloning, but it must win the listening test and pass licensing review. Do not assume that voice cloning guarantees native Hungarian pronunciation.

### Local ASR benchmark

The authoritative current video is not a meaningful Hungarian ASR benchmark because it contains no useful speech. Do not draw ASR-quality conclusions from it.

For a future speech-containing Hungarian test clip, benchmark faster-whisper `large-v3` and `turbo` on the RTX 3090. Preserve word/segment timestamps, confidence where available, terminology candidates, and runtime/VRAM measurements. Compare accuracy specifically on patchwork/sewing terminology. Keep visual analysis as complementary evidence, not as a replacement for the spoken semantic source.

### Other RTX-beneficial workloads

- local multimodal/video-model comparisons;
- local LLM translation experiments;
- voice cloning and speaker-preservation tests;
- source separation, denoising, or batch audio processing;
- high-resolution or batch media preprocessing.

The laptop remains suitable for Python orchestration, FFmpeg, JSON/manifests, cloud calls, translation review, audio placement, subtitles, FCPXML, and UI work.

## Immediate continuation gate

The next test should be offline and cost-free: create a DaVinci Resolve delivery package from the accepted Hungarian baseline and verify FCPXML import. The package should reference the authoritative source video plus the four positioned narration WAVs and the accepted Hungarian subtitles. Check that all media paths resolve, narration and captions remain synchronized, no clip exceeds 86.355011 seconds, and Resolve reports no import errors. Do not use a compressed preview MP4 as production source media.

After Resolve import succeeds, perform the first multilingual workflow test:

1. Localize directly from the approved Hungarian structured meaning to English.
2. Review and approve the English script before any TTS call.
3. Generate English TTS, place it naturally against the same authoritative video, and derive English subtitles.
4. Repeat independently for German, Spanish, and French only after English is accepted. Do not use English as a pivot.

Before every new live provider call, state provider/model, credentials/profile, expected quota or cost, and expected artifact, then obtain approval. Voice cloning remains explicitly deferred.

## Next cloud/workflow gate

After or alongside the local baseline work, the next cloud workflow test is direct Hungarian-to-English localization from the approved structured narration. English should be reviewed before TTS. Then generate English TTS, place it against the same authoritative video, and derive English subtitles. German, Spanish, and French follow only after the English workflow is accepted.

Do not use English as a pivot for German, Spanish, or French. Each target must localize directly from the approved Hungarian/source meaning and structured evidence.

No production pipeline changes have yet been made for the tested architecture. The engineering issues listed earlier in this handoff remain open.
