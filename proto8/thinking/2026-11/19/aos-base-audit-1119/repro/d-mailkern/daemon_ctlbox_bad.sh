# 測 daemon 的 ctl 信箱（procs_requests）收到壞信、以及一封認領不了（夾權限 000）的信時：好信還套不套、daemon 會不會卡住或重讀。
source $(dirname $0)/common.sh
R=$RUN/ctlbad; rm -rf $R; mkdir -p $R
echo "[\"sleep\", \"600\"]" > $R/body.json
start_daemon $R || exit 1
B=$R/stack/procs_requests; N=$B/new
mkdir $N/bad1; echo "{oops" > $N/bad1/letter.json
mkdir $N/bad2
mkdir $N/bad3; echo "{\"sender\":\"/x\",\"sent_at\":\"x\",\"body\":{\"procs_added\":{\"x\":5}}}" > $N/bad3/letter.json
echo "{\"procs_added\": {\"good1\": \"$R/body.json\"}}" | c aos-post send $B >/dev/null
sleep 1.5
echo "== after bad letters"; ctl $R ls; python3 -c "import json;print(json.load(open(\"$R/stack/state_flux.json\")).get(\"mailbox_warning\"))"; ls $N $B/cur
echo "== unclaimable letter (dir mode 000) then good2"
mkdir -m 555 $N/00000000000000000001.x.y   # 認領要 rename 夾，夾本身不可寫就 EACCES（跨帳號寄的信夾 755 屬於別人時同理）
echo "{\"procs_added\": {\"good2\": \"$R/body.json\"}}" | c aos-post send $B >/dev/null
sleep 2
ctl $R ls; python3 -c "import json;d=json.load(open(\"$R/stack/state_flux.json\"));print({k:d.get(k) for k in (\"mailbox_warning\",\"warning\",\"error\")})"; ls $N; tail -3 $R/daemon.err
echo "== ping while blocked"; T=8 ctl $R ping --timeout-s 3; echo "ping exit=$?"
chmod 755 $N/00000000000000000001.x.y; sleep 1.5
echo "== after unblocking"; ctl $R ls
stop_daemon $R
