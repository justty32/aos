#!/usr/bin/env bash
# 真模型實跑；不在測試套內。暫存 root 與證據保留供人審查。
set -euo pipefail
if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo '用法：run.sh MODEL [OUTDIR]' >&2
  exit 2
fi
AUTHOR_MODEL=$1
AUTHOR_EXAMPLE="$(cd -- "$(dirname -- "$0")" && pwd)"
AUTHOR_PACK="$(cd -- "$AUTHOR_EXAMPLE/../.." && pwd)"
AUTHOR_TOP="$(cd -- "$AUTHOR_PACK/../.." && pwd)"
# 模型名可能含 /，預設目錄只保留安全字元。
AUTHOR_SAFE_MODEL="$(python3 -c 'import re,sys; print(re.sub(r"[^A-Za-z0-9_-]", "_", sys.argv[1]))' "$AUTHOR_MODEL")"
AUTHOR_OUT=${2:-./evidence-$AUTHOR_SAFE_MODEL}
mkdir -p -- "$AUTHOR_OUT"
AUTHOR_OUT="$(cd -- "$AUTHOR_OUT" && pwd)"
if [[ -n "$(ls -A -- "$AUTHOR_OUT")" ]]; then
  echo 'OUTDIR 必須為空，避免混入上次證據' >&2
  exit 2
fi
AUTHOR_ROOT="$(mktemp -d /tmp/aos7-author-llm.XXXXXX)"
AUTHOR_LEDGER_PID=''
AUTHOR_DAEMON_PID=''
AUTHOR_STARTED=''
AUTHOR_SECONDS=''
finish() {
  AUTHOR_RC=$?
  trap - EXIT INT TERM
  if [[ -n "$AUTHOR_DAEMON_PID" ]]; then
    python3 "$AUTHOR_TOP/bin/aos7-ctl" daemon "$AUTHOR_ROOT" stop --kill > "$AUTHOR_OUT/daemon-stop.json" 2> "$AUTHOR_OUT/daemon-stop.stderr" || true
    for _ in $(seq 50); do kill -0 "$AUTHOR_DAEMON_PID" 2>/dev/null || break; sleep 0.2; done
    kill -TERM "$AUTHOR_DAEMON_PID" 2>/dev/null || true
    sleep 1
    kill -KILL "$AUTHOR_DAEMON_PID" 2>/dev/null || true
    wait "$AUTHOR_DAEMON_PID" 2>/dev/null || true
  fi
  if [[ -n "$AUTHOR_LEDGER_PID" ]]; then
    kill "$AUTHOR_LEDGER_PID" 2>/dev/null || true
    wait "$AUTHOR_LEDGER_PID" 2>/dev/null || true
  fi
  if [[ -n "$AUTHOR_STARTED" && -z "$AUTHOR_SECONDS" ]]; then
    AUTHOR_SECONDS="$(python3 -c 'import time,sys; print(round(time.time()-float(sys.argv[1]),3))' "$AUTHOR_STARTED")"
  fi
  python3 "$AUTHOR_EXAMPLE/summary.py" "$AUTHOR_OUT" "$AUTHOR_MODEL" "${AUTHOR_SECONDS:-}" "$AUTHOR_ROOT"
  printf '證據：%s\n暫存 root：%s\n' "$AUTHOR_OUT" "$AUTHOR_ROOT"
  exit "$AUTHOR_RC"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
mkdir -p "$AUTHOR_ROOT/llm/.aos" "$AUTHOR_ROOT/llm/budget/llm" "$AUTHOR_ROOT/work/.aos"
python3 - "$AUTHOR_ROOT" <<'PY'
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
(root / 'llm/.aos/round.json').write_text(json.dumps({'round': 5, 'open': False}))
(root / 'llm/budget/llm/grant.json').write_text(json.dumps({
    'v': 1, 'grant': 'author-llm-demo', 'budget': 'llm', 'holder': 'author',
    'resource': 'llm.tokens', 'gateway': 'llm.litellm', 'amount': 100000000,
    'clock': 'completed_tock', 'from': 0, 'until': 1000000, 'delegate': False}))
PY
cd "$AUTHOR_ROOT/llm"
python3 "$AUTHOR_TOP/packs/budget/bin/aos7-budget" init budget/llm > "$AUTHOR_OUT/budget-init.json" 2> "$AUTHOR_OUT/budget-init.stderr"
python3 "$AUTHOR_TOP/packs/budget/bin/aos7-budget" ledger budget/llm > "$AUTHOR_OUT/ledger.stdout" 2> "$AUTHOR_OUT/ledger.stderr" &
AUTHOR_LEDGER_PID=$!
cd "$AUTHOR_ROOT/work"
cp "$AUTHOR_TOP/packs/step/examples/csv/data.csv" data.csv
python3 "$AUTHOR_PACK/bin/aos7-author" register "$AUTHOR_PACK/examples/csv-request/request.json" > "$AUTHOR_OUT/register.json" 2> "$AUTHOR_OUT/register.stderr"
AUTHOR_STARTED="$(python3 -c 'import time; print(time.time())')"
AUTHOR_PROPOSE_RC=0
python3 "$AUTHOR_PACK/bin/aos7-author" propose csv1 --llm "$AUTHOR_MODEL" --budget ../llm/budget/llm > "$AUTHOR_OUT/propose.json" 2> "$AUTHOR_OUT/propose.stderr" || AUTHOR_PROPOSE_RC=$?
AUTHOR_SECONDS="$(python3 -c 'import time,sys; print(round(time.time()-float(sys.argv[1]),3))' "$AUTHOR_STARTED")"
# 即使 propose 不過，也保存 llmcall 證據與壞候選原文帳。
python3 "$AUTHOR_EXAMPLE/summary.py" "$AUTHOR_OUT" "$AUTHOR_MODEL" "$AUTHOR_SECONDS" "$AUTHOR_ROOT" --collect-only
[[ "$AUTHOR_PROPOSE_RC" == 0 ]] || exit "$AUTHOR_PROPOSE_RC"
python3 "$AUTHOR_PACK/bin/aos7-author" publish csv1 > "$AUTHOR_OUT/publish.json" 2> "$AUTHOR_OUT/publish.stderr"
AUTHOR_JOB="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["job"])' "$AUTHOR_OUT/propose.json")"
python3 "$AUTHOR_TOP/bin/aos7-ctl" daemon "$AUTHOR_ROOT" register work > "$AUTHOR_OUT/daemon-register.json" 2> "$AUTHOR_OUT/daemon-register.stderr"
python3 "$AUTHOR_TOP/bin/aos7-daemon" "$AUTHOR_ROOT" > "$AUTHOR_OUT/daemon.stdout" 2> "$AUTHOR_OUT/daemon.stderr" &
AUTHOR_DAEMON_PID=$!
AUTHOR_ENDED=0
AUTHOR_UNTIL=$((SECONDS + 120))
while ((SECONDS < AUTHOR_UNTIL)); do
  sleep 1
  AUTHOR_LEFT=$((AUTHOR_UNTIL - SECONDS))
  ((AUTHOR_LEFT > 0)) || break
  timeout "$AUTHOR_LEFT" python3 "$AUTHOR_TOP/packs/step/bin/aos7-step" status "jobs/$AUTHOR_JOB" > "$AUTHOR_OUT/step-status.json" 2> "$AUTHOR_OUT/step-status.stderr" || true
  if python3 - "$AUTHOR_OUT/step-status.json" <<'PY'
import json, sys
try:
    ended = json.load(open(sys.argv[1])).get('phase') == 'ended'
except (ValueError, OSError):
    ended = False
sys.exit(0 if ended else 1)
PY
  then
    AUTHOR_ENDED=1
    break
  fi
done
[[ "$AUTHOR_ENDED" == 1 ]] || exit 4
AUTHOR_ANSWER_RC=0
python3 "$AUTHOR_PACK/bin/aos7-author" answer csv1 > "$AUTHOR_OUT/answer.json" 2> "$AUTHOR_OUT/answer.stderr" || AUTHOR_ANSWER_RC=$?
# answer 寫回 verdict，close 前取最後版本。
python3 "$AUTHOR_EXAMPLE/summary.py" "$AUTHOR_OUT" "$AUTHOR_MODEL" "$AUTHOR_SECONDS" "$AUTHOR_ROOT" --collect-only
[[ "$AUTHOR_ANSWER_RC" == 0 ]] || exit "$AUTHOR_ANSWER_RC"
python3 "$AUTHOR_TOP/packs/step/bin/aos7-step" close "jobs/$AUTHOR_JOB" > "$AUTHOR_OUT/step-close.json" 2> "$AUTHOR_OUT/step-close.stderr"
python3 "$AUTHOR_PACK/bin/aos7-author" close csv1 > "$AUTHOR_OUT/close.json" 2> "$AUTHOR_OUT/close.stderr"
