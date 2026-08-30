#!/bin/sh
# L2-09  投遞失敗時錯誤訊息不指路：不存在的資料夾 與 沒有 agent 的資料夾 講同一句話，
#        而且從不說出它解析到的是哪個路徑。
#
# 期待：「聯絡人 ghost 指到 <解析後的絕對路徑>，那個資料夾不存在」。
# 實際：兩種情況都印 "aos say: 這個資料夾還沒有 agent；請先跑 aos agent init"，
#       使用者不知道是打錯路徑、還是對方真的沒 init，也不知道該去哪個資料夾 init。
set -eu
AOS="${AOS_BIN:-aos}"
ROOT="$(mktemp -d)"
trap 'rm -rf "$ROOT"' EXIT

mkdir -p "$ROOT/a/.aos"
(cd "$ROOT/a" && "$AOS" agent init --name a >/dev/null)

# 情況一：資料夾根本不存在
(cd "$ROOT/a" && "$AOS" contact add ghost ../nope >/dev/null)
echo "--- 情況一：contact 指到不存在的資料夾 ---"
(cd "$ROOT/a" && "$AOS" say --to ghost "hi" 2>&1) || true

# 情況二：資料夾存在、是個世界、但沒有 agent
mkdir -p "$ROOT/empty/.aos/agents"
(cd "$ROOT/a" && "$AOS" contact add empty ../empty >/dev/null)
echo "--- 情況二：資料夾存在但沒有 agent ---"
(cd "$ROOT/a" && "$AOS" say --to empty "hi" 2>&1) || true

echo
echo "兩句一模一樣，且都沒有印出解析後的路徑 → 錯誤不指路"
