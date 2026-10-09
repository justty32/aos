#!/usr/bin/env bash
# 從任意目錄可跑；只送一次，保留暫存 node 供檢查。
set -eu
LLMCALL_EXAMPLE="$(cd -- "$(dirname -- "$0")" && pwd)"
P="$(cd -- "$LLMCALL_EXAMPLE/../../../.." && pwd)"
mkdir -p -- "${1:-./evidence}"
LLMCALL_EVIDENCE="$(cd -- "${1:-./evidence}" && pwd)"
LLMCALL_DEMO="$(mktemp -d /tmp/aos7-litellm-demo.XXXXXX)"
mkdir -p "$LLMCALL_DEMO/.aos" "$LLMCALL_DEMO/budget/llm"
cp "$LLMCALL_EXAMPLE/grant.json" "$LLMCALL_DEMO/budget/llm/grant.json"
printf '%s\n' '{"round":5,"open":false}' > "$LLMCALL_DEMO/.aos/round.json"
(
  cd "$LLMCALL_DEMO"
  python3 "$P/packs/budget/bin/aos7-budget" ledger budget/llm &
  LLMCALL_LEDGER_PID=$!
  trap 'kill "$LLMCALL_LEDGER_PID" 2>/dev/null || true; wait "$LLMCALL_LEDGER_PID" 2>/dev/null || true' EXIT
  python3 "$P/packs/budget/bin/aos7-budget" init budget/llm
  LLMCALL_RC=0
  python3 "$P/packs/llmcall/bin/aos7-llmcall" call budget/llm --holder author --call demo-c1 --request "$LLMCALL_EXAMPLE/req.json" --reserve 1000000 > "$LLMCALL_EVIDENCE/receipt.stdout.json" || LLMCALL_RC=$?
  cat "$LLMCALL_EVIDENCE/receipt.stdout.json"
  python3 "$P/packs/llmcall/bin/aos7-llmcall" status budget/llm --holder author --call demo-c1 > "$LLMCALL_EVIDENCE/status.json"
  python3 "$P/packs/budget/bin/aos7-budget" status budget/llm > "$LLMCALL_EVIDENCE/budget-status.json"
  if [ -f llmcall/llm/demo-c1/raw.json ]; then
    cp llmcall/llm/demo-c1/raw.json "$LLMCALL_EVIDENCE/raw.json"
  fi
  printf '證據：%s\n暫存 node：%s\ncall 退出碼：%s\n' "$LLMCALL_EVIDENCE" "$LLMCALL_DEMO" "$LLMCALL_RC"
  exit "$LLMCALL_RC"
)
