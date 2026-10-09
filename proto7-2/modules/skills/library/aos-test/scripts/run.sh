#!/usr/bin/env bash
# 在 repo 根跑：把 run_all.py 包進 systemd scope；全套給 800 個程序，部分給 300。
set -eu
if [ "$#" -eq 0 ]; then LIMIT=800; else LIMIT=300; fi
exec systemd-run --user --scope -q -p TasksMax=$LIMIT -p RuntimeMaxSec=1800 python3 proto7-2/tests/run_all.py "$@"
