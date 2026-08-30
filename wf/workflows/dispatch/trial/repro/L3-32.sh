#!/usr/bin/env bash
set -u

AOS="${AOS:-/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a15b3afb7ede212cc/build/bin/aos}"
SBX=$(mktemp -d /tmp/l3-32-XXXXXX)
RUN_PID=""
cleanup() {
  if [[ -n "$RUN_PID" ]] && kill -0 "$RUN_PID" 2>/dev/null; then
    kill "$RUN_PID" 2>/dev/null || true
    wait "$RUN_PID" 2>/dev/null || true
  fi
  rm -rf "$SBX"
}
trap cleanup EXIT INT TERM

export HOME="$SBX/home"
mkdir -p "$HOME"
export AOS_HOME="$HOME/.aos"

declare -a results=()
all_zero=1
for sub in tick heartbeat routine schedule; do
  OUT=$(timeout 10 "$AOS" "$sub" --help 2>&1)
  RC=$?
  LINES=$(printf '%s\n' "$OUT" | wc -l)
  results+=("$sub=$RC/${LINES}lines")
  if [[ $RC -ne 0 ]]; then
    all_zero=0
  fi
done

echo "EXPECT: tick／heartbeat／routine／schedule 的 --help 都 exit 0 並正常顯示說明"
echo "ACTUAL: ${results[*]}"
if [[ $all_zero -eq 1 ]]; then
  echo PASS
  exit 0
fi
echo FAIL
exit 1
