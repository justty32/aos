#!/usr/bin/env bash
set -u

AOS="${AOS:-/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a15b3afb7ede212cc/build/bin/aos}"
BASE=$(mktemp -d /tmp/l3-chat-XXXXXX)
PARENT="$BASE/parent"
CHILD="$PARENT/child"
export HOME="$BASE/home"
export AOS_HOME="$BASE/home/.aos"

cleanup() {
  set +e
  timeout 10 "$AOS" stop "$PARENT" >/dev/null 2>&1
  case "$BASE" in
    /tmp/l3-chat-*) rm -rf -- "$BASE" ;;
  esac
}
trap cleanup EXIT

mkdir -p "$HOME" "$PARENT/.aos" "$CHILD"
printf '# parent fixture\n' > "$PARENT/README.md"
printf '# child fixture\n' > "$CHILD/README.md"

cd "$CHILD"
reply=$(timeout 120 "$AOS" chat --engine pi '請在 README.md 最後加一行 ## 用法' 2>&1)
chat_rc=$?
child_count=$(grep -c '^## 用法$' "$CHILD/README.md" || true)
parent_count=$(grep -c '^## 用法$' "$PARENT/README.md" || true)

echo "EXPECT: chat 從沒有 .aos 的 child 執行時，修改 child/README.md，不碰祖先世界的 README.md。"
echo "ACTUAL: chat_exit=$chat_rc child_heading_count=$child_count parent_heading_count=$parent_count reply_bytes=${#reply}。"
if test "$chat_rc" -eq 0 && test "$child_count" -eq 1 && test "$parent_count" -eq 0; then
  echo PASS
  exit 0
fi
echo FAIL
exit 1
