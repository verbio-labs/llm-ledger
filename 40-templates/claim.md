---
id: clm-YYYY-NNNN
statement: "한 문장의 검증 가능한 단언 (자기완결적)"
topic: topic-slug
type: fact            # fact | event | definition | claim | metric | relation
sources:
  - ref: 20-raw/topic-source.md
    quote: "원문 인용 (가능하면 그대로)"
    locator: "§/페이지/타임스탬프"
confidence: medium    # high | medium | low | contested
valid_from: null      # 사실이 성립한 시점 (YYYY-MM-DD 또는 unknown)
valid_until: null     # 더 이상 사실이 아닌 시점 (null = 현재 유효)
status: active        # active | superseded | contested | retracted
supersedes: null
superseded_by: null
contradicts: []
relations: []         # ["caused:clm-...", "part_of:clm-...", "located_in:clm-..."]
created: YYYY-MM-DD
updated: YYYY-MM-DD
note: null            # retracted/contested 사유 등
---

<!-- 본문은 선택. 추가 맥락이나 미묘한 뉘앙스가 있으면 여기에. statement가 본질. -->
