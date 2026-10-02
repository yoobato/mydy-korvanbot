# KoreaVancouverBot

주밴쿠버 대한민국 총영사관 게시판의 새 글을 공개 텔레그램 채널에 자동 게시합니다.
개인이 운영하는 비공식 서비스로, 원문 제목·게시일·링크만 전달합니다.
구독자는 공개 채널 링크를 열어 참여하고 알림을 켜면 됩니다. 회원가입이나 전화번호 수집은 없습니다.

저장소: [yoobato/mydy-korvanbot](https://github.com/yoobato/mydy-korvanbot).
개발은 `main`에서 진행하며 변경할 때 관련 문서도 함께 갱신하고 커밋·푸시합니다.
운영 서버는 CaLog·ChutChut과 같은 AWS Lightsail입니다. **도메인이나 인바운드 포트는 필요 없습니다.**
실제 배포 경로와 절차·현재 상태는 [운영 문서](docs/deployment.md)를 확인하세요.
Lightsail에서 자동 알림을 운영합니다. 공개 구독 채널은
[주밴쿠버 대한민국 총영사관 소식](https://t.me/korea_vancouver), 게시 봇은
[@KoreaVancouverBot](https://t.me/KoreaVancouverBot)입니다.
채널에 참여하고 알림을 켜면 이후 감지한 새 게시글을 받을 수 있습니다.
서버에서 실제 게시판 5개 수집과 테스트 메시지 전송을 확인했습니다.

## 텔레그램 준비

1. 텔레그램에서 공개 채널을 만들고 공개 주소를 설정합니다. 예: `@vancouver_consulate_updates` (예시이며 실제 계정이 아닙니다).
2. [@BotFather](https://t.me/BotFather)에게 `/newbot`을 보내 봇을 만듭니다.
3. 채널의 관리자에 봇을 추가하고 **메시지 게시** 권한을 줍니다.
4. 봇 토큰을 채팅이나 저장소에 넣지 말고 작업공간 밖의 비밀 파일에 저장합니다.

관리자 추가 메뉴: **채널 열기 → 상단 채널 이름 → 편집/관리 → 관리자 → 관리자 추가**.
`KoreaVancouverBot`이 표시 이름이라면 BotFather가 지정한 정확한 `@사용자명`으로 검색합니다.
관리자 역할에서 메시지 게시를 켜고 저장하세요. 앱 언어와 기기에 따라 메뉴 이름은 조금 다를 수 있습니다.
채널의 `@주소`와 봇의 `@사용자명`은 서로 다른 값입니다.

채널 소개 예시:

> 주밴쿠버 대한민국 총영사관 홈페이지의 새 게시글을 알려드립니다.
> 개인이 운영하는 비공식 서비스이며, 총영사관이 운영하거나 승인한 채널이 아닙니다.
> 정확한 내용은 각 메시지의 원문 링크를 확인해 주세요.

## 비밀값 설정

`/Users/yoobato/YoobatoDev/secrets/consulate-alerts/telegram.env`에 다음 값을 저장하세요.
파일 권한은 `chmod 600`으로 제한합니다. Docker에서는 실행 호스트에 맞는 경로를 사용하세요.

```dotenv
TELEGRAM_BOT_TOKEN=BotFather에서_받은_토큰
TELEGRAM_CHANNEL_ID=@실제_공개채널아이디
```

## 로컬 확인 및 실행

Python 3.11 이상이면 별도 패키지 설치가 필요 없습니다. 아래 명령은 이 제품 디렉터리에서 실행합니다.
이 Mac에서 검증에 사용한 Python은 `/Users/yoobato/.pyenv/versions/3.12.2/bin/python3`입니다.
`python3`가 `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3`로 연결되어 인증서 오류가 나면
검증된 Python 경로로 실행하거나 해당 Python의 CA 인증서 설정을 복구하세요. TLS 검증은 끄지 않습니다.

```sh
python3 -m unittest discover -s tests -v
python3 monitor.py preview
```

`preview`는 실제 게시판 수집만 확인합니다. 메시지를 보내거나 상태 DB를 만들지 않습니다.

```sh
set -a
source /Users/yoobato/YoobatoDev/secrets/consulate-alerts/telegram.env
set +a
python3 monitor.py test-message
python3 monitor.py once
python3 monitor.py run
```

`test-message`는 채널에 테스트 메시지 1개를 게시합니다.
`once`는 한 번 확인하고 종료합니다. 새 DB에서는 기존 글을 기준선으로 저장만 합니다.
`run`은 기본 10분 간격으로 계속 확인합니다. 로컬 컴퓨터가 잠자거나 종료되면 감시도 멈춥니다.

## 계속 켜 둘 서버에서 실행

```sh
export KORVANBOT_ENV_FILE=/절대경로/telegram.env
docker compose up -d --build
docker compose logs --tail=50
```

봇 메시지 발송 자체는 이 채널 방식에서 건별 비용이 없으며, 서버 비용은 별도입니다.
Lightsail에서는 [운영 문서](docs/deployment.md)의 배포 스크립트를 사용합니다.
채널 연결·실행 여부는 운영 문서의 배포 상태를 확인하세요.

## 게시판 설정

`boards.json`에 기본으로 공지사항, 순회영사, 해외여행안전정보, 공관 활동, 동포/지역한인회 소식이 설정되어 있습니다.
공지사항은 공식 RSS와 목록을 함께 읽으며, 다른 게시판은 목록을 읽습니다.
RSS가 실패하면 목록을 사용합니다. 쿠키를 유지해 사이트의 동일 주소 리다이렉트를 처리합니다.

아래 게시판을 `boards` 배열에 같은 형식으로 추가할 수 있습니다.
예: `{"id": "m_4573", "name": "여권"}`. 제외할 때는 `"enabled": false`를 넣습니다.
추가 게시판은 첫 확인 때 기준선을 새로 만들므로 기존 글을 전송하지 않습니다.

| ID | 게시판 |
|---|---|
| m_4572 | 자주묻는질문 |
| m_4573 | 여권 |
| m_4574 | 비자 |
| m_4575 | 병역 |
| m_4576 | 가족관계등록 |
| m_4577 | 국적 |
| m_4578 | 공증 |
| m_4579 | 재외국민등록/해외이주신고 |
| m_4580 | 각종 증명서 발급 |
| m_4581 | 신속해외송금지원제도 |
| m_4583 | 공관별민원서식 |
| m_4587 | 관할지 개관 |
| m_4588 | 한국과의관계 |
| m_4589 | 관할지 경제정보 |
| m_4594 | 해외취업 지원 정보 |
| m_4592 | 기업지원헬프데스크 |
| m_4598 | 한인단체현황 |
| m_4599 | 교육/유학정보 |
| m_26508 | 워킹홀리데이 정보 |
| m_4602 | 일자리 정보 |
| m_4603 | 캐나다민원정보 |
| m_24869 | 유실물 공지 |
| m_4590 | 수출수주알리미 |

## 운영 동작과 제한

- SQLite에 발견·전송 상태를 저장하므로 재시작해도 보통 같은 글을 다시 보내지 않습니다. `data/`를 보존하세요.
- 고정 공지와 일반 글을 게시글 URL로 구분하며, 제목 수정만으로 알림을 재발송하지 않습니다.
- 기본 최근 3페이지와 RSS 범위에서 새로 발견한 글을 감지합니다. 긴 장애 기간에 그 범위를 넘어간 글은 놓칠 수 있으므로 `pages`를 조정하세요.
- 수집 실패 또는 목록 구조 변경 시 해당 게시판 상태를 갱신하지 않고 오류를 기록합니다. 다른 게시판은 계속 확인합니다.
- 전송 실패는 대기열에 남겨 다음 확인 때 다시 시도합니다. 오래된 대기열도 목록에서 사라졌다고 삭제하지 않습니다.
- 텔레그램이 메시지를 받은 직후 프로세스가 종료되거나 응답이 유실되면 다음 시도에서 중복 게시될 수 있습니다. 정확히 한 번 전송을 보장하지 않습니다.
- 같은 DB를 쓰는 두 프로세스의 동시 실행은 잠금으로 방지합니다. 채널·봇별로 DB를 분리하세요.
- 게시판별로 독립적인 URL을 사용하므로 같은 공지가 서로 다른 게시판에 등록되면 각각 알림을 보냅니다.
- 오류 기록은 로컬/Docker 로그에 남습니다. 별도 운영 장애 알림은 아직 없습니다.

공식 문서: [RSS 안내](https://www.mofa.go.kr/ca-vancouver-ko/wpge/m_24145/contents.do),
[Telegram Bot API](https://core.telegram.org/bots/api#sendmessage).
