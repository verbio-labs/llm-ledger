#!/usr/bin/env bash
# SessionStart 안내. 외부 의존 없음.
inbox=$(find 10-inbox -type f ! -name '.gitkeep' 2>/dev/null | wc -l | tr -d ' ')
claims=$(find 30-ledger/claims -type f ! -name '.gitkeep' 2>/dev/null | wc -l | tr -d ' ')
cat <<MSG
📒 LLM Ledger — 검증 가능한 시간축 지식 원장
원자 단위는 '주장(claim)'입니다. 출처·신뢰도·유효기간을 갖고, 사실은 덮어쓰지 않고 승계됩니다.

상태: inbox에 미처리 소스 ${inbox}개 · 원장에 주장 ${claims}개

커맨드:
  /ingest <소스>    자료를 10-inbox/에 수집
  /compile          inbox → 주장 추출 + 토픽 뷰 + 인덱스 갱신
  /query <질문>     2단 라우팅 회수 + 인용 합성
  /audit            모순·저신뢰·시간 일관성 점검
  /timeline <주제>  지식이 시간에 따라 어떻게 변했는지 추적

규약: 00-system/conventions.md (단일 진실)
MSG
