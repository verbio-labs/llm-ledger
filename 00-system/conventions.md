# Conventions — LLM Ledger Operating Spec

> 이 문서는 LLM이 원장(ledger)을 쓰고 유지할 때 따르는 **단일 진실 규약**입니다.
> 사람과 LLM이 함께 진화시킵니다. 충돌 시 이 문서가 우선합니다.

---

## 0. 핵심 원칙 (Why this exists)

원본 [LLM Wiki(Karpathy 패턴)](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)는
원자 단위가 **합성된 산문 페이지**였습니다. 이 때문에 세 가지가 구조적으로 불가능했습니다.

1. **출처 추적** — "이 문장은 누가, 어느 자료에서 한 말인가?"
2. **시간 추적** — "이게 *언제부터* 사실이었고, *아직도* 사실인가?"
3. **모순 처리** — 새 자료가 옛 내용과 충돌하면 조용히 덮어써져 과거가 사라짐.

LLM Ledger는 원자 단위를 **주장(Claim)**으로 바꿉니다. 모든 사실은 출처·신뢰도·유효기간을
가진 추적 가능한 레코드입니다. 토픽 페이지는 더 이상 *원본*이 아니라 주장들을 조립한 **뷰(view)**입니다.

> **위키는 가변 산문이고, 원장은 추가 전용(append-only)·감사 가능(auditable)합니다.**
> 우리는 사실을 *덮어쓰지* 않습니다 — *승계(supersede)*하고 과거를 보존합니다.

토큰 효율성(원본의 강점)은 유지합니다: `index.md`는 카탈로그가 아니라 **라우터**이고,
주장은 신뢰도·주제별로 인덱싱되어 질문당 읽는 토큰을 일정하게 유지합니다.

---

## 1. 4-Layer 데이터 흐름

| 레이어 | 폴더 | 소유 | 가변성 |
| --- | --- | --- | --- |
| **inbox** (미처리 대기열) | `10-inbox/` | 사람이 넣음 | 처리 후 비워짐 |
| **raw** (불변 원본) | `20-raw/` | compile이 채움 | 불변, 읽기 전용 |
| **ledger** (합성된 진실) | `30-ledger/` | LLM이 전적으로 씀 | 추가 전용 |
| **schema** (운영 규약) | `CLAUDE.md` + 이 파일 | 사람·LLM 공동 | 신중히 진화 |

```
10-inbox/ ──/ingest──> (수집)
          ──/compile──> 주장 추출 → 30-ledger/claims/  (원자 사실)
                        토픽 뷰 조립 → 30-ledger/topics/
                        라우터·인덱스·aliases 갱신
                        원본을 20-raw/ 로 이동 (불변 보관)

/query   ──> Phase A 라우팅 → Phase B 주장 회수 → 인용 합성 → 50-queries/ 파일백
/audit   ──> 모순·저신뢰·고아·인덱스 정합·시간 일관성 점검
/timeline──> 한 주제/엔티티의 주장을 시간순으로 펼쳐 변화 추적
```

규칙: **inbox에 있으면 미처리, raw로 갔으면 처리 완료.**

---

## 2. 주장(Claim) — 원자 단위

주장은 `30-ledger/claims/`에 한 파일당 하나, 또는 토픽별 묶음 파일로 저장합니다.
각 주장은 다음 frontmatter를 가집니다.

```yaml
---
id: clm-2026-0001          # 불변 ID. clm-{연도}-{4자리 일련}
statement: "나폴레옹은 1799년 브뤼메르 쿠데타로 권력을 잡았다."
topic: napoleon            # 정본 토픽 키 (aliases.md 기준)
type: event                # fact | event | definition | claim | metric | relation
sources:                   # 출처 = provenance (필수, 최소 1개)
  - ref: raw/napoleon-britannica.md
    quote: "Napoleon seized power in the coup of 18 Brumaire (1799)."
    locator: "§3"
confidence: high           # high | medium | low | contested
valid_from: 1799-11-09     # 이 사실이 성립한 시점 (없으면 unknown)
valid_until: null          # 더 이상 사실이 아닌 시점 (null = 현재 유효)
status: active             # active | superseded | contested | retracted
supersedes: null           # 이 주장이 대체한 이전 주장 id
superseded_by: null        # 이 주장을 대체한 이후 주장 id
contradicts: []            # 충돌하는 다른 주장 id 목록
relations: []              # ["caused:clm-...", "part_of:clm-..."] 타입 관계
created: 2026-06-19
updated: 2026-06-19
---
```

### 2.1 주장 작성 규칙
- **원자성**: 한 주장은 하나의 검증 가능한 단언만. "그리고/그러나"로 두 사실이 붙으면 분리.
- **출처 필수**: `sources`가 빈 주장은 만들지 않습니다. LLM의 일반지식은 출처가 아닙니다
  (정 필요하면 `ref: model-prior`로 명시하고 `confidence: low`).
- **인용 보존**: 가능하면 원문 `quote`를 그대로. 번역·요약은 statement에만.
- **statement는 자기완결적**: 페이지 맥락 없이 읽어도 뜻이 통해야 함.

---

## 3. 신뢰도(Confidence) 산정

신뢰도는 LLM이 매 compile/audit 시 다음을 종합해 부여합니다.

| 등급 | 기준 |
| --- | --- |
| `high` | 2개 이상 독립 출처가 동의 / 1차 출처 / 정량·검증 가능 |
| `medium` | 단일 신뢰 출처 / 2차 출처 / 합리적 추론 |
| `low` | 약한 출처 / 모델 추정 / 오래되어 갱신 필요 |
| `contested` | 출처들이 서로 충돌 (3절 모순 처리 참조) |

> 신뢰도는 **가변**입니다. 새 출처가 들어오면 등급이 오르내릴 수 있고, 변경 시 `updated`를 갱신합니다.

---

## 4. 모순 처리 (덮어쓰지 않기)

새 자료가 기존 주장과 충돌하면 — **이것이 원본 위키와의 핵심 차이** — 조용히 덮어쓰지 않습니다.

**케이스 A: 사실이 시간에 따라 바뀜 (supersession)**
- 옛 주장: `valid_until`을 변경 시점으로 채우고 `status: superseded`, `superseded_by: 새 id`.
- 새 주장: `valid_from`을 채우고 `supersedes: 옛 id`, `status: active`.
- 과거는 90-archive로 옮기지 않고 ledger에 남깁니다 (`/timeline`이 쓰므로).

**케이스 B: 출처들이 진짜로 불일치 (contested)**
- 충돌하는 주장 모두 `status: contested`, 서로를 `contradicts`에 기재.
- 어느 쪽도 삭제하지 않음. 토픽 뷰에 "⚠ 이견 있음"으로 양쪽을 노출.
- `/audit`가 contested를 보고서로 올려 사람이 판단하도록 함.

**케이스 C: 명백한 오류 (retraction)**
- `status: retracted`, 이유를 frontmatter `note`에 기록. 삭제하지 않고 흔적을 남김.

---

## 5. 토픽 뷰 (Topic = view over claims)

`30-ledger/topics/{topic}.md`는 원본이 아니라 주장들을 **조립한 읽기용 뷰**입니다.

```markdown
---
topic: napoleon
canonical: "나폴레옹 보나파르트"
type: entity              # entity | concept
claim_refs: [clm-2026-0001, clm-2026-0004, ...]
updated: 2026-06-19
---

# 나폴레옹 보나파르트

## 개요
{high-confidence active 주장들로 합성한 산문. 각 문장 끝에 [^clm-id] 각주.}

## 쟁점 (contested)
{contested 주장이 있으면 양쪽 입장 + 출처.}

## 타임라인
{valid_from 순으로 주요 변화. 상세는 /timeline.}

[^clm-2026-0001]: napoleon-britannica.md §3 (confidence: high)
```

규칙:
- 뷰의 **모든 문장은 주장으로 환원 가능**해야 함. 각주 없는 단언 금지.
- 뷰는 `status: active`를 기본 노출, `superseded`는 타임라인 섹션에만, `contested`는 쟁점 섹션에.
- 뷰는 언제든 주장으로부터 **재생성 가능**. 손상되면 claims가 진실의 원천.

---

## 6. 라우터 = 인덱스 (토큰 일정성)

원본의 핵심 강점을 계승·강화합니다. `index.md`는 전체 목록이 아니라
**"질문 의도 → 어느 인덱스/샤드를 펼칠지" 결정하는 라우터(MOC)**입니다.

- **2단 라우팅**: Route(라우터 + `aliases.md`만 읽고 대상 샤드 결정) → Search(지정 샤드만 펼침).
- **인덱스 종류** (`30-ledger/indexes/`):
  - `by-topic.md` — 토픽 → claim_refs
  - `by-confidence.md` — contested/low 주장 빠른 조회 (audit용)
  - `by-time.md` — valid_from 정렬 (timeline용)
- **정본화(canonicalization)**: 표기 흔들림(나폴레옹/Napoleon/보나파르트)을 정본명 1개로.
  정본명이 라우팅 키이며 `aliases.md`가 매핑을 보관.
- **샤딩**: 인덱스가 ≥50K 토큰이면 정본명 첫 글자로 분할.
- **성장 경로**: 규모가 커지면 `.rag`(BM25/벡터)를 1순위 회수로 붙이고 라우터→샤드는 폴백으로 유지.

---

## 7. Provenance & 감사 가능성

- 모든 주장은 `20-raw/`의 불변 원본을 가리킵니다. raw가 진실의 마지막 보루.
- raw 파일은 절대 수정하지 않습니다 (오타도). 잘못됐으면 새 주장으로 정정.
- 주장의 생애(생성→신뢰도변경→승계→은퇴)는 frontmatter에 흔적이 남습니다.
- `_meta/`에 compile/audit 실행 로그를 남겨 "언제 무엇이 들어왔나"를 추적합니다.

---

## 8. ID & 명명 규칙

- 주장 ID: `clm-{YYYY}-{NNNN}` (연도별 일련). 한 번 부여하면 불변.
- 토픽 키: 소문자 슬러그 (`napoleon`, `transformer-architecture`).
- raw 파일: `{topic}-{source-slug}.md`.
- 쿼리 파일백: `50-queries/{YYYY-MM-DD}-{slug}.md`.

---

## 9. 품질 규칙 (LLM이 항상 지킴)

1. 출처 없는 주장을 만들지 않는다.
2. 사실을 덮어쓰지 않는다 — 승계하거나 contested로 둔다.
3. 토픽 뷰의 모든 단언에 각주를 단다.
4. 정본명을 먼저 확인하고(aliases) 새 표기를 함부로 만들지 않는다.
5. 불확실하면 `confidence: low`로 명시하고 audit가 잡게 둔다.
6. raw는 읽기만, 수정 금지.
7. 큰 작업 후 인덱스 정합성을 갱신한다.
