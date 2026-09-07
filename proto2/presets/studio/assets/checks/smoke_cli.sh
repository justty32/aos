#!/usr/bin/env bash
# CLI 冒煙：--help，再走 add → list → delete 三步，資料檔開在暫存目錄，不動專案的檔。
# 用法：bash smoke_cli.sh <主程式.py>
# 退出碼：0 全過；1 某一步失敗（會印是哪一步）；2 參數或檔案不對。
set -u

main=${1:-}
[ -n "$main" ] || { echo "用法：smoke_cli.sh <主程式.py>"; exit 2; }
[ -f "$main" ] || { echo "找不到主程式：$main"; exit 2; }
main=$(cd "$(dirname "$main")" && pwd)/$(basename "$main")

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
data="$tmp/smoke.json"
item="冒煙測試項目"

bad() {  # bad <哪一步> <輸出>
  echo "冒煙失敗：$1"
  printf '%s\n' "$2" | tail -20
  exit 1
}

out=$(python3 "$main" --help 2>&1) || bad "--help 跑不起來" "$out"
case "$out" in
  *"--file"*) args=(--file "$data") ;;
  *) args=(); cd "$tmp" || bad "進不去暫存目錄" "$tmp" ;;
esac

out=$(python3 "$main" "${args[@]}" add "$item" 2>&1) || bad "add 退出碼不是 0" "$out"
id=$(printf '%s' "$out" | grep -o '[0-9][0-9]*' | head -1)
[ -n "$id" ] || id=1

out=$(python3 "$main" "${args[@]}" list 2>&1) || bad "list 退出碼不是 0" "$out"
case "$out" in
  *"$item"*) ;;
  *) bad "list 沒有列出剛剛 add 的那筆" "$out" ;;
esac

out=$(python3 "$main" "${args[@]}" delete "$id" 2>&1) || bad "delete $id 退出碼不是 0" "$out"

out=$(python3 "$main" "${args[@]}" list 2>&1) || bad "刪完再 list 退出碼不是 0" "$out"
case "$out" in
  *"$item"*) bad "delete 之後那筆還在" "$out" ;;
esac

echo "冒煙通過：--help、add、list、delete 四步都過（$(basename "$main")）"
