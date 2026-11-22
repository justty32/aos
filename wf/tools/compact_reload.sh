#!/bin/sh
# compact 後重讀：Claude Code SessionStart（matcher=compact）hook 呼叫，stdout 會進 compact 後的上下文。
# 輸出：使用者偏好全文（wf/workflows/common/user.md 入口＋user/ 底下所有分檔）＋最新一條 compact 交接（wf/HANDOFF.md 第一個「## 」段）＋提醒。
# HANDOFF.md 沒有條目時，改印 wf/progress.json 的 open 條目（一條兩行：狀態｜標題：現況，下一行細節連結）。從任何 cwd 都能跑。
# what／next 寫成 {"$ref": "progress/x.md"}（路徑從 wf/ 算）時，印那份 md 的第一行加全文路徑，不印全文。
root="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
user="$root/wf/workflows/common/user.md"
handoff="$root/wf/HANDOFF.md"
progress="$root/wf/progress.json"

# progress.json 的 open 條目印成人讀的幾行；沒有 python3 就整份照印
print_progress() {
    if command -v python3 >/dev/null 2>&1; then
        python3 - "$1" <<'PY'
import json, os, sys
base = os.path.dirname(os.path.abspath(sys.argv[1]))
root = os.path.dirname(base)
def text(v):
    # {"$ref": "progress/x.md"} -> first line of that file + where the full text is
    if not (isinstance(v, dict) and isinstance(v.get("$ref"), str)):
        return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    path = os.path.normpath(os.path.join(base, v["$ref"].split("#", 1)[0]))
    shown = os.path.relpath(path, root)
    try:
        with open(path, encoding="utf-8") as f:
            first = f.readline().strip().lstrip("#").strip()
    except OSError:
        return f"(missing: {shown})"
    return f"{first} (full text: {shown})"
d = json.load(open(sys.argv[1], encoding="utf-8")).get("open", {})
if not d:
    print("(no open entries)")
for k, e in d.items():
    flow = f" [{e['flow']}]" if e.get("flow") else ""
    print(f"- {e.get('status', '')}｜{e.get('title', k)}{flow}：{text(e.get('what', ''))}")
    if e.get("next"):
        print(f"  next: {text(e['next'])}")
    if e.get("see"):
        print(f"  see: {'、'.join(e['see'])}")
PY
    else
        cat "$1"
    fi
}

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
    echo "===== wf/HANDOFF.md 沒有交接條目，改看 wf/progress.json 的 open 條目 ====="
    if [ -f "$progress" ]; then print_progress "$progress"; else echo "（找不到 $progress）"; fi
fi
echo
echo "提醒：設計題先讀相關 NORMS／CONCEPTS 再回答；說「已寫進」前先查。開場兩軸（inbox、progress.json）照 AGENTS.md。"
