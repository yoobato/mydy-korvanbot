import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from monitor import BoardParser, DetailParser, cycle, database, deliver, format_date, format_message, parse_rss, remember, summarize_body

BOARD = {"id": "m_4585", "name": "공지사항"}


def detail(url, title):
    return {"date": "2026-10-01", "summary": "본문 요약"}


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
        deliver(self.conn, messages.append, detail)
        self.assertEqual(messages, [])
        remember(self.conn, BOARD, [post(2), post(3, "새 글 <알림>")])
        deliver(self.conn, messages.append, detail)
        self.assertEqual(len(messages), 1)
        self.assertIn("&lt;알림&gt;", messages[0])
        self.conn.close()
        self.conn = database(Path(self.temp.name) / "state.sqlite3")
        remember(self.conn, BOARD, [post(3)])
        deliver(self.conn, messages.append, detail)
        self.assertEqual(len(messages), 1)

    @patch("monitor.time.sleep")
    def test_failed_delivery_remains_queued_even_if_not_in_next_poll(self, sleep):
        remember(self.conn, BOARD, [post(1)])
        remember(self.conn, BOARD, [post(2)])
        with self.assertRaises(RuntimeError):
            deliver(self.conn, lambda text: (_ for _ in ()).throw(RuntimeError()), detail)
        remember(self.conn, BOARD, [post(3)])
        messages = []
        deliver(self.conn, messages.append, detail)
        self.assertEqual(len(messages), 2)

    def test_collection_failure_does_not_initialize_board(self):
        class BrokenCollector:
            def collect(self, board, pages):
                raise ValueError("Site structure changed")
            detail = staticmethod(detail)
        self.assertTrue(cycle({"boards": [BOARD], "pages": 3}, BrokenCollector(), self.conn, lambda text: None))
        self.assertEqual(self.conn.execute("SELECT count(*) FROM boards").fetchone()[0], 0)

    def test_detail_excludes_header_footer_and_scripts(self):
        parser = DetailParser()
        parser.feed('''<div class="bo_head">작성일 <dd>2026-10-02</dd></div>
        <div class="bo_con"><div><p>안내 제목</p><p>접수는 <b>10월 5일</b>까지입니다.</p>
        <p>신청서를 제출해 주세요.<br/>문의는 이메일로 받습니다.</p>
        <script>tracking()</script></div></div><footer>개인정보처리방침</footer>''')
        summary = summarize_body("".join(parser.text), "안내 제목")
        self.assertIn("접수는 10월 5일까지입니다.", summary)
        self.assertNotIn("tracking", summary)
        self.assertNotIn("개인정보처리방침", summary)
        self.assertNotIn("작성일", summary)

    def test_image_only_post_has_honest_fallback_and_excerpt_is_bounded(self):
        parser = DetailParser()
        parser.feed('<div class="bo_con"><p><img src="poster.jpg"/><br/></p></div>')
        self.assertIn("이미지", summarize_body("".join(parser.text), "행사", parser.has_images))
        self.assertEqual(len(summarize_body("가" * 500, "제목")), 320)

    def test_summary_prioritizes_schedule_over_headings(self):
        text = "순회영사를 실시합니다.\n1. 일정 안내\n기상 악화에 주의하세요.\n- 일시 : 2026.6.26 10:00\n- 장소 : 행사장\n- 온라인 예약 : 6월 16일부터"
        summary = summarize_body(text, "순회영사")
        self.assertIn("2026.6.26 10:00", summary)
        self.assertIn("장소 : 행사장", summary)
        self.assertIn("온라인 예약", summary)
        self.assertNotIn("1. 일정 안내", summary)

    def test_message_format_escapes_content_and_omits_old_labels(self):
        message = format_message("공지사항", "안내 <제목>", "2026-10-02", "문의 & 접수", post(1)["url"])
        self.assertIn("&lt;제목&gt;", message)
        self.assertIn("문의 &amp; 접수", message)
        self.assertNotIn("총영사관", message)
        self.assertNotIn("테스트", message)

    def test_date_uses_korean_weekday_and_preserves_unrecognized_values(self):
        self.assertEqual(format_date("2026-05-21"), "2026년 5월 21일 (목)")
        self.assertEqual(format_date("2026-10-02"), "2026년 10월 2일 (금)")
        self.assertEqual(format_date("날짜 미상"), "날짜 미상")
        self.assertEqual(format_date("2026-02-30"), "2026-02-30")

    def test_detail_failure_preserves_pending_post(self):
        remember(self.conn, BOARD, [post(1)])
        remember(self.conn, BOARD, [post(2)])
        def failed_detail(url, title):
            raise ValueError("Body unavailable")
        messages = []
        with self.assertRaises(ValueError):
            deliver(self.conn, messages.append, failed_detail)
        self.assertEqual(messages, [])
        self.assertEqual(self.conn.execute("SELECT sent FROM posts WHERE url=?", (post(2)["url"],)).fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
