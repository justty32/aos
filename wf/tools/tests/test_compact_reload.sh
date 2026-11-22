#!/bin/bash
# test_compact_reload.sh — 在 repo 外的暫存夾搭一棵小樹測 compact_reload.sh 的「HANDOFF 空時印 progress open 條目」：一般字串、what／next 寫成 $ref（印 md 第一行加路徑）、$ref 指到不在的檔；不碰來源 repo
# 用法：test_compact_reload.sh <repo 外的暫存夾>   每次開一個新的 run-<時間> 子夾，不刪任何東西
set -u
[ -n "${BASH_VERSION:-}" ] || { echo "not bash" >&2; exit 1; }
TOOL=$(dirname "$(readlink -f "$0")")/../compact_reload.sh
WORK=$(readlink -f "${1:?work folder}")
RUN="$WORK/run-$(date +%Y%m%d-%H%M%S)-$$"
T="$RUN/tree"
mkdir -p "$T/wf/tools" "$T/wf/workflows/common" "$T/wf/progress" || exit 1
cp -p "$TOOL" "$T/wf/tools/compact_reload.sh"
printf '# user 測試\n' > "$T/wf/workflows/common/user.md"
printf '# HANDOFF\n\n沒有條目。\n' > "$T/wf/HANDOFF.md"
printf '# 長條目的一句話\n\n很長的內文。\n' > "$T/wf/progress/long.md"
printf '下一步的一句話\n' > "$T/wf/progress/long-next.md"
cat > "$T/wf/progress.json" <<'J'
{
  "_description": "t",
  "open": {
    "plain": {"title": "一般條目", "status": "open", "flow": "", "what": "短現況", "next": "", "see": ["[a](a.md)"], "since": "2026-11-22"},
    "long": {"title": "長條目", "status": "等使用者", "flow": "", "what": {"$ref": "progress/long.md"}, "next": {"$ref": "progress/long-next.md"}, "see": [], "since": "2026-11-22"},
    "gone": {"title": "壞指標", "status": "open", "flow": "", "what": {"$ref": "progress/nope.md"}, "next": "", "see": [], "since": "2026-11-22"}
  }
}
J
OUT="$RUN/out.txt"
env -u CLAUDE_PROJECT_DIR sh "$T/wf/tools/compact_reload.sh" > "$OUT" 2>&1
PASS=0; FAIL=0
check() { local d="$1"; shift; if "$@"; then PASS=$((PASS+1)); echo "  ok   $d"; else FAIL=$((FAIL+1)); echo "  FAIL $d"; fi; }
check "falls back to progress when HANDOFF has no entry" grep -q 'progress.json 的 open 條目' "$OUT"
check "plain entry printed as before" grep -qxF -- '- open｜一般條目：短現況' "$OUT"
check "ref what → first line without '#', plus path" grep -qxF -- '- 等使用者｜長條目：長條目的一句話 (full text: wf/progress/long.md)' "$OUT"
check "ref next → first line plus path" grep -qxF -- '  next: 下一步的一句話 (full text: wf/progress/long-next.md)' "$OUT"
check "missing ref file → says missing" grep -qxF -- '- open｜壞指標：(missing: wf/progress/nope.md)' "$OUT"
check "no python dict literal leaks" bash -c "! grep -qF \"{'\\\$ref'\" '$OUT'"
echo
echo "run folder: $RUN"
echo "PASS $PASS  FAIL $FAIL"
[ $FAIL = 0 ]
