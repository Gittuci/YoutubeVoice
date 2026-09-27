# Architecture

This document distinguishes the inherited implementation that exists today from the validated target architecture. It does not claim that planned components are implemented.

For accepted product decisions, see [DECISIONS.md](DECISIONS.md). For active work, see [TODO.md](../TODO.md). For experiments, hashes, provider results, and machine state, see [CODEX_HANDOFF.md](CODEX_HANDOFF.md).

## 1. Current inherited implementation

Status: implemented before the current Codex investigation; retained for compatibility and not yet refactored.

```text
YouTube URL or media
        |
        v
pipeline/eyes.py or pipeline/ears.py
        |
        v
Hungarian SRT
        |
        v
pipeline/brains.py
Hungarian -> English -> DE/ES/FR
        |
        v
pipeline/voice.py
one TTS WAV per SRT entry; overlong audio accelerated
        |
        v
pipeline/fcpxml.py
muted source video + positioned WAV clips
```

### Components

- `run_pipeline.py` orchestrates phases 2–5.
- `pipeline/eyes.py` sends inline video bytes to Gemini using a prompt that directly requests Hungarian SRT.
- `pipeline/ears.py` extracts audio and requests SRT with tone tags.
- `pipeline/brains.py` uses DeepSeek first and Gemini as fallback and currently uses English as a translation pivot.
- `pipeline/voice.py` synthesizes per-SRT-entry audio, caches mainly by modification time, trims leading samples by threshold, and accelerates overlong clips with FFmpeg.
- `pipeline/fcpxml.py` generates FCPXML 1.12 from SRT and WAV inputs.
- `webui/` provides a partially implemented Streamlit interface.
- `prompts/` contains inherited prompts, including a video-analysis prompt specialized for the original hexagon demonstration.

### Current-state limitations

- SRT conflates semantic meaning, narration wording, and timing.
- Evidence, uncertainty, terminology decisions, teaching intent, review state, and safe timing flexibility are not represented.
- Provider configuration is hardcoded and partially inconsistent with authentication behavior.
- Translation, TTS segmentation, caching, resume, validation, and UI limitations are tracked in [TODO.md](../TODO.md).

## 2. Target architecture

Status: target design informed by controlled mute-video tests; not yet implemented as the production pipeline. The speech-containing branch and multilingual localization remain untested.

```text
media ingest and probe
        |
        v
speech-usefulness classification
        |
        +-----------------------+
        |                       |
        v                       v
speech evidence timeline   visual evidence timeline
        |                       |
        +-----------+-----------+
                    v
        structured semantic project state
        meaning + evidence + terminology + review
                    |
                    v
          direct per-language localization
                    |
                    v
       narration planning with flexible windows
                    |
                    v
       coherent TTS generation and evaluation
                    |
                    v
       placement, mix, normalization, validation
                    |
                    v
        derived SRT / WAV / preview / FCPXML
```

### Canonical project state

The target source of truth is a structured, versioned project document. At minimum it must represent:

- source media identity, hash, duration, and probe metadata;
- spoken/source meaning and traceable source evidence;
- visible actions, objects, tools, materials, spatial references, and timestamps;
- evidence class: directly observed, reasonable interpretation, uncertain inference, or unsupported assumption;
- semantic instructional units and teaching intent;
- importance: `required`, `useful`, or `optional`;
- approved/prohibited terminology and pronunciation hints;
- tone, emphasis, rhythm, pauses, and speaker identity;
- hard and soft timing bounds plus safe placement flexibility;
- direct target-language localizations;
- provider/model/voice configuration and input hashes;
- raw and final audio duration, processing, placement, and speed adjustment;
- confidence, warnings, and human-review/lock state.

SRT, WAV, mixed audio, preview video, and FCPXML are generated views of this state, not competing sources of truth.

### Mute-video workflow

The authoritative sample tested evidence-based analysis and separate narration review. The production two-pass workflow remains planned:

1. Extract an evidence-first factual visual timeline.
2. Review uncertainty and unsupported assumptions.
3. Generate instructional commentary from approved semantic units using a selected domain profile.
4. Review/lock Hungarian/source meaning and terminology.
5. Continue to localization, narration planning, and TTS.

Visual understanding and final subtitle authoring must not be collapsed into one opaque step.

### Localization and narration

- Localize independently from approved Hungarian/source meaning into EN, DE, ES, and FR.
- English may be a reviewer reference but is not a pivot source for the other languages.
- Plan complete sentences or short coherent utterance groups against flexible visual windows before synthesis.
- Preserve provider output and derive speech-aligned captions from final audio.
- Apply the natural-speech fitting policy in [AGENTS.md](../AGENTS.md) and the decision record in [DECISIONS.md](DECISIONS.md).

### Artifact and run model

Every controlled or production run should have a manifest containing input/configuration hashes, exact provider settings, usage/cost where available, raw and final artifacts, timing, processing, warnings, and validation results. Resume and cache decisions should be derived from this manifest and filesystem state.

The authoritative source media must remain immutable. Preview MP4 files are review artifacts and must never silently replace production source media.

## 3. Future Hungarian-speech workflow

Status: planned; not implemented or validated with a suitable speech-containing source video.

Hungarian speech will be the primary semantic source. Vision will provide complementary evidence for visible actions, tools, materials, components, and spatial references.

The fusion stage should:

- align word/segment timestamps with visible actions;
- resolve references such as “this,” “here,” and “the other side”;
- flag visually supported ASR/terminology corrections;
- keep corrections and additions traceable and individually reviewable;
- distinguish spoken facts from visually inferred additions.

Two explicit output modes are planned:

### Faithful dubbing

Preserve original meaning, omissions, emphasis, tone, rhythm, pauses, and teaching style. Use vision only for disambiguation and terminology correction.

### Enhanced instructional localization

Preserve essential meaning while allowing concise, visually supported teaching additions. Mark every addition so it can be reviewed or disabled.

Voice preservation or cloning is a future optional layer. It requires explicit consent, provider/license review, native-language evaluation, and separate cost approval.
