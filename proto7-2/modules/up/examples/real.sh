#!/usr/bin/env bash
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
HERE=$(cd "$(dirname "$0")" && pwd)
TOP=$(cd "$HERE/../../.." && pwd)
MODEL=${MODEL:-${1:-chatgpt-gpt-6-sol-high}}
OUTDIR=${OUTDIR:-${2:-$HERE/real-evidence}}
HOUSE=$(mktemp -d /tmp/aos-up-real.XXXXXX)
DAEMON=
cleanup() {
  if [[ -n "$DAEMON" ]]; then
    python3 "$TOP/bin/aos7-ctl" daemon "$HOUSE" stop --kill >/dev/null || true
    wait "$DAEMON" || true
  fi
}
trap cleanup EXIT
python3 "$HERE/brain_node.py" "$HOUSE/bob" --model "$MODEL"
python3 "$TOP/bin/aos7-ctl" daemon "$HOUSE" register bob >/dev/null
python3 "$TOP/bin/aos7-daemon" "$HOUSE" >"$HOUSE/daemon.log" 2>&1 &
DAEMON=$!
python3 - "$TOP" "$HOUSE/bob" "$OUTDIR" "$MODEL" <<'PY'
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
top, node, out = map(Path, sys.argv[1:4])
started = time.time()
p = subprocess.run([sys.executable, str(top / 'modules/up/aos7_up_brain.py'), 'ask', str(node),
                    '用一句話說明你是誰、你的工作簿在哪', '--wait', '300'], capture_output=True, text=True)
seconds = time.time() - started
print(p.stdout, end='')
if p.returncode or ' 回信（' not in p.stdout:
    raise SystemExit('沒拿到回信。怎麼辦：看 aos7-up status 的 AI 那行')
receipts = list(node.glob('llmcall/*/*/receipt.json'))
if len(receipts) != 1:
    raise SystemExit('沒拿到完整回條。怎麼辦：看 aos7-up status 的 AI 那行')
out.mkdir(parents=True, exist_ok=True)
shutil.copyfile(receipts[0], out / 'receipt.json')
shutil.copyfile(node / 'brain/reply.md', out / 'reply.md')
r = json.loads(receipts[0].read_text())
status = 'BLOCKED' if '（BLOCKED）' in p.stdout else 'DONE'
(out / 'README.md').write_text('模型 %s，%s，%s token，%.3f 秒。\n' %
                              (sys.argv[4], status, (r.get('usage') or {}).get('total_tokens', '未知'), seconds), encoding='utf-8')
print('證據：' + str(out))
print('brain/：' + ', '.join(sorted(p.name for p in (node / 'brain').iterdir())))
PY
