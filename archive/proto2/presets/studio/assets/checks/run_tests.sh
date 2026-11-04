#!/usr/bin/env bash
# 標準檢查：在專案目錄跑 py_compile 與 unittest，最後印一行總結。
# 用法：bash run_tests.sh [專案目錄]（不給就用目前目錄）
# 退出碼：0 全過；1 有東西沒過；2 目錄不對；3 沒有測試。
set -u

dir=${1:-.}
cd "$dir" 2>/dev/null || { echo "總結：進不去專案目錄 $dir"; exit 2; }

shopt -s nullglob
pys=(*.py)
if [ ${#pys[@]} -eq 0 ]; then
  echo "總結：這個資料夾一個 .py 檔都沒有（$PWD）"
  exit 2
fi

echo "== py_compile（${#pys[@]} 個檔）=="
if python3 -m py_compile "${pys[@]}"; then
  compile_note="py_compile 過"
  compile_ok=1
else
  compile_note="py_compile 失敗"
  compile_ok=0
fi

tests=(test_*.py)
if [ ${#tests[@]} -eq 0 ]; then
  rm -rf __pycache__
  echo "總結：沒有測試（找不到 test_*.py）；照 team/assets/snippets/test_template.py 先寫一支再來。"
  exit 3
fi

echo "== unittest discover（${#tests[@]} 個測試檔）=="
if python3 -m unittest discover -v; then
  test_note="unittest 過"
  test_ok=1
else
  test_note="unittest 失敗"
  test_ok=0
fi

rm -rf __pycache__
echo "總結：$compile_note；$test_note（$PWD）"
[ "$compile_ok" = 1 ] && [ "$test_ok" = 1 ] && exit 0
exit 1
