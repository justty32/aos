#!/bin/sh
# L2-02  新世界的預設工具裡沒有 `aos`，所以 boss agent 開箱即用時**根本無法派工**。
# L2-03  就算把 `aos` 登記進去，system prompt 也從不提通訊錄——agent 不知道 w1／w2 存在。
#
# 期待：一隻 boss agent 一開機就有「投遞給隊友」這個能力，並且知道隊上有誰。
# 實際：(1) `aos agent init` 只裝 cat／ls／sh 三個工具，沒有 aos、沒有 deliver、沒有 contact；
#           （repo 根 .aos/tools/ 裡的 aos.json、git.json 是人手加進版控的，不是預設）
#       (2) core/agent 裡只有 run_top.cpp 這個**頂層 CLI** 讀 contacts.json；
#           step.cpp／tools.cpp 組 system prompt 時只列工具、從不列聯絡人。
#       → 使用者得自己 `aos tool add aos` 再在人格或訊息裡把隊友名單抄一遍。
set -eu
AOS="${AOS_BIN:-aos}"
ROOT="$(mktemp -d)"
trap 'rm -rf "$ROOT"' EXIT

mkdir -p "$ROOT/boss/.aos" "$ROOT/w1/.aos"
(cd "$ROOT/boss" && "$AOS" agent init --name boss >/dev/null)
(cd "$ROOT/w1"   && "$AOS" agent init --name w1   >/dev/null)
(cd "$ROOT/boss" && "$AOS" contact add w1 ../w1 --note "翻譯" >/dev/null)

echo "=== 全新世界的預設工具 ==="
(cd "$ROOT/boss" && "$AOS" tool ls)

echo
echo "=== 有 aos／deliver／contact 這類投遞工具嗎？ ==="
if (cd "$ROOT/boss" && "$AOS" tool ls) | grep -qE '^(aos|deliver|contact|say) '; then
  echo "PASS"
else
  echo "FAIL: 預設工具只有 cat／ls／sh，agent 沒有任何『寄信給隊友』的能力"
fi

echo
echo "=== 通訊錄裡明明有 w1 ==="
(cd "$ROOT/boss" && "$AOS" contact ls)

echo
echo "=== 但 agent 的 system prompt 提過 w1 嗎？ ==="
echo "（system prompt 由 core/agent/src/tools.cpp:system_prompt 組成：人格 + 工具清單，沒有聯絡人區塊）"
PERSONA="$ROOT/boss/.aos/agents/boss/persona.md"
[ -f "$PERSONA" ] && { echo "--- persona.md ---"; cat "$PERSONA"; }
if grep -rq "contact" "$ROOT/boss/.aos/agents/boss/" 2>/dev/null; then
  echo "PASS: agent 端有通訊錄的影子"
else
  echo "FAIL: agent 自己的資料夾裡完全沒有通訊錄的影子；它不知道隊上有誰"
  exit 1
fi
