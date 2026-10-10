import json
import tempfile
import unittest
from pathlib import Path
from tools.youtube_caption_audit import audit


class Response:
    def __init__(self, data=None, content=b'', status=200):
        self.data, self.content, self.status_code = data, content, status

    def json(self):
        return self.data


class Session:
    def __init__(self, responses):
        self.responses, self.calls = iter(responses), []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return next(self.responses)


class AuditTests(unittest.TestCase):
    def run_case(self, responses, **kwargs):
        session = Session(responses)
        with tempfile.TemporaryDirectory(dir='output') as temp:
            destination = Path(temp) / 'audit'
            try:
                audit(session, '4sXe2lpaPqA', 'channel', destination, **kwargs)
            finally:
                manifest = json.loads((destination / 'audit_manifest.json').read_text())
                self.manifest = manifest
                self.calls = session.calls
        return manifest

    def test_backup_preserves_audio_type_and_exact_bytes(self):
        video = Response({'items': [{'snippet': {'channelId': 'channel'}}]})
        track = {'id': '../unsafe/id', 'snippet': {'videoId': '4sXe2lpaPqA',
                                                 'audioTrackType': 'descriptive'}}
        result = self.run_case([video, Response({'items': [track]}), Response(content=b'caption')])
        self.assertTrue(result['complete'])
        self.assertEqual(result['quota_units_attempted'], 251)
        self.assertEqual(result['captions'][0]['snippet']['audioTrackType'], 'descriptive')
        self.assertTrue(self.calls[-1][0].endswith('..%2Funsafe%2Fid'))
        self.assertEqual(self.calls[-1][1]['params'], {})

    def test_wrong_channel_stops_before_caption_access(self):
        with self.assertRaises(ValueError):
            self.run_case([Response({'items': [{'snippet': {'channelId': 'wrong'}}]})])
        self.assertEqual(len(self.calls), 1)
        self.assertFalse(self.manifest['complete'])

    def test_quota_bound_stops_before_downloads(self):
        with self.assertRaises(ValueError):
            self.run_case([Response({'items': [{'snippet': {'channelId': 'channel'}}]}),
                           Response({'items': [{}] * 7})])
        self.assertEqual(len(self.calls), 2)

    def test_failure_has_no_retry_and_preserves_manifest(self):
        with self.assertRaises(RuntimeError):
            self.run_case([Response(status=403)])
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.manifest['calls'][0]['http_status'], 403)


if __name__ == '__main__':
    unittest.main()
