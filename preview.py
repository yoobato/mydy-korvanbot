"""Publish only the latest public Telegram post reference, never bot credentials."""
import json
from pathlib import Path
import re
import urllib.request
from html.parser import HTMLParser

CHANNEL = "korea_vancouver"


class PreviewFailure(ValueError):
    """Safe diagnostic for public preview failures."""


class ChannelParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.message_depth = None
        self.message_id = None
        self.posts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "div":
            self.depth += 1
            if "data-post" in attrs:
                match = re.fullmatch(CHANNEL + r"/([1-9]\d*)", attrs["data-post"])
                self.message_id = int(match[1]) if match else None
                self.message_depth = self.depth
        if self.message_id and "tgme_widget_message_text" in attrs.get("class", "").split():
            self.posts.append(self.message_id)

    def handle_endtag(self, tag):
        if tag == "div":
            if self.depth == self.message_depth:
                self.message_id = self.message_depth = None
            self.depth = max(0, self.depth - 1)


def latest_post(content):
    parser = ChannelParser()
    parser.feed(content)
    if not parser.posts:
        raise PreviewFailure("공개 텔레그램 채널에서 본문이 있는 게시글 번호를 찾지 못했습니다. 기존 예시는 유지합니다.")
    return max(parser.posts)


def write_preview(path, message_id):
    if type(message_id) is not int or not 0 < message_id <= 2**53 - 1:
        raise PreviewFailure("텔레그램 전송 응답에 유효한 게시글 번호가 없습니다. 기존 예시는 유지합니다.")
    post = f"{CHANNEL}/{message_id}"
    payload = json.dumps({"post": post, "url": f"https://t.me/{post}"}) + "\n"
    path = Path(path)
    temporary = path.with_suffix(".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(payload, encoding="utf-8")
        temporary.replace(path)
    except OSError:
        raise PreviewFailure("최신 알림 정보 파일을 저장하지 못했습니다. 기존 파일과 채널 전송 기록은 유지합니다.") from None
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def refresh_preview(path):
    request = urllib.request.Request(f"https://t.me/s/{CHANNEL}", headers={"User-Agent": "ConsulateAlerts/1.0"})
    with urllib.request.urlopen(request, timeout=25) as response:
        content = response.read(2_000_001)
    if len(content) > 2_000_000:
        raise PreviewFailure("공개 채널 응답이 예상보다 큽니다. 기존 예시는 유지합니다.")
    write_preview(path, latest_post(content.decode("utf-8")))
