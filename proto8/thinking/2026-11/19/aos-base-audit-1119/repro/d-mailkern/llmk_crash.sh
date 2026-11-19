# 測 llm kernel 掛掉／重起：kill -9 這台 llm daemon 時在途（已掛上、正在跑）與剛收（還在 new/）的問腦信會怎樣、會不會重打端點、帳會不會重算；
# 以及 kernel 本身每輪出錯（壞 used.json、requests/new 裡一封認領不了的信）時問腦的人看到什麼。
source $(dirname $0)/llmk_common.sh
K=$RUN/llmk3; llmk_setup $K || exit 1; llmk_start $K
B=$K/box; c aos-post init $B >/dev/null
send() { echo "{\"endpoint\": \"$1\", \"request\": {\"messages\": [{\"role\": \"user\", \"content\": \"$2\"}]}}" | c env AOS_LLM_KERNEL=$K/stack aos-llm send --reply-to $B 2>&1 | tail -1; }
for i in 1 2 3; do send slow inflight$i > $K/name_inflight$i; done
sleep 2.5
echo "== in flight:"; c aos-daemon-ctl -d $K/stack ls | grep llm_ | cut -c1-60
P=$(cat $K/daemon.pid); [ "$(readlink /proc/$P/cwd)" = "$K/def" ] && kill -9 $P && echo "killed llm daemon $P (kill -9)"
sleep 0.5
for i in 1 2; do send fake whiledown$i > $K/name_down$i; done   # 寄件人會看到什麼
echo "== while down, sync ask (8 s limit):"; ask $K fake syncdown 8 2>&1 | tail -2
sleep 6   # 讓孤兒問腦 proc 跑完
echo "orphan endpoint procs still around: $(pgrep -f "$K/eps/fk" | wc -l)"
llmk_start $K; echo "restarted pid $(cat $K/daemon.pid)"
sleep 12
echo "== replies in box:"; c aos-post take-all $B > $K/got.txt; wc -l < $K/got.txt
for n in $(cat $K/got.txt); do python3 -c "import json,sys;d=json.load(open(sys.argv[1]));b=d[\"body\"];print(d.get(\"in_reply_to\"), (b.get(\"message\") or {}).get(\"content\") or b.get(\"error\"))" $B/cur/$n/letter.json; done
echo "== endpoint calls per message:"; python3 -c "
import json,collections
c=collections.Counter(json.loads(l)[\"msg\"] for l in open(\"$K/eps/calls.log\"))
print(dict(c))"
echo "== ledger ids:"; python3 -c "
import json,collections
rows=[json.loads(l) for l in open(\"$K/stack/ledger.jsonl\")]
c=collections.Counter(r[\"id\"] for r in rows); print(len(rows),\"rows\", \"dups:\", {k:v for k,v in c.items() if v>1}, [r[\"code\"] for r in rows])"
python3 -c "import json;d=json.load(open(\"$K/stack/used.json\"));print(\"used counter_calls\", d[\"counter_calls\"])"
echo "== kernel left anything in cur/new?"; ls $K/stack/requests/new $K/stack/requests/cur
echo
echo "== unclaimable letter in requests/new (dir mode 555), then a normal ask"
mkdir -m 555 $K/stack/requests/new/zzz.unclaimable
ask $K fake afterblock 8 2>&1 | tail -2
tail -2 $K/daemon.err
echo "daemon table still says:"; c aos-daemon-ctl -d $K/stack ls | tail -2
python3 -c "import json;d=json.load(open(\"$K/stack/state_flux.json\"));print(\"state_flux keys:\", {k:v for k,v in d.items() if k not in (\"updated_at\",)})" | cut -c1-400
chmod 755 $K/stack/requests/new/zzz.unclaimable; sleep 2
echo "== after unblocking:"; ls $K/stack/requests/new $K/stack/requests/cur; ls $K/stack/requests/reply/new 2>/dev/null | wc -l
llmk_stop $K
