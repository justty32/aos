#!/bin/bash
# go.sh MODELTAG MODEL VARIANT REP
cd /tmp/ap5-node
D=/home/lorkhan/repo/simple_tools/aos-wt/AP5/proto7-2/notes/play/2026-10-09-real-ai/evidence/apprentice5
out=/tmp/ap5-runs/$1-$3$4
mkdir -p $out
python3 $D/drive5.py $3 $out --rep $4 --tag $5 --model $2 --calls /tmp/ap5-runs/calls.jsonl --max-calls 900 > $out/drive.log 2>&1
echo "$1-$3$4 exit $?" >> /tmp/ap5-runs/done.log
