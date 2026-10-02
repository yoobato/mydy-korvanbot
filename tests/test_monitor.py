import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from monitor import BoardParser, cycle, database, deliver, parse_rss, remember

BOARD = {"id": "m_4585", "name": "공지사항"}


def post(seq, title="새 글"):
    return {"url": f"https://www.mofa.go.kr/ca-vancouver-ko/brd/m_4585/view.do?seq={seq}",
            "title": title, "date": "2026-10-01"}


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.conn = database(Path(self.temp.name) / "state.sqlite3")

    def tearDown(self):
        self.conn.close()
        self.temp.cleanup()

    def test_actual_site_onclick_and_pinned_row(self):
        parser = BoardParser("m_4585")
        parser.feed('''<table><tr><td><span>공지</span></td>
        <td><a href="#" onclick="f_view('1347690');">영사민원 수수료 카드결제로 납부 가능(2026.4.1 부터)</a></td>
        <td>주 밴쿠버 총영사관</td><td><div>2026-03-25</div></td></tr></table>''')
        self.assertEqual(len(parser.posts), 1)
        self.assertTrue(parser.posts[0]["url"].endswith("seq=1347690"))
        self.assertEqual(parser.posts[0]["date"], "2026-03-25")

    def test_rss_repairs_official_http_port_443_links(self):
        posts = parse_rss('''<rss><channel><item><title>새 글 &amp; 안내</title>
        <link>http://www.mofa.go.kr:443/ca-vancouver-ko/brd/m_4585/view.do?seq=123</link>
        <pubDate>Thu, 01 Oct 2026 12:00:00 GMT</pubDate></item></channel></rss>''')
        self.assertEqual(posts[0]["url"], post(123)["url"])
        self.assertEqual(posts[0]["title"], "새 글 & 안내")
        with self.assertRaises(ValueError):
            parse_rss("<html>Temporary failure</html>")

    @patch("monitor.time.sleep")
    def test_baseline_dedup_and_restart(self, sleep):
        remember(self.conn, BOARD, [post(1), post(2)])
        messages = []
        deliver(self.conn, messages.append)
        self.assertEqual(messages, [])
        remember(self.conn, BOARD, [post(2), post(3, "새 글 <알림>")])
        deliver(self.conn, messages.append)
        self.assertEqual(len(messages), 1)
        self.assertIn("&lt;알림&gt;", messages[0])
        self.conn.close()
        self.conn = database(Path(self.temp.name) / "state.sqlite3")
        remember(self.conn, BOARD, [post(3)])
        deliver(self.conn, messages.append)
        self.assertEqual(len(messages), 1)

    @patch("monitor.time.sleep")
    def test_failed_delivery_remains_queued_even_if_not_in_next_poll(self, sleep):
        remember(self.conn, BOARD, [post(1)])
        remember(self.conn, BOARD, [post(2)])
        with self.assertRaises(RuntimeError):
            deliver(self.conn, lambda text: (_ for _ in ()).throw(RuntimeError()))
        remember(self.conn, BOARD, [post(3)])
        messages = []
        deliver(self.conn, messages.append)
        self.assertEqual(len(messages), 2)

    def test_collection_failure_does_not_initialize_board(self):
        class BrokenCollector:
            def collect(self, board, pages):
                raise ValueError("Site structure changed")
        self.assertTrue(cycle({"boards": [BOARD], "pages": 3}, BrokenCollector(), self.conn, lambda text: None))
        self.assertEqual(self.conn.execute("SELECT count(*) FROM boards").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
