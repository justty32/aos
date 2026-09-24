#!/bin/sh
# 實驗 4：每次啟動的代價（跑 N 次 /bin/true 的平均毫秒）。
N=${1:-200}
t() { # 標籤 指令...
  label=$1; shift
  s=$(date +%s%N); i=0
  while [ $i -lt $N ]; do "$@" >/dev/null 2>&1; i=$((i+1)); done
  e=$(date +%s%N)
  echo "$label: $(( (e-s)/N/1000 )) us/次"
}
t "直接 /bin/true" /bin/true
t "unshare -U -r" unshare -U -r /bin/true
t "bwrap --unshare-user --uid（整台唯讀）" bwrap --ro-bind / / --unshare-user --uid 2001 /bin/true
t "bwrap --unshare-all 只掛 /usr" bwrap --ro-bind /usr /usr --symlink usr/bin /bin --symlink usr/lib /lib --symlink usr/lib64 /lib64 --dev /dev --proc /proc --unshare-all --clearenv /usr/bin/true
t "unshare --map-auto（呼叫 newuidmap）＋setpriv" unshare --map-auto --map-root-user --fork setpriv --reuid 1001 --regid 1001 --clear-groups /bin/true
