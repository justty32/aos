#!/bin/sh
# 範例 rotate：留三代 b.1（最新）～b.3。**不冪等**：同一份 dump 跑兩次會再推一代、把 b.3 丟掉。
# 用法：rotate.sh <dump.tgz> <archive 資料夾>
set -e
mkdir -p "$2"
rm -f "$2/b.3.tgz"
if [ -f "$2/b.2.tgz" ]; then mv "$2/b.2.tgz" "$2/b.3.tgz"; fi
if [ -f "$2/b.1.tgz" ]; then mv "$2/b.1.tgz" "$2/b.2.tgz"; fi
cp "$1" "$2/b.1.tgz"
echo rotated >> "$2/rotations.log"
