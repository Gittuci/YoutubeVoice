# Agent Instructions

Read these files before changing the repository:

1. `docs/ARCHITECTURE.md` — current implementation versus target architecture.
2. `docs/DECISIONS.md` — accepted product and architectural decisions.
3. `TODO.md` — the only authoritative engineering backlog.
4. `docs/CODEX_HANDOFF.md` — current investigation state, test results, and continuation details.

`.kilo/plans/` is historical material. Do not treat it as active requirements or a current TODO list. Do not delete `.kilo`, legacy code, prompts, or historical artifacts unless explicitly requested.

## Documentation authority

`README.md` and `USER_MANUAL.md` are inherited documentation for the legacy/Kilo-era implementation. They are retained as reference for how the current inherited code was originally intended to work, but they contain known stale or inaccurate information and must not override the authoritative project documentation above.

When documentation conflicts, use this order of authority:

1. `docs/DECISIONS.md` — accepted product and architectural decisions.
2. `docs/ARCHITECTURE.md` — current implementation boundaries and validated target architecture.
3. `TODO.md` — current engineering priorities and unfinished work.
4. `docs/CODEX_HANDOFF.md` — current experiment/session state and recent test results.
5. `README.md` and `USER_MANUAL.md` — inherited implementation reference only.
6. `.kilo/plans/` — historical context only.

Do not update `README.md` or `USER_MANUAL.md` to describe planned architecture as if it were already implemented. They should be comprehensively rewritten only when the production pipeline has been migrated to the validated architecture.

## Working rules

- Preserve `output/video.mp4` as the sole authoritative test input. Verify its SHA-256 against `docs/CODEX_HANDOFF.md` before controlled media tests. Never overwrite it.
- Treat the structured semantic project state described in `docs/ARCHITECTURE.md` as the target source of truth. SRT, WAV, preview video, and FCPXML are derived exports.
- Do not describe target architecture as implemented. Keep inherited/current behavior and planned behavior visibly separate.
- Keep each repository isolated in its project-local `.venv`. Do not install Python packages globally or modify system GPU/CUDA components without explicit approval.
- Never print, log, document, or commit `.env` values, private keys, access tokens, or `vertex-key.json` contents.
- Preserve existing user work. Avoid broad cleanup, destructive Git commands, and unrelated refactors.

## Provider calls

Before every live provider call, state and obtain approval for:

- provider and exact model;
- credential/profile and project/location where applicable;
- expected paid/free quota and estimated cost;
- input and expected artifacts;
- number and purpose of calls.

Store controlled-test results under a new `output/test_runs/YYYY-MM-DD_HHMMSS/` directory. Preserve prompts/configuration, hashes, usage/cost metadata, raw outputs where appropriate, final outputs, durations, placement, and processing history. Never silently retry a paid call when that could duplicate billing.

## Natural-speech policy

Prioritize, in order: natural speech, correct instructional meaning, professional terminology, natural target-language phrasing, then timing fit.

Do not force narration into arbitrary subtitle windows. First shorten or rewrite, improve segmentation, shift within safe visual bounds, redistribute across nearby actions, or regenerate. Use pitch-preserving speed adjustment only as a last resort; approximately `1.03x` is the default ceiling, and anything above `1.05x` requires an explicit warning and review. Persist raw and final duration and the applied speed.

## Testing expectations

- Separate directly visible/spoken facts, reasonable interpretation, uncertainty, and unsupported assumptions.
- Validate every timestamp against source-media duration and every referenced media path before export.
- Keep raw media and provider output recoverable; generate normalized, split, mixed, subtitle, and FCPXML artifacts non-destructively.
- Add offline tests for new parsing, validation, hashing, manifest, timing, and export behavior.
- For language quality or voice selection, require native-listener review; objective audio metrics are not a substitute.
- Localize each target directly from approved Hungarian/source meaning. Do not use English as a pivot for German, Spanish, or French.
