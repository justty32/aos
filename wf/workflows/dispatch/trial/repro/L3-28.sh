#!/usr/bin/env bash
set -u

AOS="${AOS:-/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a15b3afb7ede212cc/build/bin/aos}"
SBX=$(mktemp -d /tmp/l3-28-XXXXXX)
trap 'rm -rf "$SBX"' EXIT

export HOME="$SBX/home"
mkdir -p "$HOME" "$SBX/world" "$SBX/bin"
export AOS_HOME="$HOME/.aos"

printf '%s\n' '#!/usr/bin/env bash' 'echo "fake pi provider failed" >&2' 'exit 17' >"$SBX/bin/pi"
chmod +x "$SBX/bin/pi"
export PATH="$SBX/bin:$PATH"

cd "$SBX/world" || exit 2
timeout 10 "$AOS" agent init --name worker --engine pi >/dev/null
timeout 10 "$AOS" say "觸發 fake pi 錯誤" >/dev/null
timeout 10 "$AOS" run . --step 1 >"$SBX/run.out" 2>"$SBX/run.err"
RUN_RC=$?
timeout 10 "$AOS" state >"$SBX/state.json" 2>"$SBX/state.err"
STATUS=$(jq -r '.status' "$SBX/state.json")
DETAIL=$(jq -r '.detail' "$SBX/state.json")
LAST_ERROR=$(jq -r '.last_error' "$SBX/state.json")

echo "EXPECT: pi 失敗時 state.status=error，last_error 應包含與 detail 相同的失敗原因"
echo "ACTUAL: run_exit=$RUN_RC，status=$STATUS，last_error=[$LAST_ERROR]，detail=[$DETAIL]"

if test "$STATUS" = error && test -n "$LAST_ERROR"; then
  echo PASS
  exit 0
fi
echo FAIL
exit 1
