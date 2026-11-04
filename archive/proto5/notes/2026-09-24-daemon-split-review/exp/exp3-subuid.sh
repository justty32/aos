#!/bin/sh
# 實驗 3：用 /etc/subuid 已有的 65536 個副 uid（lorkhan:100000:65536，系統原本就配好的，這裡只讀不改），
# 不用 root 開一個多 uid 的 user namespace（像 rootless podman），在裡面把兩個家 chown 給兩個不同 uid，
# 再讓「A 的孩子」用 setpriv 降成 A 的 uid，看讀不讀得到 B 的家。
# newuidmap／newgidmap 是系統裝好的帶權限小幫手；這裡只呼叫它，不改它。
# 用法：sh exp3-subuid.sh <工作資料夾>
W=${1:?給一個工作資料夾}
mkdir -p "$W"
unshare --map-auto --map-root-user --mount --fork sh -s "$W" <<'IN'
W=$1
echo "-- 裡面的對應表（裡面 uid → 外面 uid → 幾個）"; cat /proc/self/uid_map
mkdir -p "$W/homeA" "$W/homeB"
echo secret-A > "$W/homeA/secret"; echo secret-B > "$W/homeB/secret"
chown -R 1001:1001 "$W/homeA"; chown -R 1002:1002 "$W/homeB"
chmod 700 "$W/homeA" "$W/homeB"; chmod 600 "$W/homeA/secret" "$W/homeB/secret"
ls -ln "$W"
DROP="setpriv --reuid 1001 --regid 1001 --clear-groups --inh-caps=-all --bounding-set=-all"
echo "== 3p: A 的孩子（uid 1001）走原路徑進自己的家（祖先資料夾是 lorkhan 的 700）"
$DROP sh -c "cat $W/homeA/secret"; echo "exit=$?"
# 祖先擋路，改用 bind mount 把工作資料夾掛到 /mnt，繞開祖先
mount --bind "$W" /mnt
echo "== 3a: A 的孩子讀自己的家（經 /mnt）"
$DROP sh -c "id; cat /mnt/homeA/secret"; echo "exit=$?"
echo "== 3b: A 的孩子讀 B 的家"
$DROP sh -c "cat /mnt/homeB/secret"; echo "exit=$?"
echo "== 3c: A 的孩子想再切成 1002 或 0"
$DROP sh -c "setpriv --reuid 1002 id"; echo "exit=$?"
$DROP sh -c "setpriv --reuid 0 id"; echo "exit=$?"
echo "== 3d: A 的孩子讀 lorkhan 的 HOME（裡面看是 uid 0 的 700）"
$DROP sh -c "ls $HOME"; echo "exit=$?"
IN
echo "== 3e: 從外面（lorkhan 本人、不在 namespace 裡）看這兩個家"
ls -ln "$W"
cat "$W/homeA/secret"; echo "exit=$?"
echo "== 3f: 外面的 lorkhan 直接刪"
rm -rf "$W/homeA" 2>&1 | head -2
[ -d "$W/homeA" ] && echo "homeA 還在（刪不掉）" || echo "刪掉了"
echo "-- 進 namespace 清理"
unshare --map-auto --map-root-user --fork rm -rf "$W/homeA" "$W/homeB"; echo "cleanup exit=$?"
ls -A "$W"
