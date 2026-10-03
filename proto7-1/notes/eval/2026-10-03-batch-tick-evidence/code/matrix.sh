#!/bin/bash
cd "$(dirname "$0")"
for c in 50 100 200; do
 for w in empty each3; do
  for spec in "base 0 1" "btick 0 1" "bboth 0 1" "bboth 16 4" "cheap 0 1"; do
    set -- $spec
    python3 bench.py --mode $1 --k $2 --par $3 --count $c --work $w --seconds 15 --out ev/m-$1-k$2p$3-$w-$c.json > /dev/null 2>>ev/matrix.err
    echo "done $1 $2 $3 $w $c $(cat /proc/loadavg)" >> ev/matrix.progress
  done
 done
 python3 bench.py --mode cfloor --count $c --work empty --seconds 15 --out ev/m-cfloor-k0p1-empty-$c.json > /dev/null 2>>ev/matrix.err
 echo "done cfloor empty $c" >> ev/matrix.progress
done
echo ALLDONE >> ev/matrix.progress
