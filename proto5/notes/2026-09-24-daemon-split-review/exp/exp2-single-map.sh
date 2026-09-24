#!/bin/sh
# 實驗 2：bwrap --unshare-user --uid／unshare -U 的「單一對應」——看起來換了 uid，擋不擋得住讀別的家？
# 擺設：$W/homeA/secret、$W/homeB/secret，兩個都是 lorkhan 擁有、700／600。
W=${1:-$(mktemp -d)}
mkdir -p "$W/homeA" "$W/homeB"
echo secret-A > "$W/homeA/secret"; echo secret-B > "$W/homeB/secret"
chmod 700 "$W/homeA" "$W/homeB"; chmod 600 "$W/homeA/secret" "$W/homeB/secret"

echo "== 2a: bwrap --unshare-user --uid 2001 --gid 2001，整台 / 唯讀掛進去，讀 homeB"
bwrap --ro-bind / / --dev /dev --proc /proc --unshare-user --uid 2001 --gid 2001 \
  sh -c "id; cat $W/homeB/secret; stat -c '%u:%g %n' $W/homeB/secret" 2>&1; echo "exit=$?"

echo "== 2b: unshare -U --map-user=2001 --map-group=2001，讀 homeB"
unshare -U --map-user=2001 --map-group=2001 \
  sh -c "id; cat $W/homeB/secret; stat -c '%u:%g %n' $W/homeB/secret" 2>&1; echo "exit=$?"

echo "== 2c: 單一對應下還能不能再切成第二個 uid（setpriv --reuid 2002）"
unshare -U -r sh -c "setpriv --reuid 2002 --regid 2002 --clear-groups id" 2>&1; echo "exit=$?"

echo "== 2d: bwrap 只掛 homeA（換 uid 無關，靠的是『沒掛』）讀 homeB"
bwrap --ro-bind /usr /usr --symlink usr/bin /bin --symlink usr/lib /lib --symlink usr/lib64 /lib64 \
  --bind "$W/homeA" /home/me --dev /dev --proc /proc --unshare-all --clearenv \
  --uid 2001 --gid 2001 --chdir /home/me \
  /bin/sh -c "id; cat secret; cat $W/homeB/secret" 2>&1; echo "exit=$?"
