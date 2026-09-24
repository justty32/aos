#!/bin/sh
# 實驗 1：不在 namespace 裡、不是 root，能不能直接切 uid？（預期不行）
# 不 sudo、不建使用者、不改系統設定。
echo "== 1a: setpriv --reuid 1234 id（沒 root）"
setpriv --reuid 1234 --regid 1234 --clear-groups id 2>&1; echo "exit=$?"
echo "== 1b: runuser -u nobody id（沒 root）"
runuser -u nobody -- id 2>&1; echo "exit=$?"
echo "== 1c: systemd-run --user 想換人（DynamicUser=／User=）"
systemd-run --user --wait --quiet -p DynamicUser=yes id 2>&1; echo "exit=$?"
systemd-run --user --wait --quiet -p User=nobody id 2>&1; echo "exit=$?"
