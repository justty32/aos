#!/bin/sh
# 範例 verify：tgz 讀得開才記 sha256（冪等）。用法：verify.sh <dump.tgz> <輸出.sha256>
set -e
tar tzf "$1" > /dev/null
sha256sum "$1" | cut -d' ' -f1 > "$2.tmp"
mv "$2.tmp" "$2"
