#!/bin/sh
# 各建一個暫時工作區、放一題、cd 進去跑 agent-bob（含它叫的 cathy）與 agent-ann（慣例用法）、印出工作區與整棵 stack 樹
here=$(cd "$(dirname "$0")" && pwd)
# aos 的程式都不動 PATH（ideas § 24）：agent 裡叫的 aos-exec、aos-loop、aos-fsm 由這裡（呼叫端）放進 PATH
PATH="$(cd "$here/../bin" && pwd):$PATH"; export PATH
for agent in agent-bob agent-ann; do
  echo "######## $agent"
  ws=$(mktemp -d)
  mkdir "$ws/inbox"; echo "1+1 等於多少？" > "$ws/inbox/q1.txt"
  (cd "$ws" && aos-exec "$here/$agent"); echo "結束碼 $?"
  cd "$ws" && echo "--- 工作區 $ws" && find . -path ./.aos -prune -o -type f -print | sort
  for f in out/* done/*; do echo "== $f"; cat "$f"; done
  echo "--- stack 整棵樹 $ws/.aos/（每檔印內容；子 agent 的工作區 ws/ 只列檔名）"
  find .aos -type f | sort | while read -r f; do
    case $f in
      */ws/*) echo "== $f" ;;
      *) echo "== $f"; cat "$f" ;;
    esac
  done
  cd "$here"; rm -rf "$ws"
done
