#!/usr/bin/env bash
# 隊長自用探針：只碰不呼叫 LLM 的介面
set -u
ROOT=/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a4b6627dc8a8b1254
AOS="$ROOT/build/bin/aos"
W="$ROOT/wf/workflows/dispatch/trial/sandbox/solo/cap"
rm -rf "$W"; mkdir -p "$W/.aos"; cd "$W"
cp -r "$ROOT/wf/workflows/dispatch/trial/sandbox/solo/_template/." .

echo "=== 1. 各子命令的 --help ==="
for c in run deliver say listen talk state tool llm; do
  echo "--- $c --help"; "$AOS" $c --help 2>&1 | head -8; echo "  exit=$?"
done

echo; echo "=== 2. init 印什麼 ==="
"$AOS" agent init; echo "init exit=$?"
echo "--- persona.md:"; cat .aos/agents/*/persona.md
echo "--- engine.json:"; cat .aos/agents/*/engine.json
echo "--- status.json:"; cat .aos/agents/*/status.json
echo "--- every/agent-*.json:"; cat .aos/every/agent-*.json
echo "--- tools:"; ls .aos/tools

echo; echo "=== 3. 重複 init ==="
"$AOS" agent init; echo "re-init exit=$?"

echo; echo "=== 4. say/listen/state 在空世界 ==="
"$AOS" say "hello"; echo "say exit=$?"
"$AOS" listen --once; echo "listen exit=$?"
"$AOS" state; echo "state exit=$?"

echo; echo "=== 5. 壞參數 ==="
"$AOS" run . --step; echo "exit=$?"
"$AOS" run . --step abc; echo "exit=$?"
"$AOS" run /nonexistent/zzz --step 1; echo "exit=$?"
"$AOS" agent init --engine nosuch; echo "exit=$?"
"$AOS" tool add; echo "exit=$?"
"$AOS" tool remove nosuch; echo "exit=$?"
"$AOS" nosuchcommand; echo "exit=$?"

echo; echo "=== 6. llm 連不上 ==="
echo hi | AOS_LLM_URL=http://localhost:19999/v1 timeout 30 "$AOS" llm; echo "exit=$?"
echo hi | AOS_LLM_MODEL=no/such-model timeout 30 "$AOS" llm; echo "exit=$?"
"$AOS" llm --slots; echo "slots exit=$?"
