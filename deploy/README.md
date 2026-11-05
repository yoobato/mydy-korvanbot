# 최신 알림 예시 제공

수집 워커가 공개 채널의 최신 게시글 번호와 링크를 `data/public/latest.json`에 저장합니다. `preview` 서비스는 이 디렉터리만 읽으며 `/latest.json` 외의 요청에는 404를 반환합니다. 채널 전송·수정 비교 기록과 비밀 설정은 마운트하지 않습니다.

기존 Lightsail의 `mydy_edge` 네트워크와 HTTPS 프록시를 사용합니다. DNS에 `api.korvanbot.mydy.kr`의 A 레코드를 서버 공인 IP로 연결하고 DNS only로 설정합니다. HTTPS 인증서는 기존 Caddy가 관리합니다.

1. 외부 비밀 설정 파일을 지정하는 기존 환경을 유지합니다. 첫 실행 전에 `data/public` 디렉터리를 준비합니다.
2. `docker compose --profile public-preview up -d --build`로 워커와 공개 조회 서비스를 실행합니다. `public-preview` 프로필을 생략하면 워커만 실행합니다.
3. 기존 HTTPS 프록시 구성에 `edge.Caddyfile` 블록을 추가합니다. 전체 설정을 검증한 뒤 Caddy를 reload하며 다른 서비스의 구성은 유지합니다. `preview.Caddyfile`은 공개 조회 컨테이너 전용입니다.
4. `https://api.korvanbot.mydy.kr/latest.json`이 JSON과 `Access-Control-Allow-Origin: *`, `Cache-Control: no-store`를 반환하는지 확인합니다. 공개 조회는 인증 없이 허용되며 게시글 번호와 공개 링크만 포함합니다.

GitHub Pages에는 같은 주소를 읽는 정적 페이지를 배포합니다. 채널 게시글이 바뀔 때마다 웹사이트를 다시 빌드하거나 저장소에 실행 데이터를 커밋할 필요는 없습니다. GitHub Pages 배포와 Lightsail의 공개 조회 서비스는 각각 독립적으로 유지됩니다.
