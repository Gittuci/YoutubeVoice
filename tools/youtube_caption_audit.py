"""Read-only YouTube caption inventory/backup pilot; never uploads or deletes.

Credentials stay in an ignored local directory, outside test artifacts.
Live calls must be approved under AGENTS.md before running auth or audit.
"""
import argparse
import hashlib
import json
import re
import webbrowser
from pathlib import Path
from urllib.parse import quote

SCOPE = 'https://www.googleapis.com/auth/youtube.force-ssl'
BASE = 'https://www.googleapis.com/youtube/v3/'
VIDEO_ID = re.compile(r'[A-Za-z0-9_-]{11}\Z')


def save_json(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def audit(session, video_id, expected_channel, destination, max_tracks=6):
    """Bounded GET-only requests. Stop on first error, preserving completed work."""
    if not VIDEO_ID.fullmatch(video_id):
        raise ValueError('Invalid video ID')
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    record = {'video_id': video_id, 'expected_channel': expected_channel,
              'mode': 'read_only', 'calls': [], 'captions': [], 'complete': False}

    def get(resource, params, units):
        entry = {'resource': resource, 'quota_units': units, 'status': 'attempted'}
        record['calls'].append(entry)
        response = session.get(BASE + resource, params=params, timeout=60,
                               allow_redirects=False)
        entry['http_status'] = response.status_code
        if response.status_code != 200:
            # Do not print raw responses, request headers or credential-bearing URLs.
            raise RuntimeError('YouTube request failed (HTTP %s)' % response.status_code)
        entry['status'] = 'success'
        return response

    try:
        videos = get('videos', {'part': 'snippet,contentDetails', 'id': video_id}, 1).json()
        save_json(destination / 'video.json', videos)
        items = videos.get('items', [])
        if len(items) != 1 or items[0]['snippet']['channelId'] != expected_channel:
            raise ValueError('Video/channel mismatch; no captions requested')
        captions = get('captions', {'part': 'snippet', 'videoId': video_id}, 50).json()
        save_json(destination / 'captions_inventory.json', captions)
        tracks = captions.get('items', [])
        if len(tracks) > max_tracks:
            raise ValueError('Track count exceeds approved download limit')
        for index, track in enumerate(tracks, 1):
            if track['snippet']['videoId'] != video_id:
                raise ValueError('Caption/video mismatch')
            caption_id = track['id']
            # Preserve the source format, without translation or conversion.
            content = get('captions/' + quote(caption_id, safe=''), {}, 200).content
            if not content:
                raise ValueError('Empty caption download')
            filename = 'caption_%02d.original' % index
            with (destination / filename).open('xb') as stream:
                stream.write(content)
            record['captions'].append({
                'id': caption_id, 'snippet': track['snippet'], 'file': filename,
                'sha256': hashlib.sha256(content).hexdigest(), 'bytes': len(content)})
        record['complete'] = True
    finally:
        record['quota_units_attempted'] = sum(c['quota_units'] for c in record['calls'])
        save_json(destination / 'audit_manifest.json', record)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    auth = sub.add_parser('auth')
    auth.add_argument('--client', type=Path, required=True)
    auth.add_argument('--token', type=Path, required=True)
    auth.add_argument('--auth-url-file', type=Path)
    run = sub.add_parser('audit')
    run.add_argument('--token', type=Path, required=True)
    run.add_argument('--video', required=True)
    run.add_argument('--channel', required=True)
    run.add_argument('--output', type=Path, required=True)
    run.add_argument('--max-tracks', type=int, default=6)
    args = parser.parse_args()
    if args.command == 'auth':
        from google_auth_oauthlib.flow import InstalledAppFlow
        if args.token.exists():
            raise ValueError('Token already exists; refusing to overwrite')
        flow = InstalledAppFlow.from_client_secrets_file(
            str(args.client), [SCOPE], autogenerate_code_verifier=True)
        browser_name = None
        if args.auth_url_file:
            class LocalUrlSink:
                def open(self, url, **kwargs):
                    # Hand the official authorization URL to the controlled browser.
                    # It contains OAuth state; keep it out of console/run manifests.
                    with args.auth_url_file.open('x', encoding='utf-8') as stream:
                        stream.write(url)
                    return True
            browser_name = 'youtubevoice-local-url'
            webbrowser.register(browser_name, None, LocalUrlSink())
        credentials = flow.run_local_server(host='127.0.0.1', port=0,
                                           authorization_prompt_message='',
                                           browser=browser_name, timeout_seconds=600,
                                           success_message='Authorization complete. Close this tab.')
        args.token.parent.mkdir(parents=True, exist_ok=True)
        with args.token.open('x', encoding='utf-8') as stream:
            stream.write(credentials.to_json())
        print('Authorization saved locally; no YouTube data calls made.')
    else:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import AuthorizedSession, Request
        credentials = Credentials.from_authorized_user_file(str(args.token))
        if not credentials.has_scopes([SCOPE]):
            raise ValueError('Missing approved YouTube scope')
        if not credentials.valid:
            credentials.refresh(Request())
        session = AuthorizedSession(credentials, max_refresh_attempts=0)
        result = audit(session, args.video, args.channel, args.output, args.max_tracks)
        print('Backup complete: %s captions, %s quota units.' % (
            len(result['captions']), result['quota_units_attempted']))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Authentication exceptions may contain sensitive responses. Never print them.
        print('Stopped safely (%s). No automatic retry; inspect local manifest.' % type(error).__name__)
        raise SystemExit(1)
