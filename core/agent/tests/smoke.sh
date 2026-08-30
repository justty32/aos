#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(cd "$SCRIPT_DIR/../../.." && pwd)
W=$(mktemp -d)
trap 'rm -rf -- "${W:?}"' EXIT
export PATH="$REPO/build/bin:$PATH"

if ! command -v aos >/dev/null || ! aos --help 2>&1 | grep -Eq '^  agent[[:space:]]'; then
    echo "aos agent 尚未實作，跳過"
    exit 0
fi

check_inbox_step() {
    python3 - "$1" "$2" <<'PY'
import json
import sys
from pathlib import Path

matches = []
for path in Path(sys.argv[1]).glob("*.json"):
    inst = json.loads(path.read_text(encoding="utf-8"))
    if inst.get("id") == sys.argv[2] and inst.get("argv", [])[:3] == ["aos", "agent", "step"]:
        matches.append(path.name)
assert matches, f"找不到 {sys.argv[2]} step"
print("  inbox:", matches[0])
PY
}

echo "[1/5] 初始化 bob 的資料夾世界：$W"
aos agent init "$W" --name bob

echo "[2/5] init 已在 inbox 投遞第一條 step"
check_inbox_step "$W/.aos/inbox" agent-bob-0

echo "[3/5] 用替身 loop 推進三回合"
python3 "$SCRIPT_DIR/fake_loop.py" "$W" --step 3 --interval 10

echo "[4/5] 每回合都收到前一回合自我投遞的新 step"
for turn in 1 2 3; do
    id=$((turn - 1))
    test -f "$W/.aos/batch/$turn/insts/agent-bob-$id.json"
    echo "  turn $turn: agent-bob-$id"
done
check_inbox_step "$W/.aos/inbox" agent-bob-3

echo "[5/5] loop state 已鏡射 bob 的 status.json"
python3 - "$W/.aos/state.json" <<'PY'
import json
import sys

state = json.load(open(sys.argv[1], encoding="utf-8"))
assert state["agents"].get("bob"), state
print(json.dumps(state["agents"]["bob"], ensure_ascii=False))
PY
echo "smoke OK"
