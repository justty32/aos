#!/bin/sh
# 範例 dump：把來源資料夾打包成 tgz（覆寫同一個檔，重跑無害＝冪等）。用法：dump.sh <來源資料夾> <輸出.tgz>
set -e
mkdir -p "$(dirname "$2")"
tar czf "$2.tmp" -C "$1" .
mv "$2.tmp" "$2"
