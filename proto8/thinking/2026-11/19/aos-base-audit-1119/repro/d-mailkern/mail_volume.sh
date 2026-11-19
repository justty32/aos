# 測信箱量與並發：一個行程連寄 200 封的順序／不丟／不重複；兩個行程同時各寄 150 封給同一信箱；5 MB 正文；多附件（信夾裡多放檔）。不需 daemon。
source $(dirname $0)/common.sh
R=$RUN/mailvol; rm -rf $R; mkdir -p $R/me $R/a $R/b
c aos-mailbox -s $R/me where >/dev/null
BOX=$R/me/mailbox
echo "== 200 sequential"
t0=$(date +%s.%N)
for i in $(seq -w 1 200); do c aos-mailbox -s $R/a send --box $BOX --status PROGRESS --title "n$i" "seq $i" >/dev/null || echo "send $i failed"; done
t1=$(date +%s.%N); echo "send time: $(echo "$t1 - $t0" | bc) s"
c aos-mailbox -s $R/me read --all -j > $R/read1.jsonl; echo "read exit=$?"
python3 - $R/read1.jsonl <<"P"
import json,sys
rows=[json.loads(l) for l in open(sys.argv[1])]
t=[r["title"] for r in rows]
print("read", len(t), "unique", len(set(t)), "in order", t==sorted(t))
P
echo "== 2 concurrent senders x150 (aos-post direct)"
for who in a b; do ( for i in $(seq -w 1 150); do echo "{\"who\":\"$who\",\"i\":\"$i\"}" | c env AOS_STACK=$R/$who aos-post send $BOX >/dev/null || echo "fail $who $i"; done ) & done; wait
ls $BOX/new | wc -l
c aos-post take-all $BOX > $R/taken.txt; echo "take-all exit=$? n=$(wc -l < $R/taken.txt)"
python3 - $BOX $R/taken.txt <<"P"
import json,sys,os
box=sys.argv[1]; names=open(sys.argv[2]).read().split()
per={"a":[],"b":[]}
for n in names:
    b=json.load(open(os.path.join(box,"cur",n,"letter.json")))["body"]; per[b["who"]].append(b["i"])
for k,v in per.items(): print(k, len(v), "unique", len(set(v)), "in-order-per-sender", v==sorted(v))
P
for n in $(cat $R/taken.txt); do c aos-post done $BOX $n; done
echo "== ordered concurrent x100 each"
for who in a b; do ( for i in $(seq -w 1 100); do echo "{\"who\":\"$who\",\"i\":\"$i\"}" | c env AOS_STACK=$R/$who aos-post send --ordered $BOX >/dev/null || echo "fail $who $i"; done ) & done; wait
c aos-post take-all $BOX > $R/taken2.txt; head -2 $R/taken2.txt; tail -1 $R/taken2.txt; echo "n=$(wc -l < $R/taken2.txt) uniq-seq=$(cut -c1-12 $R/taken2.txt | sort -u | wc -l)"; cat $BOX/order.json
for n in $(cat $R/taken2.txt); do c aos-post done $BOX $n; done
echo "== 5 MB body"
python3 -c "print(\"x\"*5*1024*1024)" > $R/big.txt
/usr/bin/time -f "send %es %MKB" $CLEAN aos-mailbox -s $R/a send --box $BOX --status DONE --title big - < $R/big.txt
du -sh $BOX/new/*
/usr/bin/time -f "peek %es" $CLEAN aos-mailbox -s $R/me peek | cut -c1-80
/usr/bin/time -f "read %es %MKB" $CLEAN aos-mailbox -s $R/me read -j | wc -c
echo "== 50 MB body via aos-post"
python3 -c "import json;print(json.dumps({\"what\":\"y\"*50*1024*1024}))" > $R/big50.json
/usr/bin/time -f "post send 50MB %es %MKB" $CLEAN aos-post send $BOX < $R/big50.json; echo "exit=$?"
/usr/bin/time -f "see 50MB %es %MKB" $CLEAN aos-mailbox -s $R/me read -j | wc -c
rm -f $R/big.txt $R/big50.json
echo "== attachments: 1000 extra files in a letter folder"
n=$(echo "{\"from\":\"a\",\"status\":\"DONE\",\"title\":\"att\",\"what\":\"w\"}" | c aos-post send $BOX)
for i in $(seq 1000); do echo $i > $BOX/new/$n/att$i.txt; done
c aos-mailbox -s $R/me read -j | cut -c1-120; echo "exit=$?"; ls $BOX/tmp $BOX/cur | wc -l
