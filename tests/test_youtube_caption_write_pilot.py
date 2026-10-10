import json
import tempfile
import unittest
from pathlib import Path
from tools.youtube_caption_write_pilot import pilot


class Response:
    def __init__(self, data=None, content=b'', status=200):
        self.data, self.content, self.status_code = data, content, status

    def json(self):
        return self.data


class Session:
    def __init__(self, responses):
        self.responses, self.calls = iter(responses), []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        response = next(self.responses)
        return response(kwargs) if callable(response) else response


class WritePilotTests(unittest.TestCase):
    def prepare(self, tail, created_id='new'):
        def inserted(kwargs):
            # Inspect metadata of the actual request, including the draft guard.
            body = kwargs['data'].split(b'\r\n\r\n', 1)[1].split(b'\r\n--', 1)[0]
            snippet = json.loads(body)['snippet']
            self.assertTrue(snippet['isDraft'])
            return Response({'id': created_id, 'snippet': snippet})
        return Session([
            Response({'items': [{'snippet': {'channelId': 'channel'}}]}),
            Response({'items': [{'id': 'existing', 'snippet': {}}]}), inserted, *tail])

    def invoke(self, session, folder):
        return pilot(session, '4sXe2lpaPqA', 'channel', b'original', b'modified', folder)

    def test_roundtrip_changes_only_new_draft_then_removes_it(self):
        session = self.prepare([
            Response(content=b'original'),
            Response({'id': 'new', 'snippet': {'isDraft': True}}),
            Response(content=b'modified'), Response(status=204),
            Response({'items': [{'id': 'existing'}]})])
        with tempfile.TemporaryDirectory(dir='output') as temp:
            result = self.invoke(session, Path(temp) / 'pilot')
        self.assertTrue(result['complete'])
        self.assertEqual(result['quota_units_attempted'], 1401)
        self.assertEqual(len(session.calls), 8)
        self.assertEqual(session.calls[-2][2]['params']['id'], 'new')
        self.assertEqual(session.calls[4][0], 'PUT')
        self.assertIn(b'"isDraft": true', session.calls[4][2]['data'])

    def test_failed_download_cleans_up_only_owned_draft_without_retry(self):
        session = self.prepare([Response(status=400), Response(status=204),
                                Response({'items': [{'id': 'existing'}]})])
        with tempfile.TemporaryDirectory(dir='output') as temp:
            folder = Path(temp) / 'pilot'
            with self.assertRaises(RuntimeError):
                self.invoke(session, folder)
            manifest = json.loads((folder / 'manifest.json').read_text())
        self.assertTrue(manifest['deleted'])
        self.assertTrue(manifest['baseline_ids_preserved'])
        self.assertFalse(manifest['complete'])
        self.assertEqual(len(session.calls), 6)

    def test_existing_caption_id_never_updated_or_deleted(self):
        session = self.prepare([], created_id='existing')
        with tempfile.TemporaryDirectory(dir='output') as temp:
            with self.assertRaises(ValueError):
                self.invoke(session, Path(temp) / 'pilot')
        self.assertEqual([x[0] for x in session.calls], ['GET', 'GET', 'POST'])

    def test_wrong_channel_prevents_any_write(self):
        session = Session([Response({'items': [{'snippet': {'channelId': 'wrong'}}]})])
        with tempfile.TemporaryDirectory(dir='output') as temp:
            with self.assertRaises(ValueError):
                self.invoke(session, Path(temp) / 'pilot')
        self.assertEqual(len(session.calls), 1)


if __name__ == '__main__':
    unittest.main()
