# YouTube caption API pilot

Status: read-only backup and bounded draft caption upload/update/delete utilities
validated live on the pilot video. All six production captions were preserved.
Batch publishing and public-API audio management are not implemented.
This is separate from the inherited media pipeline and is not a batch publisher.

Pilot target: video `4sXe2lpaPqA`, expected channel
`UCzUghL5YKVSkosyFuQ6a2pw`. The user approved OAuth setup in
`foltvilag-enterprise-audio`, using `foltvilag@gmail.com`, and at most eight
read requests: one videos.list, one captions.list, up to six captions.download.
Quota maximum: 1 + 50 + 6*200 = 1251 units; estimated monetary charge USD 0.
No TTS/model calls, upload, deletion or subtitle replacement is part of this audit.

The documented caption methods require `youtube.force-ssl`, even for reading.
This scope grants broader capabilities than the utility uses. Consent must be
reviewed by the user. Do not use Vertex service-account credentials or extract
Studio browser tokens. The Cloud project now has the approved Desktop client
YoutubeVoice Local Desktop and enabled YouTube Data API v3; the user completed
the branding policy agreement and explicitly approved API activation/terms.

## Local setup and execution

Install optional dependencies only in `.venv` using `requirements-youtube.txt`.
Configure an External, Testing OAuth application and add the channel-owning
account as a test user. Enable YouTube Data API v3 if needed. Create a Desktop
OAuth client; save its JSON to `.local/youtube/client.json`. Store the authorized
user token at `.local/youtube/token.json`. That directory is ignored by Git;
neither file belongs in output manifests, logs, or documentation. The local
configuration/token now exist; do not rerun authorization or overwrite them.

From the repository root, after the approved user sign-in:

```powershell
.\.venv\Scripts\python.exe tools/youtube_caption_audit.py auth --client .local/youtube/client.json --token .local/youtube/token.json
.\.venv\Scripts\python.exe tools/youtube_caption_audit.py audit --token .local/youtube/token.json --video 4sXe2lpaPqA --channel UCzUghL5YKVSkosyFuQ6a2pw --output output/test_runs/NEW_TIMESTAMP/youtube_api_audit --max-tracks 6
```

Replace NEW_TIMESTAMP with the actual run timestamp. The audit requires a fresh
destination and never overwrites a previous backup. It verifies the expected
channel, preserves caption metadata including audioTrackType, downloads source
format bytes without translation, hashes each successful backup and writes a
manifest even when a request fails. It stops on the first failure without
automatic API retries. A partially completed run is not a complete backup.
No audio upload API is implemented and no video/audio files are downloaded.

Four offline tests cover channel mismatch, track-count bound, HTTP failure/no
retry, and caption backup metadata/path escaping. Run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Live result

Run: `output/test_runs/2026-10-10_235135/youtube_api_audit/`.
Eight successful GET requests, 1251 quota units, no retries or remote writes.
All six caption tracks have status serving and audioTrackType unknown, including
Hungarian. All six downloaded original-format files are byte-identical to the
previously uploaded SRTs. `comparison.json` records this comparison;
`readable_srt/` contains named SRT copies and `audit_manifest.json` records hashes.
There is no caption-content difference to repair by re-uploading.

The Hungarian descriptive-audio caption chooser issue is still undiagnosed;
the API does not confirm the hypothesized primary/descriptive association.
The draft caption-update test below succeeded; player behavior remains unresolved.
No public alternate-audio upload API has been identified in the official catalog.

The OAuth app remains External/Testing. Google documents a seven-day refresh
token lifetime for this configuration with YouTube scopes. Production status and
app verification requirements must be resolved before unattended long-term use;
do not silently publish the app or broaden authorization.
https://developers.google.com/identity/protocols/oauth2#expiration

Official references:
- https://developers.google.com/youtube/v3/docs/captions/list
- https://developers.google.com/youtube/v3/docs/captions/download
- https://developers.google.com/youtube/v3/docs/captions
- https://developers.google.com/youtube/v3/guides/authentication

## Completed draft-only write pilot (2026-10-11)

The user requested upload/update/deletion testing via API and suggested relabeling
the silent primary track to free the ordinary Hungarian audio slot. Studio's
Video details > Show more > Video language selector visibly offers Not applicable.
The separately approved Not applicable experiment is recorded below.
No public alternate-audio upload/delete endpoint has been identified.

Prepared input/configuration: output/test_runs/2026-10-11_000405/plan.json.
tools/youtube_caption_write_pilot.py creates an explicitly named en-US draft,
downloads it, updates it with a changed first-cue marker, downloads/verifies the
new bytes, deletes only the owned test draft and compares the remaining caption
IDs to the initial inventory. Existing caption IDs cannot be update/delete targets.
Original source-format SRT and modified copy are hashed and preserved; timestamps
are unchanged. Requests/responses, downloads and failure/cleanup state persist.

Eight planned calls: videos.list (1), captions.list (50), insert (400), download
(200), update (450), download (200), delete (50), final list (50): 1401 quota
units, estimated USD 0. No automatic retry. A verified draft is cleaned up on
failure within the same approved scope. The eight total offline tests pass,
including baseline-ID collision protection and cleanup after a failed download.
The user explicitly approved the eight-request batch. All eight calls succeeded:
both downloads matched their respective inputs byte-for-byte, the new draft was
deleted, and the final six caption IDs exactly matched the baseline. Evidence:
`output/test_runs/2026-10-11_000405/write_pilot/manifest.json` and accompanying
responses/downloads. No retry or production caption mutation occurred.
This draft test does not publish subtitles or fix player behavior.

## Completed Studio language experiment

With separate explicit approval, changed Video language from Hungarian to Not
applicable and saved. The Languages page then showed only Set language / Confirm,
with no translation table or ordinary Hungarian audio upload control. Restored
Hungarian and saved as agreed. The five foreign audio/subtitle pairs again showed
Published. Hungarian details confirmed Original audio Published, Manual
descriptive audio Published and Manual subtitles Published. No asset was deleted
or uploaded. Not applicable therefore did not solve the ordinary-Hungarian-slot
problem in this observed UI. A rare-language relabel was not tested.

Evidence in the same run: `studio_language_experiment.json`,
`studio_not_applicable_no_language.png`, `studio_hungarian_restored_details.png`.
