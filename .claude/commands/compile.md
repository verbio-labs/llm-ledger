---
description: inbox 소스를 주장으로 추출하고 토픽 뷰·인덱스를 갱신한 뒤 raw로 이동합니다.
argument-hint: [특정 소스 파일명 | 비우면 inbox 전체]
---

# /compile — 합성 (원장의 핵심 쓰기 동작)

대상: `$ARGUMENTS` (비어 있으면 `10-inbox/` 전체)

먼저 `00-system/conventions.md`의 2~7절을 숙지하세요.

## 절차

### 1. 읽기
대상 소스를 읽는다. 토픽을 정한다 — `aliases.md`에서 **정본명**을 먼저 확인하고,
없으면 새 정본 키를 만들고 aliases에 등록한다.

### 2. 주장 추출 (atomic claims)
소스에서 검증 가능한 단언을 **원자 단위**로 뽑는다. 각 주장마다:
- `40-templates/claim.md` 형식으로 frontmatter 작성.
- `sources`에 이 소스 ref + 가능하면 원문 `quote` + `locator`.
- `valid_from` / `valid_until`을 본문 근거로 채운다 (모르면 unknown/null).
- `confidence`를 conventions 3절 기준으로 부여.
- ID는 `clm-{연도}-{다음 일련번호}` (기존 최대값+1).

### 3. 모순 검사 (덮어쓰지 않기 — 핵심)
새 주장이 기존 주장과 충돌하는지 `by-topic.md`로 조회 후 판단:
- **시간 변화** → 옛 주장 `superseded` + `valid_until`, 새 주장 `supersedes`. (conventions 4-A)
- **진짜 불일치** → 양쪽 `contested` + 상호 `contradicts`. (conventions 4-B)
- **중복** → 새 주장 만들지 말고 기존 주장의 `sources`에 출처 추가, confidence 재평가.

### 4. 토픽 뷰 조립
`30-ledger/topics/{topic}.md`를 주장들로부터 (재)생성:
- active 주장으로 개요 합성, **모든 문장에 `[^clm-id]` 각주**.
- contested 있으면 "쟁점" 섹션, superseded 있으면 "타임라인" 섹션.

### 5. 인덱스·라우터 갱신
- `indexes/by-topic.md`, `by-confidence.md`, `by-time.md` 갱신.
- 필요 시 `index.md`(라우터) 보강. 인덱스가 ≥50K 토큰이면 샤딩.

### 6. 원본 이동
처리한 소스를 `10-inbox/` → `20-raw/`로 이동 (불변 보관). frontmatter `status: compiled`.

### 7. 로그 & 보고
`_meta/`에 compile 로그 1줄 추가. 사용자에게: 추출한 주장 수, 새 토픽, 감지한 모순/승계를 요약.

## 규칙
- 출처 없는 주장 금지. raw 수정 금지. 사실 덮어쓰기 금지.
- 의심스러운 단언은 `confidence: low`로 남기고 audit가 잡게 둔다.
