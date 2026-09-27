# Decision Record

This file records architectural and product decisions already supported by controlled tests or explicit user acceptance. It is not a backlog and does not describe unimplemented components as current behavior.

Current experiment details and provider measurements belong in [CODEX_HANDOFF.md](CODEX_HANDOFF.md). Implementation work belongs in [TODO.md](../TODO.md).

## D001 — Structured semantic state is canonical

**Decision:** The target system will use a versioned structured project document as its canonical state. It will retain meaning, evidence, uncertainty, terminology, teaching intent, timing flexibility, localization, provider configuration, audio processing, and review state.

**Evidence:** The controlled Gemini video test required independent correction of visually unsupported claims and terminology. Those distinctions could not be represented safely in SRT alone.

**Consequence:** SRT, WAV, mixed audio, preview video, and FCPXML are derived artifacts. The inherited SRT-first implementation remains until migrated deliberately.

## D002 — Mute-video understanding and narration are separate stages

**Decision:** For mute demonstrations, first produce an evidence-first factual visual timeline; only then generate instructional narration from reviewed semantic units.

**Evidence:** The controlled video response included unsupported future-workflow claims that independent review removed. The factual timeline and teaching narration were stored and reviewed separately. A production two-pass implementation has not yet been tested.

**Consequence:** Domain knowledge may inform commentary but must not be presented as visible fact. Evidence class and uncertainty remain reviewable.

## D003 — Localization is direct from approved source meaning

**Decision:** English, German, Spanish, and French are localized independently from approved Hungarian/source meaning. English is not a pivot for German, Spanish, or French.

**Basis:** This is an explicit product requirement and a safeguard against semantic drift. Direct localization has not yet been tested in this project.

**Consequence:** Each target-language artifact records its source semantic-unit version and receives its own terminology and native-language review.

## D004 — Natural speech takes priority over rigid timing

**Decision:** Natural speech quality, meaning, terminology, and idiomatic phrasing take precedence over exact subtitle-window fit.

**Evidence:** Both accepted Hungarian TTS workflows fit the video by using coherent narration groups, natural pauses, silence-based splitting, and flexible placement without acceleration.

**Consequence:** Rewrite, regroup, or reposition before regenerating; apply pitch-preserving speed changes only as a reviewed last resort. Raw/final duration and applied speed must be persisted.

## D005 — Final captions derive from approved speech

**Decision:** Caption timing is derived from final synthesized speech and approved semantic units, not used as the constraint that fragments or accelerates narration.

**Evidence:** Nine readable Hungarian captions were aligned to measured pauses in accepted continuous speech and remained synchronized after placement.

**Consequence:** Subtitle timing may be regenerated when the final voice take changes. SRT is an export, not the narration authoring format.

## D006 — ElevenLabs Natural is the accepted Hungarian quality baseline

**Decision:** For the authoritative sample, ElevenLabs `eleven_v3` using the accepted user-created voice and Natural settings is the preferred Hungarian TTS quality baseline. The Vertex Gemini 2.5 Pro TTS result remains a comparison fixture.

**Evidence:** The user compared Natural and Creative ElevenLabs takes, accepted pronunciation and pace, heard no meaningful Creative advantage, and judged the synchronized Natural preview better than the Google/Vertex sample.

**Consequence:** This is a sample-specific baseline, not an automatic provider choice for EN/DE/ES/FR. Every language still requires native blind evaluation. Voice cloning and Dubbing v2 remain deferred.

## D007 — Source media is immutable and previews are derived

**Decision:** `output/video.mp4`, identified by the hash in [CODEX_HANDOFF.md](CODEX_HANDOFF.md), is the sole authoritative input for the current controlled test series. Generated previews must not become source media for production exports.

**Evidence:** Controlled tests and reproducible renderers use and verify the same committed source bytes.

**Consequence:** All edits, mixes, subtitles, and FCPXML outputs are non-destructive and stored as derived run artifacts.

## D008 — Provider profiles and credentials remain explicit

**Decision:** Vertex AI/service-account ADC remains a distinct provider profile. Gemini Developer API, ElevenLabs, DeepSeek, and local models must use separate explicit profiles and must not share implied authentication, quota, privacy, or model assumptions.

**Evidence:** The inherited `VERTEX_API_KEY` gate does not reflect actual Vertex ADC use, and Gemini 3.8 Flash TTS availability differs from the Vertex TTS catalog.

**Consequence:** Provider selection and authentication must be explicit in the eventual implementation. The live-call approval procedure is maintained in [AGENTS.md](../AGENTS.md).

## D009 — Target-language voices are selected per language

**Decision:** Do not reuse the accepted Hungarian voice automatically for foreign-language narration. Select and review a voice that sounds natural in each target language and is suitable for the intended audience.

**Evidence:** For the controlled English test, the user rejected the assumption that a Hungarian-configured voice would be the best English default, selected ElevenLabs voice `XrExE9yKIg1WjnnlVkGX`, and accepted its English narration and synchronized preview.

**Consequence:** The selected English voice is a sample-specific baseline, not a universal multilingual voice. German, Spanish, and French still require their own direct localization and native-listener voice review.
