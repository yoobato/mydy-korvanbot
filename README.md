# KoreaVancouverBot

주밴쿠버 대한민국 총영사관 홈페이지의 새 게시글을 텔레그램으로 알려주는 비공식 알림 서비스입니다.

[채널 구독](https://t.me/korea_vancouver) · [봇](https://t.me/KoreaVancouverBot)

## 모니터링 게시판

- [공지사항](https://www.mofa.go.kr/ca-vancouver-ko/brd/m_4585/list.do)
- [순회영사](https://www.mofa.go.kr/ca-vancouver-ko/brd/m_20174/list.do)
- [해외여행안전정보](https://www.mofa.go.kr/ca-vancouver-ko/brd/m_27536/list.do)
- [동포/지역한인회 소식](https://www.mofa.go.kr/ca-vancouver-ko/brd/m_24795/list.do)

자료 출처는 [총영사관 공식 홈페이지](https://www.mofa.go.kr/ca-vancouver-ko/index.do)이며,
공지사항은 [공식 RSS](https://www.mofa.go.kr/ca-vancouver-ko/brd/rss.do?brdId=4004)도 확인합니다.

## 동작 원리

1. **1시간 주기**로 각 게시판의 최근 3페이지를 확인합니다.
2. 첫 실행에서는 기존 글을 기록만 하고, 이후 새로 발견한 글부터 알림을 보냅니다.
3. **🔔 게시판 → 날짜 → 제목 → 본문 요약 → 원문 링크** 순서로 채널에 게시합니다.
4. 전송 기록으로 중복 알림을 줄이고, 실패한 전송은 다음 확인에서 재시도합니다.

항목 사이에는 한 줄씩 띄우고, 날짜는 `2026년 5월 21일 (목)` 형식으로 표시합니다.
본문 요약은 도입부와 일시·장소·신청 안내를 최대 320자로 발췌하며, 이미지뿐인 글은 원문 확인 안내를 표시합니다.

제목 수정은 새 알림을 만들지 않습니다. 같은 공지가 여러 게시판에 올라오면 각각 알림을 보냅니다.
오랜 중단으로 조회 범위를 벗어난 글은 놓칠 수 있고, 전송 응답이 유실되면 중복 알림이 발생할 수 있습니다.

게시판·확인 주기는 `boards.json`, 환경변수 예시는 `.env.example`을 참고하세요.
실제 `.env`와 게시글 기록은 저장소에 포함하지 않습니다.
