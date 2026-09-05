#!/usr/bin/env bash
# 離線跑完整互動流程：三個任務、插話、看狀態、看完整一圈、離開。
set -eu
set -o pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
PROTO="$(cd "$HERE/.." && pwd)"
OUT="$(mktemp -t aos-play-chat-selftest.XXXXXX)"
trap 'rm -f "$OUT"' EXIT

{
  printf '%s\n' '把這句話看完，沒有工具要跑就收工'
  printf '%s\n' '記得回話短一點'
  sleep 4
  printf '%s\n' '/status'
  printf '%s\n' '/log'
  printf '%s\n' '/new 再跑一個離線任務'
  printf '%s\n' '這是第二封中途插話'
  sleep 4
  printf '%s\n' '/new 最後再跑一圈'
  sleep 4
  printf '%s\n' '/quit'
} | AOS_PLAY_BACKEND=echo: bash "$PROTO/play-chat.sh" >"$OUT" 2>&1

HOME_PATH="$(sed -n 's/^家留在：//p' "$OUT" | tail -1)"
test -n "$HOME_PATH"
test -d "$HOME_PATH"
test "$(find "$HOME_PATH/lands" -mindepth 1 -maxdepth 1 -type d | wc -l)" -eq 3
test "$(grep -c '^── 第 1 圈 ──$' "$OUT")" -eq 3
test "$(grep -c '^── 第 [0-9][0-9]* 圈 ──$' "$OUT")" -eq 6
grep -q '信送進去了' "$OUT"
grep -q '記得回話短一點' "$HOME_PATH/lands/agent-001/state/rounds/002/prompt.txt"
grep -q '^===== 最後一圈的 prompt =====$' "$OUT"
grep -q '^===== 這一輪結算 =====$' "$OUT"
grep -q '"endpoint": "echo:"' "$HOME_PATH/.aos/config.json"
grep -q '"api_key_env": "DEEPSEEK_API_KEY"' "$HOME_PATH/.aos/config.json"

echo "自測通過：三個任務共跑六圈，插話進了下一份 prompt，/status、/log、/new、/quit 都走過。"
echo "自測的家留在：$HOME_PATH"
