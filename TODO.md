# Engineering Backlog

This is the only authoritative current backlog. `.kilo/plans/` is retained as historical context and must not be treated as active TODOs.

Priorities reflect current validated workflow evidence. Product and architectural rationale belongs in `docs/DECISIONS.md`; implementation boundaries belong in `docs/ARCHITECTURE.md`; experiment details belong in `docs/CODEX_HANDOFF.md`.

## P0 — Next validation gate

- [x] Build a non-destructive DaVinci Resolve delivery package from the accepted Hungarian ElevenLabs baseline: authoritative source video, four positioned narration WAVs, Hungarian subtitles, manifest, and FCPXML.
- [x] Validate that every media path resolves and every clip/caption stays within the authoritative source duration recorded in `docs/CODEX_HANDOFF.md`.
- [x] Import the FCPXML into the supported DaVinci Resolve version and record the import result/log and any compatibility corrections.
- [x] Confirm that the imported timeline uses `output/video.mp4`, not a compressed preview.

## P1 — Canonical project state

- [ ] Define and version a structured project-document schema for source evidence, semantic units, terminology, localization, narration windows, provider outputs, placement, confidence, and human-review state.
- [ ] Add migration/import support from the current SRT-oriented state without deleting legacy behavior prematurely.
- [ ] Persist a complete run manifest with content/configuration hashes, provider/model/voice, raw/final durations, processing, placement, and cost/usage metadata.
- [ ] Reconstruct resume state from manifests and the filesystem instead of Streamlit session state.
- [ ] Detect and report orphaned outputs from prior revisions; archive or remove them only with explicit policy/approval.

## P1 — Provider and configuration correctness

- [ ] Replace hardcoded model/project/location selection with explicit provider profiles.
- [ ] Remove the incorrect `VERTEX_API_KEY` prerequisite for service-account/ADC Vertex operation.
- [ ] Keep Gemini Developer API configuration explicitly separate from Vertex AI credentials, quotas, privacy terms, and models.
- [ ] Update the inherited DeepSeek configuration from retired `deepseek-chat`; benchmark `deepseek-flash` and any higher-quality candidate before choosing a production translator.
- [ ] Replace mtime-only WAV caching with source-text, prompt, provider, model, voice, and processing hashes.
- [ ] Pin dependencies and choose a reproducible lock strategy for Windows laptop and RTX workstation environments.

## P1 — Analysis and transcription

- [ ] Replace the video-specific `prompts/video_analysis.txt` with versioned domain profiles and an evidence-first two-pass mute-video workflow.
- [ ] Add validation/repair for audio transcription responses equivalent to or stronger than the vision path.
- [ ] Add a useful-source-speech classifier before choosing mute-video versus speech-containing workflow.
- [ ] For a future Hungarian-speech test clip, benchmark faster-whisper `large-v3` and `turbo` with word/segment timing, terminology accuracy, runtime, and VRAM reporting.
- [ ] Resolve or isolate the RTX faster-whisper/CTranslate2 `cublas64_12.dll` compatibility issue without destabilizing the working driver/PyTorch environment.
- [ ] Benchmark cloud ASR only as an explicit comparison/fallback after local results are measured.

## P1 — Localization and terminology

- [ ] Replace the English-pivot translation flow with direct Hungarian/source-to-target localization for EN, DE, ES, and FR.
- [ ] Create a versioned multilingual termbase with approved/prohibited translations, product spelling, pronunciation hints, and technique applicability.
- [ ] Validate terminology, meaning, evidence boundaries, and prosody metadata—not only subtitle count and timestamps.
- [x] Run the first controlled direct Hungarian-to-English localization test and obtain script approval before English TTS.
- [x] Complete and review the controlled English TTS, silence-aligned captions, synchronized preview, and Resolve/FCPXML delivery fixture.
- [ ] Repeat independently for German, Spanish, and French only after the English workflow is accepted.

## P1 — Narration, audio, and subtitles

- [ ] Generate and store coherent utterance groups instead of one TTS request per subtitle fragment.
- [ ] Implement natural-speech-first fitting and enforce configured speed ceilings and warnings.
- [ ] Replace sample-threshold leading-silence trimming with VAD/padding that protects quiet consonants and breaths.
- [ ] Add reproducible loudness normalization, short fades/crossfades, and placement validation while retaining natural pauses.
- [ ] Derive subtitle timing from final synthesized speech and approved semantic units.
- [ ] Ensure Phase 5 can reconstruct valid cached audio inputs when Phase 4 is skipped.
- [ ] Benchmark Gemini 3.8 Flash TTS, Vertex alternatives, ElevenLabs, and viable local TTS per language using native blind listening.
- [ ] Evaluate local TTS candidates, including XTTS-v2, for quality, runtime, voice preservation, and commercial licensing.
- [ ] Keep professional voice cloning and ElevenLabs Dubbing v2 deferred until an explicit consent, cost, and quality test is approved.

## P2 — Export and UI

- [ ] After explicit destructive/publish confirmation, replace the existing Hungarian descriptive audio/subtitles and English (United States) audio/subtitles on YouTube video `4sXe2lpaPqA`; preserve the Hungarian original and all French tracks unchanged.
- [ ] Update FCPXML generation to consume the canonical project document and validated media manifest.
- [ ] Fix `scan_output_dir()` using undefined `wav_dir`.
- [ ] Implement the Streamlit full-pipeline action.
- [ ] Show provider/profile, cache/manifest state, warnings, review gates, and recoverable resume state in the UI.
- [ ] Preserve separate faithful-dubbing and enhanced-instructional-localization modes when Hungarian-speech support is implemented.

## P2 — Automated quality and maintenance

- [ ] Add offline unit tests for SRT parsing/repair, timestamp bounds, hashing, manifests, cache invalidation, and FCPXML path resolution.
- [ ] Add integration fixtures using the committed authoritative video and accepted structured/audio/subtitle baselines without making live provider calls.
- [ ] Add checks that private credentials and raw secret values cannot enter logs, manifests, or commits.
- [ ] Add regression checks that production exports never use generated preview MP4s as source media.
- [ ] Document supported Python/FFmpeg/DaVinci versions after the first successful Resolve import.
