# Lightsail 운영

## 배치와 네트워크

- 저장소: https://github.com/yoobato/mydy-korvanbot, `main`
- SSH 별칭: `yoobato-canada-lightsail`
- 앱: `/opt/services/korvanbot`
- 비밀 파일: `/opt/secrets/korvanbot/telegram.env` (권한 600)
- 상태 DB: `/opt/services/korvanbot/data/state.sqlite3`
- Compose 프로젝트·서비스: `korvanbot`
- 공개 채널: https://t.me/korea_vancouver (`@korea_vancouver`)
- 게시 봇: `@KoreaVancouverBot`

CaLog, ChutChut, BabyLog가 실행 중인 Lightsail에 독립적인 Compose 프로젝트로 배치합니다.
봇은 HTTP 서버나 webhook을 사용하지 않습니다. 도메인·인바운드 포트·Caddy 설정 변경은 필요 없습니다.
`korvanbot_default` 네트워크에서 외부 HTTPS 연결만 사용하며 `mydy_edge`에 참여하지 않습니다.
컨테이너 메모리는 128MB, CPU는 0.25개, 로그는 5MB × 3개로 제한합니다.

## 변경과 배포

코드·설정·문서 변경을 함께 테스트하고 `main`에 커밋·푸시합니다. 이후:

```sh
bash deploy.sh prepare
```

스크립트는 `main` 작업공간이 깨끗하고 `origin/main`과 같은 커밋인지 확인합니다.
Git에서 추적하는 파일만 서버로 전송하고 이미지를 빌드합니다. 실행 중인 컨테이너는 이 단계에서 교체하지 않습니다.
비밀 파일이 없으면 권한 600인 빈 파일을 준비하며 기존 파일은 보존합니다.
서버의 `DEPLOYED_REVISION` 파일은 마지막으로 전송한 소스 커밋을 기록합니다.

첫 설정은 로컬 비밀 파일에 실제 토큰·채널 주소를 입력한 뒤 전송합니다.

```sh
scp /Users/yoobato/YoobatoDev/secrets/consulate-alerts/telegram.env \
  yoobato-canada-lightsail:/opt/secrets/korvanbot/telegram.env
ssh yoobato-canada-lightsail 'chmod 600 /opt/secrets/korvanbot/telegram.env'
```

처음 한 번 채널에 테스트 메시지를 보내 게시 권한을 확인합니다.

```sh
ssh yoobato-canada-lightsail \
  'cd /opt/services/korvanbot && KORVANBOT_ENV_FILE=/opt/secrets/korvanbot/telegram.env docker compose run --rm korvanbot python monitor.py test-message'
bash deploy.sh start
```

첫 실행은 기존 글을 저장만 합니다. 이후 새 글을 자동 게시합니다.
테스트 메시지 명령은 실행할 때마다 실제 채널에 메시지 1개를 게시합니다.

## 확인, 중지, 백업

```sh
ssh yoobato-canada-lightsail
cd /opt/services/korvanbot
export KORVANBOT_ENV_FILE=/opt/secrets/korvanbot/telegram.env
docker compose ps
docker compose logs --tail=100
docker compose stop
```

`docker compose stop`은 이 봇만 중지합니다. 다시 시작하려면 `docker compose up -d`를 실행합니다.
백업 전 이 봇을 중지하고 `data/`와 외부 비밀 파일을 안전한 장소에 복사한 뒤 다시 시작하세요.
DB를 지우면 다음 시작에서 기준선을 다시 만들고 이전 기록을 잃습니다.
장애 기간에 누락이 생기지 않도록 목록 조회 범위와 로그를 확인하세요.

## 배포 상태

2026-10-01 (America/Edmonton) 기준:

- 코드 배치와 Docker 이미지 빌드 완료.
- 운영 서버의 제한된 컨테이너에서 실제 게시판 5개 수집 확인: 공지사항 36개, 나머지 각 30개.
- 수집 중 메모리 약 21.5MiB. CaLog·ChutChut·BabyLog 컨테이너 상태 유지 확인.
- 로컬과 서버의 비밀 파일을 권한 600으로 설정했으며 봇 토큰과 채널 ID 연결 완료.
- Telegram API로 봇 사용자명, 채널 종류, 메시지 게시 권한 확인 완료.
- Lightsail에서 테스트 메시지 1개를 채널에 전송했고 Telegram API 성공 응답 확인.
- `korvanbot-korvanbot-1` 지속 실행 컨테이너 시작 완료. 기본 10분 간격으로 확인합니다.
- 첫 확인에서는 기존 게시글을 기준선으로 저장만 하고, 이후 감지한 새 글부터 게시합니다.
