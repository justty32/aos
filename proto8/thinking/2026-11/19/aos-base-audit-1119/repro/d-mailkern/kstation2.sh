# 測框架站 hold：after_verdict hold 有期限沒人表態、沒期限、表態 pass；站被 kill -9 時寄來的請求；requests/new 裡一封認領不了的信。max_running 寬（10）避免排隊干擾。
source $(dirname $0)/common.sh
SRC=$A/src/proto8
S=$RUN/kst2; rm -rf $S; mkdir -p $S/stack $S/box $S/h
cp -r $SRC/templates/kernel/daemon-kernel $S/def
cat > $S/h/holdh <<"P"
#!/usr/bin/env python3
# 只 hold 名字 h 開頭的 procs_added
import json, sys
e = json.load(sys.stdin); b = e.get("body") if isinstance(e.get("body"), dict) else {}
if any(k.startswith("h") for k in (b.get("procs_added") or {})): print(json.dumps({"verdict": "hold"}))
P
chmod +x $S/h/holdh
echo "{\"max_running\": 10, \"queue\": true, \"hooks\": {\"hold\": {\"event\": \"after_verdict\", \"condition\": \"pass\", \"handler\": \"$S/h/holdh\"}}}" > $S/def/kernel.json
echo "[\"sleep\", \"600\"]" > $S/body.json
st() { ( cd $S && setsid $CLEAN aos-exec --stack $S/stack $S/def >>$S/daemon.log 2>>$S/daemon.err & ); for i in $(seq 100); do grep -qs "\"pid\"" $S/stack/procs_state.json && [ -d $S/stack/requests/new ] && break; sleep 0.1; done; sleep 0.5; python3 -c "import json;print(json.load(open(\"$S/stack/procs_state.json\"))[\"pid\"])" > $S/daemon.pid; }
st
c aos-post init $S/box >/dev/null
req() { echo "$1" | c aos-post send --reply-to $S/box $S/stack/requests; }
replies() { c aos-post take-all $S/box 2>/dev/null | while read n; do python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(\"  reply\", d.get(\"in_reply_to\")[-12:], d[\"body\"])" $S/box/cur/$n/letter.json; c aos-post done $S/box $n; done; }
req "{\"procs_added\": {\"h1\": \"$S/body.json\"}, \"queue_wait_ms\": 2500}" >/dev/null
H2=$(req "{\"procs_added\": {\"h2\": \"$S/body.json\"}}")
sleep 4.5; echo "== h1 held (deadline 2.5 s), h2 held (no deadline), after 4.5 s"; replies; echo "hold.json: $(cat $S/stack/hold.json 2>/dev/null)"; ls $S/stack
echo "== decide h2 pass via decisions/"; mkdir -p $S/stack/decisions; echo "{\"verdict\": \"pass\"}" > $S/stack/decisions/$H2.json; sleep 2; replies; c aos-daemon-ctl -d $S/stack ls | grep h2 | cut -c1-40
echo "== kill -9 station daemon; send k1 while down; restart"
P=$(cat $S/daemon.pid); [ "$(readlink /proc/$P/cwd)" = "$S/def" ] && kill -9 $P 2>/dev/null && echo "killed $P"
req "{\"procs_added\": {\"k1\": \"$S/body.json\"}, \"queue_wait_ms\": 30000}" >/dev/null; sleep 1
st; sleep 2; replies; c aos-daemon-ctl -d $S/stack ls | grep k1 | cut -c1-40
echo "== unclaimable entry in station requests/new, then k2 (wait 3 s)"
mkdir -m 555 $S/stack/requests/new/zzz.unclaimable
req "{\"procs_added\": {\"k2\": \"$S/body.json\"}}" >/dev/null; sleep 3; replies; echo "(no reply above = stalled)"; tail -1 $S/daemon.err
python3 -c "import json;d=json.load(open(\"$S/stack/state_flux.json\"));print(\"daemon mailbox_warning:\", d.get(\"mailbox_warning\"))"
chmod 755 $S/stack/requests/new/zzz.unclaimable; sleep 2; echo "after unblocking:"; replies
T=30 c aos-daemon-ctl -d $S/stack shutdown; for i in $(seq 50); do kill -0 $(cat $S/daemon.pid) 2>/dev/null || break; sleep 0.2; done
