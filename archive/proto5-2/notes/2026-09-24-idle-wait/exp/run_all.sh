#!/bin/sh
# 照 measure.md 的順序跑實驗 B 的幾組（每組約 1～3 分鐘）。用法：sh run_all.sh SCRATCH [組名…]
# 組名格式 LABEL:N_AGENTS:N_DEFAULT_CPUS[:TICK_MS:INTERVAL_MS]
S=$1; shift
HERE=$(dirname "$0")
for cfg in "$@"; do
  label=$(echo "$cfg" | cut -d: -f1); n=$(echo "$cfg" | cut -d: -f2); d=$(echo "$cfg" | cut -d: -f3)
  tick=$(echo "$cfg" | cut -d: -f4); iv=$(echo "$cfg" | cut -d: -f5)
  python3 "$HERE/b_e2e.py" "$S" "$label" "$n" "$d" 60 ${tick:-1000} ${iv:-1000} > "$S/b-$label.json" 2> "$S/b-$label.err"
  echo "$label rc=$?"
done
