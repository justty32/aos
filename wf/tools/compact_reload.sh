#!/bin/sh
# compact 後重讀：Claude Code SessionStart（matcher=compact）hook 呼叫，stdout 會進 compact 後的上下文。
# 輸出：使用者偏好全文（wf/workflows/common/user.md 入口＋user/ 底下所有分檔）＋最新一條 compact 交接（wf/HANDOFF.md 第一個「## 」段）＋提醒。
# HANDOFF.md 沒有條目時，改印 SESSION-LOG 的「## 最新進度」段。從任何 cwd 都能跑。
root="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
user="$root/wf/workflows/common/user.md"
handoff="$root/wf/HANDOFF.md"
log="$root/wf/SESSION-LOG.md"

# 印第一個「## 」標題起、到下一個「## 」之前的段落；$2 有給就只找標題等於它的那段
first_section() {
    awk -v want="$2" '
        /^## / { if (on) exit; if (want == "" || $0 == want) on = 1 }
        on { print }
    ' "$1"
}

echo "compact 後重讀：以下是使用者偏好與最近的交接"
echo
echo "===== wf/workflows/common/user.md ====="
if [ -f "$user" ]; then cat "$user"; else echo "（找不到 $user）"; fi
# user.md 已拆成 user/NN-*.md 分檔（逐字），入口只留前言與目錄，所以分檔也要讀回
for part in "${user%.md}"/*.md; do
    [ -f "$part" ] || continue
    echo
    echo "===== wf/workflows/common/user/$(basename "$part") ====="
    cat "$part"
done
echo

entry=""
[ -f "$handoff" ] && entry=$(first_section "$handoff")
if [ -n "$entry" ]; then
    echo "===== 最新 compact 交接（wf/HANDOFF.md 第一條）====="
    printf '%s\n' "$entry"
else
    echo "===== wf/HANDOFF.md 沒有交接條目，改看 SESSION-LOG 最新進度 ====="
    [ -f "$log" ] && first_section "$log" "## 最新進度"
fi
echo
echo "提醒：設計題先讀相關 NORMS／CONCEPTS 再回答；說「已寫進」前先查。開場三軸（inbox、SESSION-LOG、WAIT_USER）照 AGENTS.md。"
