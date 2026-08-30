#!/usr/bin/env bash
set -u
ROOT=/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a4b6627dc8a8b1254
AOS="$ROOT/build/bin/aos"
W="$ROOT/wf/workflows/dispatch/trial/sandbox/solo/cap"
cd "$W"

echo "=== A. --help 的真 exit code（有 agent 的世界） ==="
for c in say listen state talk deliver; do
  out=$("$AOS" $c --help 2>&1); rc=$?
  echo "--- aos $c --help -> exit=$rc"; echo "$out" | head -4
done

echo; echo "=== B. aos say --help 有沒有把 --help 當成訊息送出去？ ==="
ls .aos/agents/cap/say/ 2>&1

echo; echo "=== C. listen --once 看不看得到使用者自己說的話 ==="
"$AOS" say "第二句話"; echo "say exit=$?"
ls .aos/agents/cap/say/
echo "--- listen --once:"; "$AOS" listen --once; echo "listen exit=$?"
echo "--- log.md 大小:"; wc -c .aos/agents/cap/log.md
echo "--- history.json:"; cat .aos/agents/cap/history.json

echo; echo "=== D. state 是誰的 state ==="
echo "--- aos state:"; "$AOS" state
echo "--- .aos/state.json:"; cat .aos/state.json 2>&1

echo; echo "=== E. 沒有世界的地方（repo 外） ==="
mkdir -p /tmp/aos-cap-empty && cd /tmp/aos-cap-empty
"$AOS" state; echo "state exit=$?"
"$AOS" say hi; echo "say exit=$?"
"$AOS" listen --once; echo "listen exit=$?"
cd /tmp && rm -rf /tmp/aos-cap-empty

echo; echo "=== F. run 對不存在資料夾 vs 沒權限 ==="
"$AOS" run /nonexistent/zzz --step 1; echo "exit=$?"
"$AOS" run /tmp/definitely-not-here-xyz --step 1; echo "exit=$?"

echo; echo "=== G. tool 的真名 ==="
cd "$W"
"$AOS" tool list; echo "tool list exit=$?"
"$AOS" tool ls; echo "tool ls exit=$?"
