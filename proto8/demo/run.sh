#!/bin/sh
# 各建一個暫時工作區、放一題、cd 進去跑 agent-bob（含它叫的 cathy）與 agent-ann（慣例用法）、印出工作區與整棵 stack 樹；
# 接著跑 agent-dan（假腦、叫 clock 工具再答）；
# 再跑 daemon：一個 daemon 同時管 bob、ann 兩個子 loop（各自的工作區在 bob/、ann/）；
# 再跑 tick：aos-loop 跑 5 次 aos-tick，時鐘檔 $AOS_STACK/tick.txt 走到 5（10-21 計畫第 4 段）；
# 最後跑 kernel-llm：一個 daemon 同時管 LLM kernel 與三隻走 kernel 的 agent（c 是 high），看服務順序（thinking 2026-10-24-llm-kernel）
here=$(cd "$(dirname "$0")" && pwd)
# aos 的程式都不動 PATH（ideas § 24）：agent 裡叫的 aos-exec、aos-loop、aos-fsm、aos-daemon、aos-tick 由這裡（呼叫端）放進 PATH。
# 10-23 起前四支是 C++（10-24 加 aos-kernel-llm、aos-gate 兩支）（proto8/impls/<名>/bin/，要先建，見 wf/workflows/testing.md）；aos-tick 還是 Python（proto8/bin/）
impls=$(cd "$here/../impls" && pwd)
for p in aos-exec aos-loop aos-fsm aos-daemon aos-kernel-llm aos-gate; do
  [ -x "$impls/$p/bin/$p" ] || { echo "run.sh：$impls/$p/bin/$p 還沒建（先建 proto8/impls，見 wf/workflows/testing.md）" >&2; exit 1; }
  PATH="$impls/$p/bin:$PATH"
done
PATH="$(cd "$here/../bin" && pwd):$PATH"; export PATH
show() {   # 印工作區與 stack 樹（每檔印內容；子 agent 的工作區 ws/ 只列檔名）
  echo "--- 工作區 $1" && (cd "$1" && find . -path ./.stack -prune -o -type f -print | sort)
  (cd "$1" && for f in $(find . -path ./.stack -prune -o -type f \( -path '*/out/*' -o -path '*/done/*' \) -print | sort); do
    echo "== $f"; cat "$f"; done)
  echo "--- stack 整棵樹 $1/.stack/"
  (cd "$1" && find .stack -type f | sort | while read -r f; do
    case $f in
      */ws/*) echo "== $f" ;;
      *) echo "== $f"; cat "$f" ;;
    esac
  done)
}
for agent in agent-bob agent-ann; do
  echo "######## $agent"
  ws=$(mktemp -d)
  mkdir "$ws/new"; echo "1+1 等於多少？" > "$ws/new/q1.txt"
  (cd "$ws" && aos-exec "$here/$agent"); echo "結束碼 $?"
  show "$ws"; rm -rf "$ws"
done
echo "######## agent-dan"   # 會用工具的問答 agent（假腦：先叫 clock、再答；thinking 2026-10-23-tool-calls）
ws=$(mktemp -d)
mkdir "$ws/new"; echo "現在幾點？" > "$ws/new/q1.txt"
(cd "$ws" && aos-exec "$here/agent-dan"); echo "結束碼 $?"
show "$ws"; rm -rf "$ws"
echo "######## daemon"
ws=$(mktemp -d)
for a in bob ann; do mkdir -p "$ws/$a/new"; echo "2+2 等於多少？" > "$ws/$a/new/q1.txt"; done
(cd "$ws" && aos-exec "$here/daemon"); echo "結束碼 $?"
show "$ws"; rm -rf "$ws"
echo "######## tick"
ws=$(mktemp -d)
(cd "$ws" && aos-exec "$here/tick"); echo "結束碼 $?"
show "$ws"; rm -rf "$ws"
echo "######## kernel-llm"   # 三隻 agent 同時問腦，腦經 kernel 排隊（slots 1、假腦想 1 秒）；served.jsonl 是服務順序，high 的 c 先
ws=$(mktemp -d)
for a in a b c; do mkdir -p "$ws/$a/new"; echo "$a 問：2+2 等於多少？" > "$ws/$a/new/q1.txt"; done
(cd "$ws" && aos-exec "$here/kernel-llm"); echo "結束碼 $?"
show "$ws"; rm -rf "$ws"
