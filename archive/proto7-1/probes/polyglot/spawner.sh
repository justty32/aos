#!/bin/bash
# polyglot 的 bash 任務：開三種背景子程序，看任務 kill 收不收得到。
#   sleep 301：普通背景 &（同一個程序群組）
#   sleep 302：setsid（新 session，但仍是 bash 的子程序＝後代）
#   sleep 303：( setsid sleep & )（雙 fork：中間的 subshell 先走，被 init 收養，不再是後代）
sleep 301 &
setsid sleep 302 &
( setsid sleep 303 & )
echo "spawned"
wait
