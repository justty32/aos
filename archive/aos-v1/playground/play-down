#!/bin/sh
# 收工：把 daemon 停掉（kernel 跟所有行程都跟著停）。遊樂場的檔案都留著，下次 up.sh 接著玩。
[ -n "$AOS_DAEMON_HOME" ] || { echo "先 source $(dirname "$0")/env.sh"; exit 2; }
aos-daemon-ctl stop
