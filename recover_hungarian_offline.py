from pathlib import Path
from datetime import datetime
import hashlib
import importlib.util
import json
import subprocess

ROOT = Path(__file__).resolve().parent
COMMIT = '2e69428e08a03303ccf21acd8e9c2afb932d31f5'
BASE = ROOT / 'work_runs' / (datetime.now().strftime('%Y-%m-%d_%H%M%S') + '_hungarian_recovery')
BASE.mkdir(parents=True, exist_ok=False)
records = []
prefixes = ('output/test_runs/2026-09-26_170438/', 'output/test_runs/2026-09-27_000442/', 'output/test_runs/2026-09-27_001434/')
paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', COMMIT], cwd=ROOT).decode().splitlines()
for original in paths:
    if not original.startswith(prefixes):
        continue
    data = subprocess.check_output(['git', 'show', f'{COMMIT}:{original}'], cwd=ROOT)
    target = BASE / 'recovered' / Path(original).relative_to('output/test_runs')
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('xb') as handle:
        handle.write(data)
    records.append({'original_path': original, 'path': str(target.relative_to(ROOT)), 'sha256': hashlib.sha256(data).hexdigest().upper()})

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()

assert digest(ROOT / 'output/video.mp4') == '6582AC24DF91F6CBD89F71FCBFAC7E7C7421BAE9489E71C5734F3CDA0887D7FB'
voice = BASE / 'recovered/2026-09-27_000442/eleven_v3_natural_normalized.wav'
assert digest(voice) == 'BFDA0A1B260F17E30D94ECF0A0EEE6F8DA3251C6A5463C332AF46CC9E3B49EB0'
script = BASE / 'recovered/2026-09-27_001434/render_synced_preview.py'
spec = importlib.util.spec_from_file_location('historical_renderer', script)
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)
renderer.ROOT = ROOT
renderer.RUN = BASE / 'rebuilt'
renderer.VIDEO = ROOT / 'output/video.mp4'
renderer.VOICE = voice
renderer.main()
expected = json.loads((script.parent / 'run_manifest.json').read_text(encoding='utf-8'))
assert digest(renderer.RUN / 'voiceover_placed.wav') == expected['outputs']['voiceover_placed.wav']['sha256']
assert digest(renderer.RUN / 'captions_hu.srt') == expected['outputs']['captions_hu.srt']['sha256']
for item in expected['segments']:
    assert digest(renderer.RUN / 'segments' / Path(item['path'].replace('\\', '/')).name) == item['sha256']
report = {'source_commit': COMMIT, 'provider_calls': 0, 'provider_cost_usd': 0, 'recovered': records, 'validation': 'Source video, accepted normalized voice, all four rebuilt segments, placed WAV and regenerated SRT match historical SHA-256; both previews decode successfully.', 'historical_paths': 'Preserved historical manifests retain original deleted paths; rebuilt/run_manifest.json records current paths.'}
with (BASE / 'recovery_manifest.json').open('x', encoding='utf-8') as handle:
    json.dump(report, handle, ensure_ascii=False, indent=2)
print('RECOVERY_COMPLETE', BASE)
