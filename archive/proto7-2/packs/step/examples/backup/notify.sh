#!/bin/sh
# 範例 notify：把這次備份的摘要寫成通知檔（覆寫，冪等；真的要送出去的話接在這裡）。用法：notify.sh <archive> <輸出> <request>
set -e
{ echo "backup ok request=$3"; ls "$1"; } > "$2.tmp"
mv "$2.tmp" "$2"
