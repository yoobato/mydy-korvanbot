"""Consulate boards → a Telegram channel. Python 3.11+, no dependencies."""
import argparse
from datetime import datetime
import fcntl
import html
import http.cookiejar
import json
import logging
import os
from pathlib import Path
import re
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parent
BASE = "https://www.mofa.go.kr"
LOG = logging.getLogger("consulate-alerts")


class BoardParser(HTMLParser):
    def __init__(self, board):
        super().__init__()
        self.board = board
        self.posts = []
        self.row = None
        self.anchor = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "tr":
            self.row = {"seq": None, "title": [], "text": []}
        if tag == "a" and self.row is not None:
            match = re.search(r"f_view\(['\"](\d+)['\"]", attrs.get("onclick", ""))
            if match:
                self.row["seq"] = match[1]
                self.anchor = True

    def handle_data(self, data):
        if self.row is not None:
            self.row["text"].append(data)
            if self.anchor:
                self.row["title"].append(data)

    def handle_endtag(self, tag):
        if tag == "a":
            self.anchor = False
        if tag == "tr" and self.row is not None:
            row = self.row
            title = " ".join("".join(row["title"]).split())
            date = re.search(r"\d{4}-\d{2}-\d{2}", "".join(row["text"]))
            if row["seq"] and title and date:
                self.posts.append({"title": title, "date": date[0],
                    "url": f'{BASE}/ca-vancouver-ko/brd/{self.board}/view.do?seq={row["seq"]}'})
            self.row = None


class DetailParser(HTMLParser):
    VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__()
        self.depth = 0
        self.body_depth = None
        self.head_depth = None
        self.hidden_depth = None
        self.text = []
        self.header = []
        self.has_images = False
        self.found_body = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag not in self.VOID_TAGS:
            self.depth += 1
        classes = attrs.get("class", "").split()
        if "bo_con" in classes:
            self.body_depth = self.depth
            self.found_body = True
        if "bo_head" in classes:
            self.head_depth = self.depth
        if self.body_depth is not None:
            if tag in {"script", "style"}:
                self.hidden_depth = self.depth
            if tag == "img":
                self.has_images = True
            if tag in {"br", "p", "li", "tr", "div"}:
                self.text.append("\n")

    def handle_data(self, data):
        if self.body_depth is not None and self.hidden_depth is None:
            self.text.append(data)
        if self.head_depth is not None:
            self.header.append(data)

    def handle_endtag(self, tag):
        if tag in self.VOID_TAGS:
            return
        if self.body_depth is not None and tag in {"p", "li", "tr", "div"}:
            self.text.append("\n")
        if self.depth == self.hidden_depth:
            self.hidden_depth = None
        if self.depth == self.body_depth:
            self.body_depth = None
        if self.depth == self.head_depth:
            self.head_depth = None
        self.depth = max(0, self.depth - 1)


def summarize_body(text, title, has_images=False):
    paragraphs = [" ".join(p.replace("\u200b", "").replace("\ufeff", "").split()) for p in text.splitlines()]
    paragraphs = [p for p in paragraphs if p and p != title and not p.startswith(("(사진", "사진제공", "사진 제공"))]
    if not paragraphs:
        return "본문이 이미지로 게시되어 있습니다.\n자세한 내용은 원문 이미지를 확인해 주세요." if has_images else "본문에 텍스트가 없습니다.\n자세한 내용은 원문을 확인해 주세요."
    # Prefer explicit schedule/application lines, preserving their original text.
    labels = r"(?:일시|일자|장소|신청\s*기간|접수\s*기간|예약\s*기간|온라인\s*예약|마감)\s*[:：]"
    important = [p for p in paragraphs[1:] if re.search(labels, p)]
    selected = [paragraphs[0]] + important[:3] if important else paragraphs[:2]
    excerpt = "\n\n".join(re.sub(r"(?<=[.!?])\s+(?=[가-힣])", "\n", p) for p in selected)
    if len(excerpt) <= 320:
        return excerpt
    return excerpt[:319].rstrip() + "…"


def format_date(value):
    try:
        day = datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return value
    return f'{day:%Y-%m-%d} ({"월화수목금토일"[day.weekday()]})'


def format_message(name, title, date, summary, url):
    return (f'🔔 <b>{html.escape(name)}</b>\n\n'
            f'📅 {html.escape(format_date(date))}\n\n'
            f'📝 <b>{html.escape(title[:1800])}</b>\n\n'
            f'<blockquote>{html.escape(summary)}</blockquote>\n\n'
            f'🔗 <a href="{html.escape(url, quote=True)}">원문 보기</a>')


def parse_rss(content):
    root = ET.fromstring(content)
    if root.tag != "rss":
        raise ValueError("Expected an RSS document")
    posts = []
    for item in root.findall("./channel/item"):
        url = urllib.parse.urlsplit(item.findtext("link", ""))
        # The official feed emits http://www.mofa.go.kr:443 links.
        if not url.path.startswith("/ca-vancouver-ko/brd/"):
            continue
        title = " ".join(item.findtext("title", "").split())
        if title and "seq" in urllib.parse.parse_qs(url.query):
            posts.append({"title": title, "date": item.findtext("pubDate", ""),
                "url": urllib.parse.urlunsplit(("https", "www.mofa.go.kr", url.path, url.query, ""))})
    if not posts:
        raise ValueError("Feed has no recognizable posts")
    return posts


class Collector:
    def __init__(self, reporter=None):
        self.reporter = reporter
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def get(self, url):
        request = urllib.request.Request(url, headers={"User-Agent": "ConsulateAlerts/1.0"})
        with self.opener.open(request, timeout=25) as response:
            return response.read().decode("utf-8-sig")

    def collect(self, board, pages):
        # Lists are also read to cover pinned posts and items outside the RSS window.
        posts = {}
        if board.get("rss_id"):
            try:
                for post in parse_rss(self.get(f'{BASE}/ca-vancouver-ko/brd/rss.do?brdId={board["rss_id"]}')):
                    posts[post["url"]] = post
                if self.reporter:
                    self.reporter.update(f'rss:{board["id"]}', f'{board["name"]} RSS')
            except Exception as exc:
                LOG.warning("%s RSS unavailable (%s); reading lists", board["name"], type(exc).__name__)
                if self.reporter:
                    self.reporter.update(f'rss:{board["id"]}', f'{board["name"]} RSS (목록으로 대체 수집)', exc)
        for page in range(1, pages + 1):
            parser = BoardParser(board["id"])
            parser.feed(self.get(f'{BASE}/ca-vancouver-ko/brd/{board["id"]}/list.do?page={page}'))
            if not parser.posts:
                raise ValueError("List has no recognizable posts; refusing to update state")
            for post in parser.posts:
                posts[post["url"]] = post
        return sorted(posts.values(), key=lambda p: int(urllib.parse.parse_qs(urllib.parse.urlsplit(p["url"]).query)["seq"][0]))

    def detail(self, url, title):
        parser = DetailParser()
        parser.feed(self.get(url))
        if not parser.found_body:
            raise ValueError("Post body not recognized")
        date = re.search(r"\d{4}-\d{2}-\d{2}", " ".join(parser.header))
        return {"date": date[0] if date else None,
                "summary": summarize_body("".join(parser.text), title, parser.has_images)}


def database(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE IF NOT EXISTS boards (id TEXT PRIMARY KEY)")
    conn.execute("CREATE TABLE IF NOT EXISTS posts (url TEXT PRIMARY KEY, board TEXT, name TEXT, title TEXT, date TEXT, sent INTEGER)")
    conn.execute("CREATE TABLE IF NOT EXISTS issues (key TEXT PRIMARY KEY, label TEXT, active INTEGER, notified INTEGER)")
    conn.commit()
    return conn


def remember(conn, board, posts):
    initialized = conn.execute("SELECT 1 FROM boards WHERE id=?", (board["id"],)).fetchone()
    with conn:
        for post in posts:
            conn.execute("INSERT OR IGNORE INTO posts VALUES (?,?,?,?,?,?)",
                (post["url"], board["id"], board["name"], post["title"], post["date"], 0 if initialized else 1))
        conn.execute("INSERT OR IGNORE INTO boards VALUES (?)", (board["id"],))
    return bool(initialized)


def telegram(token, channel, text):
    request = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage",
        data=json.dumps({"chat_id": channel, "text": text, "parse_mode": "HTML",
                         "link_preview_options": {"is_disabled": True}}).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        # Do not log the exception URL: it contains the bot token.
        raise RuntimeError(f"Telegram HTTP {exc.code}; check channel permissions, token, and rate limits") from None
    except Exception:
        raise RuntimeError("Telegram network error; delivery outcome uncertain") from None
    if not result.get("ok"):
        raise RuntimeError("Telegram rejected the message")


class IssueReporter:
    """Persist incidents, retry failed alerts, and announce recovery once."""
    def __init__(self, conn, send):
        self.conn = conn
        self.send = send

    def update(self, key, label, error=None):
        try:
            row = self.conn.execute("SELECT label,active,notified FROM issues WHERE key=?", (key,)).fetchone()
            if error is not None:
                if row and row[1] and row[2]:
                    return
                with self.conn:
                    self.conn.execute("INSERT OR REPLACE INTO issues VALUES (?,?,1,0)", (key, label))
                message = (f'⚠️ <b>KoreaVancouverBot 장애 알림</b>\n\n{html.escape(label)}\n'
                           f'오류 유형: <code>{html.escape(type(error).__name__)}</code>\n\n'
                           '다음 확인 주기에 재시도합니다. 같은 장애의 반복 알림은 생략합니다.')
                self.send(message)
                with self.conn:
                    self.conn.execute("UPDATE issues SET notified=1 WHERE key=?", (key,))
            elif row and (row[1] or row[2]):
                with self.conn:
                    self.conn.execute("UPDATE issues SET active=0 WHERE key=?", (key,))
                if row[2]:
                    self.send(f'✅ <b>KoreaVancouverBot 복구 알림</b>\n\n{html.escape(row[0])}\n정상 동작을 확인했습니다.')
                with self.conn:
                    self.conn.execute("UPDATE issues SET active=0,notified=0 WHERE key=?", (key,))
        except Exception as exc:
            # Alert transport failure must not interrupt public post delivery.
            LOG.error("Private issue alert failed (%s); retry on next check", type(exc).__name__)

    def retry_recoveries(self):
        for key, label in self.conn.execute("SELECT key,label FROM issues WHERE active=0 AND notified=1").fetchall():
            self.update(key, label)


def deliver(conn, send, get_detail, reporter=None):
    failed = False
    for url, name, title, date in conn.execute("SELECT url,name,title,date FROM posts WHERE sent=0 ORDER BY rowid").fetchall():
        try:
            detail = get_detail(url, title)
        except Exception as exc:
            if reporter is None:
                raise
            failed = True
            reporter.update(f'detail:{url}', f'{name} 원문 조회·파싱: {title[:200]}', exc)
            LOG.error("Post detail failed (%s); queued post retained", type(exc).__name__)
            continue
        if reporter:
            reporter.update(f'detail:{url}', f'{name} 원문 조회·파싱')
        try:
            send(format_message(name, title, detail["date"] or date, detail["summary"], url))
        except Exception as exc:
            if reporter is None:
                raise
            reporter.update('channel', '텔레그램 채널 전송 (미전송 글은 보관)', exc)
            LOG.error("Channel delivery failed (%s); queued posts retained", type(exc).__name__)
            return True
        if reporter:
            reporter.update('channel', '텔레그램 채널 전송')
        with conn:
            conn.execute("UPDATE posts SET sent=1 WHERE url=?", (url,))
        LOG.info("Published: %s", title)
        time.sleep(1.1)
    return failed


def cycle(config, collector, conn, send, reporter=None):
    failed = False
    if reporter:
        reporter.retry_recoveries()
    for board in config["boards"]:
        if not board.get("enabled", True):
            continue
        try:
            posts = collector.collect(board, config["pages"])
            initialized = remember(conn, board, posts)
            if reporter:
                reporter.update(f'board:{board["id"]}', f'{board["name"]} 수집·파싱')
            LOG.info("%s: %d posts (%s)", board["name"], len(posts), "checked" if initialized else "baseline saved, no history sent")
        except Exception as exc:
            failed = True
            LOG.error("%s: collection failed (%s); state retained", board["name"], type(exc).__name__)
            if reporter:
                reporter.update(f'board:{board["id"]}', f'{board["name"]} 수집·파싱', exc)
    try:
        failed = deliver(conn, send, collector.detail, reporter) or failed
    except Exception as exc:
        failed = True
        LOG.error("Delivery failed (%s); queued posts retained", type(exc).__name__)
        if reporter:
            reporter.update('worker', '알림 처리', exc)
    else:
        if reporter:
            reporter.update('worker', '알림 처리')
    return failed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "boards.json")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = json.loads(args.config.read_text())
    if config["pages"] < 1 or config["interval_seconds"] < 60:
        parser.error("pages must be positive and interval_seconds >= 60")
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    channel = os.environ.get("TELEGRAM_CHANNEL_ID")
    if not token or not channel:
        parser.error("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID in the external secrets file")
    send = lambda text: telegram(token, channel, text)
    state = Path(os.environ.get("STATE_PATH", str(ROOT / "data" / "state.sqlite3")))
    state.parent.mkdir(parents=True, exist_ok=True)
    with state.with_suffix(".lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error("Another monitor is already using this state database")
        conn = database(state)
        admin = os.environ.get("TELEGRAM_ADMIN_CHAT_ID")
        reporter = IssueReporter(conn, lambda text: telegram(token, admin, text)) if admin else None
        collector = Collector(reporter)
        try:
            while True:
                try:
                    cycle(config, collector, conn, send, reporter)
                except Exception as exc:
                    LOG.error("Monitor cycle failed (%s)", type(exc).__name__)
                    if reporter:
                        reporter.update('worker', '모니터링 처리', exc)
                time.sleep(config["interval_seconds"])
        finally:
            conn.close()


if __name__ == "__main__":
    main()
