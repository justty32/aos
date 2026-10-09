#!/usr/bin/env bash
# 手動一次真 AI；不在測試套裡跑，node 與證據均保留。
set -eu
if [ "$#" -ne 1 ]; then
  printf '用法：%s <輸出資料夾>\n' "$0" >&2
  exit 2
fi
COMPACT_EXAMPLE="$(cd -- "$(dirname -- "$0")" && pwd)"
P="$(cd -- "$COMPACT_EXAMPLE/../../.." && pwd)"
mkdir -p -- "$1"
COMPACT_EVIDENCE="$(cd -- "$1" && pwd)"
COMPACT_DEMO="$(mktemp -d /tmp/aos7-compact-real.XXXXXX)"
export COMPACT_DEMO
mkdir -p "$COMPACT_DEMO/.aos" "$COMPACT_DEMO/budget/llm" "$COMPACT_DEMO/notes"
cp "$COMPACT_EXAMPLE/real_journal.jsonl" "$COMPACT_DEMO/notes/journal.jsonl"
cp "$COMPACT_DEMO/notes/journal.jsonl" "$COMPACT_EVIDENCE/journal-before.jsonl"
python3 - <<'PY'
import json, os
from pathlib import Path
n = Path(os.environ['COMPACT_DEMO'])
grant = dict(v=1, grant='compact-real', budget='llm', holder='compact', resource='llm.tokens',
             gateway='llm.litellm', amount=10000000, clock='completed_tock', until=1000, delegate=False)
grant['from'] = 0
(n / 'budget/llm/grant.json').write_text(json.dumps(grant))
(n / '.aos/round.json').write_text('{"round":5,"open":false}')
(n / 'compact.json').write_text(json.dumps(dict(files=['notes/journal.jsonl'], keep_recent=0,
    llm=dict(gateway='litellm', reserve=1000000, deadline=900))))
PY
(
  cd "$COMPACT_DEMO"
  python3 "$P/packs/budget/bin/aos7-budget" ledger budget/llm &
  COMPACT_LEDGER_PID=$!
  trap 'kill "$COMPACT_LEDGER_PID" 2>/dev/null || true; wait "$COMPACT_LEDGER_PID" 2>/dev/null || true' EXIT
  python3 "$P/packs/budget/bin/aos7-budget" init budget/llm
  COMPACT_RC=0
  timeout 1000 python3 "$P/modules/compact/aos7-compact" now "$COMPACT_DEMO" --force > "$COMPACT_EVIDENCE/compact.stdout.json" || COMPACT_RC=$?
  cat "$COMPACT_EVIDENCE/compact.stdout.json"
  cp notes/journal.jsonl "$COMPACT_EVIDENCE/journal-after.jsonl"
  if [ -f compact/log.jsonl ]; then cp compact/log.jsonl "$COMPACT_EVIDENCE/log.jsonl"; fi
  for COMPACT_CALL in llmcall/llm/*; do
    [ -d "$COMPACT_CALL" ] || continue
    for COMPACT_FILE in receipt.json raw.json request.json; do
      if [ -f "$COMPACT_CALL/$COMPACT_FILE" ]; then cp "$COMPACT_CALL/$COMPACT_FILE" "$COMPACT_EVIDENCE/$COMPACT_FILE"; fi
    done
  done
  python3 "$P/packs/budget/bin/aos7-budget" status budget/llm > "$COMPACT_EVIDENCE/budget-status.json"
  printf '證據：%s\n暫存 node：%s\ncompact 退出碼：%s\n' "$COMPACT_EVIDENCE" "$COMPACT_DEMO" "$COMPACT_RC"
  exit "$COMPACT_RC"
)
