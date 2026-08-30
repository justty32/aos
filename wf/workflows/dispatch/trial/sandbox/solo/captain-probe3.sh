#!/usr/bin/env bash
set -u
ROOT=/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a4b6627dc8a8b1254
AOS="$ROOT/build/bin/aos"
cd "$ROOT/wf/workflows/dispatch/trial/sandbox/solo/A/mini"
echo "=== log.md 大小 ==="; wc -c .aos/agents/mini/log.md
echo "=== listen --once 的輸出行數 ==="; timeout 20 "$AOS" listen --once | wc -l
echo "=== listen --once 前 12 行 ==="; timeout 20 "$AOS" listen --once | head -12
echo "=== listen（不帶 --once）30 秒內印了幾行、會不會自己結束 ==="
timeout 30 "$AOS" listen > /tmp/aos-listen-probe.txt 2>&1; echo "exit=$?"
wc -l /tmp/aos-listen-probe.txt
head -4 /tmp/aos-listen-probe.txt
rm -f /tmp/aos-listen-probe.txt
echo "=== 頂層 listen 吃不吃資料夾參數 ==="
cd "$ROOT"
timeout 20 "$AOS" listen --once wf/workflows/dispatch/trial/sandbox/solo/A/mini; echo "exit=$?"
