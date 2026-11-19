# 測一封認領不了的信排在好信「後面」時：take-all 已搬進 cur/ 的好信會不會被套、還是卡在 cur/ 直到 daemon 重起。
source $(dirname $0)/common.sh
R=$RUN/ctlbad2; rm -rf $R; mkdir -p $R
echo "[\"sleep\", \"600\"]" > $R/body.json
start_daemon $R || exit 1
B=$R/stack/procs_requests; N=$B/new
# 先暫停讓兩封同一圈被看到：用 tmp 寫好再一起放
c aos-daemon-ctl -d $R/stack ping >/dev/null
mkdir -p $R/stage
echo "{\"procs_added\": {\"good3\": \"$R/body.json\"}}" | c aos-post send $B >/dev/null   # 名字 0179... 排在前
mkdir -m 555 $N/zzz.unclaimable
sleep 2
echo "== good3 then zzz (unclaimable) in the same round"; ctl $R ls; echo "new:"; ls $N; echo "cur:"; ls $B/cur
python3 -c "import json;print(json.load(open(\"$R/stack/state_flux.json\")).get(\"mailbox_warning\"))"
chmod 755 $N/zzz.unclaimable; sleep 2
echo "== after unblocking"; ctl $R ls; echo "cur:"; ls $B/cur
stop_daemon $R
echo "== restart"; start_daemon $R; sleep 2; ctl $R ls; echo "cur:"; ls $B/cur
stop_daemon $R
