#!/bin/sh
# 建暫時工作區、放一題、跑 agent-bob、印出工作區內容
here=$(cd "$(dirname "$0")" && pwd)
ws=$(mktemp -d)
mkdir "$ws/inbox"; echo "1+1 等於多少？" > "$ws/inbox/q1.txt"
"$here/../bin/aos-exec" "$ws" "$here/agent-bob"; echo "結束碼 $?"
cd "$ws" && for f in trace.log state out/* done/*; do echo "== $f"; cat "$f"; done
rm -rf "$ws"
