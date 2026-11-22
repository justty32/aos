#!/bin/bash
# test_compact_reload.sh — 在 repo 外的暫存夾搭一棵小樹測 compact_reload.sh：HANDOFF 空時印 progress open 條目（一般字串、$ref、壞 $ref）、頂層照貼 HANDOFF 第一條、subagent 不貼 HANDOFF／progress 改指向 $AOS_STACK/notes_path；不碰來源 repo
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
# 每次都從空環境跑（沒有 AOS_*、沒有 CLAUDE_PROJECT_DIR），要的變數自己給
run() { env -i PATH="$PATH" HOME="$HOME" "$@" sh "$T/wf/tools/compact_reload.sh"; }
run > "$OUT" 2>&1
PASS=0; FAIL=0
check() { local d="$1"; shift; if "$@"; then PASS=$((PASS+1)); echo "  ok   $d"; else FAIL=$((FAIL+1)); echo "  FAIL $d"; fi; }
check "falls back to progress when HANDOFF has no entry" grep -q 'progress.json 的 open 條目' "$OUT"
check "plain entry printed as before" grep -qxF -- '- open｜一般條目：短現況' "$OUT"
check "ref what → first line without '#', plus path" grep -qxF -- '- 等使用者｜長條目：長條目的一句話 (full text: wf/progress/long.md)' "$OUT"
check "ref next → first line plus path" grep -qxF -- '  next: 下一步的一句話 (full text: wf/progress/long-next.md)' "$OUT"
check "missing ref file → says missing" grep -qxF -- '- open｜壞指標：(missing: wf/progress/nope.md)' "$OUT"
check "no python dict literal leaks" bash -c "! grep -qF \"{'\\\$ref'\" '$OUT'"

# subagent，HANDOFF 空：不印 progress 條目，改指向自己的筆記
S="$RUN/stack"; mkdir -p "$S" || exit 1
printf 'wf/ws/p/kid/notes.md\n' > "$S/notes_path"
OUT_SE="$RUN/out-sub-empty.txt"
run AOS_PARENT_STACK=/x/parent AOS_STACK="$S" AOS_WS=/w > "$OUT_SE" 2>&1
check "subagent, HANDOFF empty: no progress entries" bash -c "! grep -qF '一般條目' '$OUT_SE' && ! grep -qF 'progress.json 的 open 條目' '$OUT_SE'"
check "subagent, HANDOFF empty: still points to own notes" grep -qxF -- 'Your own notes are /w/wf/ws/p/kid/notes.md; read them now, before anything else.' "$OUT_SE"

# 換成有條目的 HANDOFF
printf '# HANDOFF\n\n## 11-22 上層的交接\n\n上層的祕密內文。\n\n## 更舊的\n\n舊的。\n' > "$T/wf/HANDOFF.md"

# 頂層：照貼 HANDOFF 第一條，沒有 subagent 那段
OUT_TOP="$RUN/out-top.txt"
run AOS_STACK="$S" AOS_WS=/w > "$OUT_TOP" 2>&1
check "top level: HANDOFF first entry pasted" grep -qxF -- '上層的祕密內文。' "$OUT_TOP"
check "top level: only the first entry" bash -c "! grep -qF '舊的。' '$OUT_TOP'"
check "top level: no subagent sentence" bash -c "! grep -qF 'not yours' '$OUT_TOP'"
OUT_TOP2="$RUN/out-top-empty-parent.txt"
run AOS_PARENT_STACK= AOS_STACK="$S" > "$OUT_TOP2" 2>&1
check "empty AOS_PARENT_STACK counts as top level" cmp -s "$OUT_TOP" "$OUT_TOP2"

# subagent，notes_path 相對：從 AOS_WS 算
OUT_SUB="$RUN/out-sub.txt"
run AOS_PARENT_STACK=/x/parent AOS_STACK="$S" AOS_WS=/w > "$OUT_SUB" 2>&1
check "subagent: HANDOFF not pasted" bash -c "! grep -qF '上層的祕密內文' '$OUT_SUB'"
check "subagent: says it is the parent's" grep -qxF -- "wf/HANDOFF.md (and wf/progress.json) is your parent's handoff, not yours (your parent's stack is /x/parent)." "$OUT_SUB"
check "subagent: relative notes_path joined to AOS_WS" grep -qxF -- 'Your own notes are /w/wf/ws/p/kid/notes.md; read them now, before anything else.' "$OUT_SUB"
check "subagent: user.md still pasted" grep -qxF -- '# user 測試' "$OUT_SUB"

# subagent，notes_path 絕對（前後空白、沒有換行結尾）
printf '  /abs/notes.md  ' > "$S/notes_path"
OUT_ABS="$RUN/out-sub-abs.txt"
run AOS_PARENT_STACK=/x/parent AOS_STACK="$S" AOS_WS=/w > "$OUT_ABS" 2>&1
check "subagent: absolute notes_path kept as is" grep -qxF -- 'Your own notes are /abs/notes.md; read them now, before anything else.' "$OUT_ABS"

# subagent，沒有 notes_path：叫它看系統文字
rm -f "$S/notes_path"
OUT_NONE="$RUN/out-sub-none.txt"
run AOS_PARENT_STACK=/x/parent AOS_STACK="$S" AOS_WS=/w > "$OUT_NONE" 2>&1
check "subagent without notes_path: points to system text" grep -qxF -- 'Your own notes are the file your system text names; read them now, before anything else.' "$OUT_NONE"
check "subagent without notes_path: HANDOFF not pasted" bash -c "! grep -qF '上層的祕密內文' '$OUT_NONE'"
echo
echo "run folder: $RUN"
echo "PASS $PASS  FAIL $FAIL"
[ $FAIL = 0 ]
