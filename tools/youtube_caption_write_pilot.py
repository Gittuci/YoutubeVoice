"""Bounded draft-only caption insert/update/download/delete integration pilot."""
import argparse
import hashlib
import json
import uuid
from pathlib import Path
from urllib.parse import quote

try:
    from .youtube_caption_audit import BASE, SCOPE, VIDEO_ID
except ImportError:
    from youtube_caption_audit import BASE, SCOPE, VIDEO_ID


def multipart(metadata, media):
    boundary = 'youtubevoice_' + uuid.uuid4().hex
    body = (('--' + boundary + '\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n').encode()
            + json.dumps(metadata).encode() + b'\r\n'
            + ('--' + boundary + '\r\nContent-Type: application/octet-stream\r\n\r\n').encode()
            + media + ('\r\n--' + boundary + '--\r\n').encode())
    return body, {'Content-Type': 'multipart/related; boundary=' + boundary}


def pilot(session, video, channel, original, modified, output):
    if not VIDEO_ID.fullmatch(video) or original == modified:
        raise ValueError('Invalid video or identical test inputs')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    name = 'YoutubeVoice API draft test ' + output.parent.name
    record = {'video_id': video, 'channel_id': channel, 'name': name,
              'mode': 'draft_only', 'calls': [], 'created_id': None,
              'deleted': False, 'complete': False}
    baseline = set()
    owned_id = None

    def persist():
        record['quota_units_attempted'] = sum(x['units'] for x in record['calls'])
        temp = output / 'manifest.pending.json'
        temp.write_text(json.dumps(record, indent=2), encoding='utf-8')
        temp.replace(output / 'manifest.json')

    def request(method, resource, units, upload=False, **kwargs):
        call = {'method': method, 'resource': resource, 'units': units, 'status': 'attempted'}
        record['calls'].append(call)
        persist()
        base = 'https://www.googleapis.com/upload/youtube/v3/' if upload else BASE
        response = session.request(method, base + resource, timeout=60,
                                   allow_redirects=False, **kwargs)
        call['http_status'] = response.status_code
        persist()
        if response.status_code not in (200, 204):
            raise RuntimeError('HTTP %s' % response.status_code)
        call['status'] = 'success'
        persist()
        return response

    def caption_ids(response):
        tracks = response.json()
        return {x['id'] for x in tracks.get('items', [])}, tracks

    def download(caption_id, expected, filename):
        data = request('GET', 'captions/' + quote(caption_id, safe=''), 200).content
        (output / filename).write_bytes(data)
        if data != expected:
            raise ValueError('Downloaded test content differs')
        record[filename] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
        persist()

    try:
        items = request('GET', 'videos', 1,
                        params={'part': 'snippet', 'id': video}).json().get('items', [])
        if len(items) != 1 or items[0]['snippet']['channelId'] != channel:
            raise ValueError('Video/channel mismatch')
        baseline, inventory = caption_ids(request('GET', 'captions', 50,
                                                  params={'part': 'snippet', 'videoId': video}))
        (output / 'inventory_before.json').write_text(json.dumps(inventory, indent=2), encoding='utf-8')
        if any(x['snippet'].get('name') == name for x in inventory.get('items', [])):
            raise ValueError('Test name already exists')
        metadata = {'snippet': {'videoId': video, 'language': 'en-US',
                                'name': name, 'isDraft': True}}
        body, headers = multipart(metadata, original)
        created = request('POST', 'captions', 400, upload=True,
                          params={'part': 'snippet', 'uploadType': 'multipart'},
                          headers=headers, data=body).json()
        (output / 'insert_response.json').write_text(json.dumps(created, indent=2), encoding='utf-8')
        record['created_id'] = created.get('id')
        snippet = created.get('snippet', {})
        if (not record['created_id'] or record['created_id'] in baseline
                or snippet.get('videoId') != video or snippet.get('name') != name
                or snippet.get('isDraft') is not True):
            raise ValueError('Insert identity/draft verification failed; no deletion attempted')
        owned_id = record['created_id']
        persist()
        download(owned_id, original, 'download_original.srt')
        metadata = {'id': owned_id, 'snippet': {'isDraft': True}}
        body, headers = multipart(metadata, modified)
        updated = request('PUT', 'captions', 450, upload=True,
                          params={'part': 'snippet', 'uploadType': 'multipart'},
                          headers=headers, data=body).json()
        (output / 'update_response.json').write_text(json.dumps(updated, indent=2), encoding='utf-8')
        if updated.get('id') != owned_id or updated.get('snippet', {}).get('isDraft') is not True:
            raise ValueError('Update identity/draft verification failed')
        download(owned_id, modified, 'download_modified.srt')
        record['content_roundtrip_verified'] = True
    finally:
        # Only delete the new, verified draft created by this very run.
        if owned_id is not None:
            request('DELETE', 'captions', 50, params={'id': owned_id})
            record['deleted'] = True
            persist()
            final_ids, final_inventory = caption_ids(request('GET', 'captions', 50,
                                                            params={'part': 'snippet', 'videoId': video}))
            (output / 'inventory_after.json').write_text(json.dumps(final_inventory, indent=2), encoding='utf-8')
            record['baseline_ids_preserved'] = final_ids == baseline
            record['complete'] = (record.get('content_roundtrip_verified', False)
                                  and record['baseline_ids_preserved'])
        persist()
    if not record['complete']:
        raise ValueError('Pilot incomplete')
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--token', type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding='utf-8'))
    files = []
    for key in ('original', 'modified'):
        item = plan[key]
        data = Path(item['path']).read_bytes()
        if hashlib.sha256(data).hexdigest() != item['sha256']:
            raise ValueError('Prepared input hash mismatch')
        files.append(data)
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import AuthorizedSession, Request
    credentials = Credentials.from_authorized_user_file(str(args.token))
    if not credentials.has_scopes([SCOPE]):
        raise ValueError('Missing approved scope')
    if not credentials.valid:
        credentials.refresh(Request())
    result = pilot(AuthorizedSession(credentials, max_refresh_attempts=0),
                   plan['video'], plan['channel'], *files, plan['output'])
    print('Draft upload/update/download/delete verified; original captions preserved. Quota units:',
          result['quota_units_attempted'])


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('Pilot stopped (%s); inspect local manifest. No automatic retry.' % type(error).__name__)
        raise SystemExit(1)
