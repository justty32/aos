#!/bin/sh
# L2-10  `aos say --help` 不但問不到用法，還會把 "--help" 當成訊息投給 agent。
#
# 期待：印出 `usage: aos say [--to <名字>] <text...>`（那串 usage 是存在的，
#       打 `aos say` 不帶參數就看得到），且不動到 agent。
# 實際：(1) 在沒有 agent 的資料夾 → 印「這個資料夾還沒有 agent」，看不到 usage；
#       (2) 在有 agent 的資料夾 → **靜默把字串 "--help" 寫進 agent 的 say/ 信箱、exit 0**，
#           下一回合 agent 就會被這則垃圾訊息叫醒、白燒一次 LLM；
#       (3) 任何一份 usage 都沒說明 `--to` 是查通訊錄用的，
#           而 `--to` 是跨世界投遞的唯一入口。
set -eu
AOS="${AOS_BIN:-aos}"
ROOT="$(mktemp -d)"
trap 'rm -rf "$ROOT"' EXIT

echo "=== (1) 沒有 agent 的資料夾 ==="
(cd "$ROOT" && "$AOS" say --help 2>&1) || true

echo
echo "=== (2) 有 agent 的資料夾 ==="
mkdir -p "$ROOT/w/.aos"
(cd "$ROOT/w" && "$AOS" agent init --name w >/dev/null)
(cd "$ROOT/w" && "$AOS" say --help 2>&1) || true
echo "say/ 信箱內容："
for f in "$ROOT/w/.aos/agents/w/say/"*; do
  [ -e "$f" ] || { echo "  （空）"; break; }
  printf '  %s -> ' "$(basename "$f")"; cat "$f"; echo
done
LEAKED=0
if [ -n "$(ls -A "$ROOT/w/.aos/agents/w/say/" 2>/dev/null)" ]; then
  echo "FAIL: --help 被當成訊息投遞出去了"
  LEAKED=1
else
  echo "PASS"
fi

echo
echo "=== (3) usage 其實存在，只是 --help 到不了；而且沒解釋 --to ==="
(cd "$ROOT/w" && "$AOS" say 2>&1) || true

echo
echo "=== 對照：listen／state／talk 的 --help 會印 usage（但 state／talk 尾巴多空格、無參數說明） ==="
for c in listen state talk; do
  printf '  aos %s --help -> ' "$c"
  (cd "$ROOT" && "$AOS" "$c" --help 2>&1) || true
done

exit "$LEAKED"
