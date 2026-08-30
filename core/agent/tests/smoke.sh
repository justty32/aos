#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(cd "$SCRIPT_DIR/../../.." && pwd)
TEMP=$(mktemp -d)
W="$TEMP/bob"
mkdir -p "$W"
trap 'rm -rf -- "${TEMP:?}"' EXIT
export PATH="$REPO/build/bin:$PATH"

if ! command -v aos >/dev/null || ! aos --help 2>&1 | grep -Eq '^  agent[[:space:]]'; then
    echo "aos agent 尚未實作，跳過"
    exit 0
fi

check_every_step() {
    python3 - "$1" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
inst = json.loads(path.read_text(encoding="utf-8"))
assert inst == {"argv": ["aos", "agent", "step"]}, inst
print("  every:", path.name)
PY
}

echo "[1/5] 初始化 bob 的資料夾世界：$W"
(
    cd "$W"
    aos agent init
)

echo "[2/5] init 已寫入 every，inbox 保持空白"
check_every_step "$W/.aos/every/agent-bob.json"
test -z "$(find "$W/.aos/inbox" -maxdepth 1 -name '*.json' -print -quit)"

echo "[3/5] 用替身 loop 推進三回合"
python3 "$SCRIPT_DIR/fake_loop.py" "$W" --step 3 --interval 10

echo "[4/5] every 在每回合產生一條新的 step，原檔保留"
for turn in 1 2 3; do
    test -f "$W/.aos/batch/$turn/insts/agent-bob-$turn.json"
    echo "  turn $turn: agent-bob-$turn"
done
check_every_step "$W/.aos/every/agent-bob.json"
test -z "$(find "$W/.aos/inbox" -maxdepth 1 -name '*.json' -print -quit)"

echo "[5/5] loop state 已鏡射 bob 的 status.json"
python3 - "$W/.aos/state.json" <<'PY'
import json
import sys

state = json.load(open(sys.argv[1], encoding="utf-8"))
assert state["agents"].get("bob"), state
print(json.dumps(state["agents"]["bob"], ensure_ascii=False))
PY
echo "smoke OK"
