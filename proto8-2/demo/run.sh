#!/bin/sh
# 建暫時工作區、放一題、cd 進去跑 agent-bob（慣例用法）、印出工作區與 stack 內容
here=$(cd "$(dirname "$0")" && pwd)
ws=$(mktemp -d)
mkdir "$ws/inbox"; echo "1+1 等於多少？" > "$ws/inbox/q1.txt"
(cd "$ws" && "$here/../bin/aos-exec" "$here/agent-bob"); echo "結束碼 $?"
cd "$ws" && echo "--- 工作區 $ws" && find . -path ./.aos -prune -o -type f -print | sort
for f in out/* done/*; do echo "== $f"; cat "$f"; done
echo "--- stack $ws/.aos/"
for f in .aos/*; do echo "== $f"; cat "$f"; done
rm -rf "$ws"
