#!/usr/bin/env bash
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
UP="$PWD/proto7-2/modules/up/aos7-up"
if [[ ! -f "$UP" ]]; then
  echo '請從 aos repo 根目錄跑這個範例。' >&2
  exit 2
fi
HOUSE=$(mktemp -d /tmp/aos-up-multiround.XXXXXX)
NODE="$HOUSE/bob"
cleanup() {
  if [[ -d "$HOUSE/.aosd" ]]; then
    # stop 失敗時保留房子，避免仍在跑的任務失去檔案。
    if ! python3 -B "$UP" stop "$NODE"; then
      echo "心跳尚未停乾淨，房子留在 $HOUSE" >&2
      return 1
    fi
  fi
  rm -rf -- "$HOUSE"
}
trap cleanup EXIT
ARGS=()
QUESTION='請分 8 回合做完'
WAIT=60
if [[ -n "${MODEL:-}" ]]; then
  ARGS=(--model "$MODEL")
  WAIT=900
  QUESTION='請分 5 回合整理如何開始使用 aos，每回合只做一小步；前 4 回合用「繼續：」回報，第 5 回合用「回信：」結案'
fi
python3 -B "$UP" "$NODE" -d "${ARGS[@]}"
python3 -B - "$NODE" <<'PY'
import json
from pathlib import Path
import sys
path = Path(sys.argv[1]) / '.aos/timeline.json'
cfg = json.loads(path.read_text()) if path.exists() else {}
cfg['interval_ms'] = 200
tmp = path.with_suffix('.tmp')
tmp.write_text(json.dumps(cfg))
tmp.replace(path)
PY
python3 -B "$UP" ask "$NODE" "$QUESTION" --wait "$WAIT"
python3 -B - "$PWD/proto7-2" "$HOUSE" <<'PY'
from pathlib import Path
import sys
top, house = map(Path, sys.argv[1:])
sys.path.insert(0, str(top / 'modules/mail'))
from aos7_mail import letter
letters = [letter(p) for p in (house / 'you/inbox').rglob('*.md')]
print('\n回信箱：')
for item in sorted(letters, key=lambda l: (l['at'], l['id'])):
    print(f"{item['status']}（re: {item['re']}）：{item['title']}")
print('\nSTATE 最後幾行：')
for path in sorted((house / 'bob/wf/handoffs').glob('*/STATE.md')):
    print('\n'.join(path.read_text().splitlines()[-10:]))
if not any(l['status'] == 'DONE' for l in letters):
    raise SystemExit('等完了還沒有 DONE；請看上方回信與 STATE。')
PY
