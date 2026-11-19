#!/bin/bash
# 測：aos-clock-register 的 after／every／at 過去時刻，與 aos-clock 推進時寄信、一次性的格寄完拿掉（對 knowledge/aos/clock.json#/wake_at）
set -u
W=$(mktemp -d "$HOME/.aos/scratch/aos-base-audit-1119/a-docs/forkB/clock.XXXX")
aos-post init "$W/q" >/dev/null
echo 5 > "$W/clock"
export AOS_CLOCK=$W/clock
aos-clock-register add --after 2 --box "$W/q" --by t -- once "after two"; echo "exit $?"
aos-clock-register add --every 3 --box "$W/q" --by t -- tri "every three"; echo "exit $?"
aos-clock-register add --at "2000-01-01 00:00" --box "$W/q" --by t -- past "past"; echo "exit $?"
aos-clock-register add --at "+1d" --box "$W/q" --by t -- tomorrow "x"; echo "exit $?"
aos-clock-register ls
for i in 1 2 3 4; do aos-clock "$W/clock"; echo "cycle $(cat $W/clock): $(ls $W/q/new | wc -l) letters"; done
aos-clock-register ls
for n in $(ls $W/q/new); do python3 -c "import json,sys;print(json.load(open(sys.argv[1]))[\"body\"][\"content\"])" "$W/q/new/$n/letter.json"; done
