import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from monitor import IssueReporter, database, deliver, publish, remember, telegram
from preview import PreviewFailure, latest_post, refresh_preview, write_preview


class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'public' / 'latest.json'

    def tearDown(self):
        self.temp.cleanup()

    def test_latest_ignores_service_foreign_and_pinned_posts(self):
        content = '''<div data-post="korea_vancouver/10"><div class="tgme_widget_message_text js-message_text">공지</div></div>
        <div data-post="korea_vancouver/99"><div>Channel created</div></div>
        <div data-post="other_channel/123"><div class="tgme_widget_message_text">다른 채널</div></div>
        <div data-post="korea_vancouver/2"><div class="tgme_widget_message_text">고정 글</div></div>'''
        self.assertEqual(latest_post(content), 10)
        with self.assertRaises(PreviewFailure):
            latest_post('<html>unavailable</html>')

    def test_metadata_is_public_only_atomic_and_validated(self):
        write_preview(self.path, 52)
        self.assertEqual(json.loads(self.path.read_text()), {
            'post': 'korea_vancouver/52', 'url': 'https://t.me/korea_vancouver/52'})
        self.assertFalse(self.path.with_suffix('.tmp').exists())
        for value in [0, -1, True, '53', 2**53]:
            with self.assertRaises(PreviewFailure):
                write_preview(self.path, value)
            self.assertEqual(json.loads(self.path.read_text())['post'], 'korea_vancouver/52')
        with patch('preview.Path.replace', side_effect=OSError()):
            with self.assertRaises(PreviewFailure):
                write_preview(self.path, 53)
        self.assertFalse(self.path.with_suffix('.tmp').exists())
        self.assertEqual(json.loads(self.path.read_text())['post'], 'korea_vancouver/52')

    @patch('preview.urllib.request.urlopen')
    def test_refresh_deleted_latest_and_parse_failure_keeps_previous(self, open_url):
        write_preview(self.path, 53)
        response = open_url.return_value.__enter__.return_value
        response.read.return_value = b'<div data-post="korea_vancouver/52"><div class="tgme_widget_message_text">post</div></div>'
        refresh_preview(self.path)
        self.assertEqual(json.loads(self.path.read_text())['post'], 'korea_vancouver/52')
        response.read.return_value = b'<html>unavailable</html>'
        with self.assertRaises(PreviewFailure):
            refresh_preview(self.path)
        self.assertEqual(json.loads(self.path.read_text())['post'], 'korea_vancouver/52')

    @patch('monitor.urllib.request.urlopen')
    def test_telegram_returns_successful_message_id(self, open_url):
        response = open_url.return_value.__enter__.return_value
        response.read.return_value = b'{"ok":true,"result":{"message_id":53}}'
        self.assertEqual(telegram('fake-test-token', '@korea_vancouver', 'text'), 53)

    @patch('monitor.telegram', return_value=53)
    def test_successful_send_updates_preview(self, send):
        publish('fake-test-token', '@korea_vancouver', 'text', self.path)
        self.assertEqual(json.loads(self.path.read_text())['post'], 'korea_vancouver/53')
        send.assert_called_once()

    @patch('monitor.time.sleep')
    @patch('monitor.write_preview', side_effect=OSError('fake failure'))
    @patch('monitor.telegram', return_value=53)
    def test_preview_failure_does_not_resend_successful_channel_post(self, send, write, sleep):
        conn = database(Path(self.temp.name) / 'state.sqlite3')
        try:
            board = {'id': 'm_4585', 'name': '공지사항'}
            post = lambda i: {'url': f'https://example.com/{i}', 'title': 'title', 'date': '2026-11-05'}
            remember(conn, board, [post(1)])
            remember(conn, board, [post(2)])
            private = []
            reporter = IssueReporter(conn, private.append)
            public = lambda text: publish('fake-test-token', '@korea_vancouver', text, self.path, reporter)
            detail = lambda url, title: {'date': '2026-11-05', 'summary': 'summary', 'fingerprint': 'abc'}
            self.assertFalse(deliver(conn, public, detail, reporter))
            self.assertFalse(deliver(conn, public, detail, reporter))
            self.assertEqual(send.call_count, 1)
            self.assertEqual(conn.execute('SELECT count(*) FROM posts WHERE sent=0').fetchone()[0], 0)
            self.assertEqual(len(private), 1)
            self.assertIn('소개페이지', private[0])
        finally:
            conn.close()


if __name__ == '__main__':
    unittest.main()
