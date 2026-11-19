# 測框架站（daemon-kernel 範本，daemon 的身體＝kernel 站）：白名單、max_running＋排隊期限、after_verdict hold 沒人表態（有期限／沒期限）、
# 站被 kill -9 時寄來的請求、requests/new 裡一封認領不了的信。
source $(dirname $0)/common.sh
SRC=$A/src/proto8
S=$RUN/kst; rm -rf $S; mkdir -p $S/stack $S/box $S/h
cp -r $SRC/templates/kernel/daemon-kernel $S/def
cat > $S/h/holdh <<"P"
#!/usr/bin/env python3
# 只 hold 名字 h 開頭的 procs_added
import json, sys
e = json.load(sys.stdin); b = e.get("body") if isinstance(e.get("body"), dict) else {}
if any(k.startswith("h") for k in (b.get("procs_added") or {})): print(json.dumps({"verdict": "hold"}))
P
chmod +x $S/h/holdh
echo "{\"allowed\": [\"w1\", \"w2\", \"w3\", \"h1\", \"h2\", \"k1\", \"k2\"], \"max_running\": 2, \"queue\": true, \"hooks\": {\"hold\": {\"event\": \"after_verdict\", \"condition\": \"pass\", \"handler\": \"$S/h/holdh\"}}}" > $S/def/kernel.json
echo "[\"sleep\", \"600\"]" > $S/body.json
( cd $S && setsid $CLEAN aos-exec --stack $S/stack $S/def >>$S/daemon.log 2>>$S/daemon.err & )
for i in $(seq 100); do grep -qs "\"pid\"" $S/stack/procs_state.json && [ -d $S/stack/requests/new ] && break; sleep 0.1; done
python3 -c "import json;print(json.load(open(\"$S/stack/procs_state.json\"))[\"pid\"])" > $S/daemon.pid
c aos-post init $S/box >/dev/null
req() { echo "$1" | c aos-post send --reply-to $S/box $S/stack/requests; }
replies() { c aos-post take-all $S/box 2>/dev/null | while read n; do python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(\"  reply\", d[\"body\"])" $S/box/cur/$n/letter.json; c aos-post done $S/box $n; done; }
req "{\"procs_added\": {\"w1\": \"$S/body.json\"}}" >/dev/null
req "{\"procs_added\": {\"bad\": \"$S/body.json\"}}" >/dev/null
req "{\"procs_added\": {\"w2\": \"$S/body.json\"}}" >/dev/null
sleep 2; echo "== w1, bad(not allowed), w2"; replies
req "{\"procs_added\": {\"w3\": \"$S/body.json\"}, \"queue_wait_ms\": 2500}" >/dev/null
sleep 4; echo "== w3 queued (max_running 2), deadline 2.5 s"; replies; cat $S/stack/queue.json 2>/dev/null; echo
c aos-daemon-ctl -d $S/stack rm w2 >/dev/null; sleep 1
req "{\"procs_added\": {\"h1\": \"$S/body.json\"}, \"queue_wait_ms\": 2500}" >/dev/null
req "{\"procs_added\": {\"h2\": \"$S/body.json\"}}" >/dev/null
sleep 4; echo "== h1 held with deadline 2.5 s, h2 held without deadline (4 s later)"; replies; echo "hold.json:"; cat $S/stack/hold.json 2>/dev/null; echo
echo "== decide h2 pass"; n=$(python3 -c "import json;d=json.load(open(\"$S/stack/hold.json\"));print(list(d[\"held\"] if \"held\" in d else d)[0])" 2>/dev/null); echo "held letter: $n"
mkdir -p $S/stack/decisions; echo "{\"verdict\": \"pass\"}" > $S/stack/decisions/$n.json; sleep 2; replies
c aos-daemon-ctl -d $S/stack ls | cut -c1-50
echo "== kill -9 the station daemon, send k1 while down, restart"
P=$(cat $S/daemon.pid); [ "$(readlink /proc/$P/cwd)" = "$S/def" ] && kill -9 $P && echo "killed $P"
c aos-daemon-ctl -d $S/stack rm w1 2>&1 | tail -1
c aos-daemon-ctl -d $S/stack rm h2 2>&1 | tail -1
req "{\"procs_added\": {\"k1\": \"$S/body.json\"}, \"queue_wait_ms\": 30000}" >/dev/null; sleep 1
( cd $S && setsid $CLEAN aos-exec --stack $S/stack $S/def >>$S/daemon.log 2>>$S/daemon.err & ); sleep 3
python3 -c "import json;print(json.load(open(\"$S/stack/procs_state.json\"))[\"pid\"])" > $S/daemon.pid
replies; c aos-daemon-ctl -d $S/stack ls | cut -c1-50
echo "== unclaimable entry in station requests/new, then k2"
mkdir -m 555 $S/stack/requests/new/zzz.unclaimable
req "{\"procs_added\": {\"k2\": \"$S/body.json\"}}" >/dev/null; sleep 3; replies; echo "(no reply above = stalled)"; tail -1 $S/daemon.err
c aos-daemon-ctl -d $S/stack ls | cut -c1-50
chmod 755 $S/stack/requests/new/zzz.unclaimable; sleep 2; echo "after unblocking:"; replies
T=30 c aos-daemon-ctl -d $S/stack shutdown; for i in $(seq 50); do kill -0 $(cat $S/daemon.pid) 2>/dev/null || break; sleep 0.2; done
