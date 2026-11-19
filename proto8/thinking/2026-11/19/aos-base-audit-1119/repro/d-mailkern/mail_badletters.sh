# 測壞信：letter.json 壞 JSON／缺欄／二進位／只有夾／半寫／new 裡一般檔／letter.json 是夾／權限 000，aos-mailbox read 與 mail_notify（peek）會不會卡住、重讀。
source $(dirname $0)/common.sh
R=$RUN/mailbad; rm -rf $R; mkdir -p $R/me $R/a
c aos-mailbox -s $R/me where >/dev/null
BOX=$R/me/mailbox; N=$BOX/new
good() { c aos-mailbox -s $R/a send --box $BOX --status DONE --title "$1" "w" >/dev/null; }
good g1
mkdir $N/b1.badjson; echo "{not json" > $N/b1.badjson/letter.json
mkdir $N/b2.nosender; echo "{\"sent_at\":\"x\",\"body\":{}}" > $N/b2.nosender/letter.json
mkdir $N/b3.binary; head -c 200 /dev/urandom > $N/b3.binary/letter.json
mkdir $N/b4.emptydir
mkdir $N/b5.half; echo -n "{\"sender\":\"/x\",\"sent_at\":\"2026\",\"body\":{\"title\":\"hal" > $N/b5.half/letter.json
echo "plain" > $N/b6.plainfile
mkdir -p $N/b7.jsondir/letter.json
mkdir $N/b8.array; echo "[1,2]" > $N/b8.array/letter.json
mkdir $N/b9.bodystring; echo "{\"sender\":\"/x\",\"sent_at\":\"2026\",\"body\":\"just text\"}" > $N/b9.bodystring/letter.json
good g2
echo "== peek"; c aos-mailbox -s $R/me peek; echo "peek exit=$?"
echo "== mail_notify on it"
mkdir -p $R/me/hooks/mail_notify
echo "{\"event\":\"on_clock\",\"stack\":\"$R/me\",\"first\":false}" | c env AOS_STACK=$R/me/hooks/mail_notify $A/src/proto8/lib/tools/agent/mail_notify/_entry; echo "notify exit=$?"
c aos-post take-all $R/me/queue >/dev/null 2>&1; for x in $R/me/queue/cur/*/letter.json; do python3 -c "import json,sys;print(json.load(open(sys.argv[1]))[\"body\"][\"content\"])" $x; done
echo "== read --all"
c aos-mailbox -s $R/me read --all -j | python3 -c "import sys,json;[print(\"READ\",json.loads(l).get(\"title\"),json.loads(l).get(\"what\")) for l in sys.stdin]"; echo "read exit=${PIPESTATUS[0]}"
echo "left new:"; ls $N; echo "left cur:"; ls $BOX/cur; echo "left tmp:"; ls $BOX/tmp
echo "== perm 000 letter dir"
good g3; n=$(ls $N | head -1); chmod 000 $N/$n
c aos-mailbox -s $R/me read -j; echo "read1 exit=$?"
c aos-mailbox -s $R/me read -j; echo "read2 exit=$?"
good g4; c aos-mailbox -s $R/me read -j | cut -c1-90; echo "read3 exit=$?"
echo "new:"; ls $N; echo "cur:"; ls $BOX/cur; echo "tmp:"; ls $BOX/tmp
chmod -R 700 $BOX
