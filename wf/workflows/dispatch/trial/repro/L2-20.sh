#!/bin/sh
# L2-20  inst 的 ended_at 記的是**整批**的結束時間，不是自己的。
#
# 期待：一條 `true`（瞬間）與一條 `sleep 3`，ended_at 應該差約 3 秒。
# 實際：started_at 是各自的（差 1 ms），但 ended_at 兩條完全相同——
#       都被寫成整批結束的時刻。於是每條 inst 看起來都跑滿整個回合，
#       「這回合是誰拖慢的」從 out JSON 看不出來。
set -eu
AOS="${AOS_BIN:-aos}"
ROOT="$(mktemp -d)"
trap 'rm -rf "$ROOT"' EXIT

mkdir -p "$ROOT/w/.aos/every"
(cd "$ROOT/w" && "$AOS" agent init --name w >/dev/null)
rm -f "$ROOT/w/.aos/every/agent-w.json"          # 不要 LLM，這條純看時間戳
printf '{"argv":["sleep","3"]}\n' > "$ROOT/w/.aos/every/slow.json"
printf '{"argv":["true"]}\n'      > "$ROOT/w/.aos/every/fast.json"

(cd "$ROOT/w" && "$AOS" run --step 1)

echo "=== 每條 inst 的 out ==="
for f in "$ROOT/w/.aos/batch/1/out/"*.json; do
  echo "--- $(basename "$f") ---"
  grep -E '"(id|started_at|ended_at)"' "$f"
done

STARTS=$(grep -h '"started_at"' "$ROOT/w/.aos/batch/1/out/"*.json | sort -u | wc -l)
ENDS=$(grep -h '"ended_at"'   "$ROOT/w/.aos/batch/1/out/"*.json | sort -u | wc -l)
echo
echo "相異的 started_at：$STARTS（2 = 各自的，正確）"
echo "相異的 ended_at  ：$ENDS（1 = 整批的，錯）"

if [ "$ENDS" -eq 1 ]; then
  echo "FAIL: true 與 sleep 3 的 ended_at 相同——ended_at 是整批的，分不出誰慢"
  exit 1
fi
echo "PASS"
