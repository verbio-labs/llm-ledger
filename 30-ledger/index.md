# Router (MOC) — 이건 카탈로그가 아니라 라우터입니다

질문이 오면 **이 파일 + `aliases.md`만 읽고** 어느 인덱스/샤드를 펼칠지 결정하세요.
토픽 페이지나 주장을 처음부터 다 읽지 마세요 (토큰 일정성 유지).

## 라우팅 규칙 (의도 → 대상)
- 특정 토픽의 사실을 물으면 → `indexes/by-topic.md`에서 해당 토픽의 claim_refs → 그 주장만 펼침.
- "언제/어떻게 바뀌었나 / ~년 기준" 시간 질문 → `indexes/by-time.md` (+ `/timeline`).
- "확실한가 / 이견 있나 / 출처" 신뢰도 질문 → `indexes/by-confidence.md`.
- 자유 탐색·개요 → `topics/{topic}.md` 뷰.

## 인덱스
- [by-topic](indexes/by-topic.md) — 토픽 → 주장
- [by-time](indexes/by-time.md) — valid_from 정렬
- [by-confidence](indexes/by-confidence.md) — contested/low 빠른 조회

## 토픽 (정본명은 aliases.md)
- pluto → [topics/pluto.md](topics/pluto.md)

## 성장 메모
- 인덱스가 ≥50K 토큰이면 정본명 첫 글자로 샤딩.
- 규모가 커지면 `.rag`(BM25/벡터)를 1순위 회수로, 라우터→샤드는 폴백으로.
