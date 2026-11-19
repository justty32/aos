# 測 aos-mailbox send --to 在收件人：在跑、停著、已 rm、stack 被刪、--box 不存在時的結果（寄件人看到什麼、信落在哪）。
source $(dirname $0)/common.sh
R=$RUN/mailrcpt; rm -rf $R; mkdir -p $R
echo "[\"sleep\", \"600\"]" > $R/body.json
start_daemon $R || exit 1
S=$R/sender; mkdir -p $S
for n in alive stopped removed purged; do ctl $R add --name $n $R/body.json >/dev/null; done
sleep 1
ctl $R stop stopped; ctl $R rm removed; ctl $R rm purged; sleep 1
ctl $R ls
PS=$(ctl $R where --stack alive); echo "alive stack: $PS"
rm -rf $R/stack/procs/purged
send() { c aos-mailbox -s $S send --to $1 -d $R/stack --status REQUEST --title "t $1" "hello $1"; echo "exit=$?"; }
for n in alive stopped removed purged nosuch; do echo "--- to $n"; send $n; done
echo "--- box missing"; c aos-mailbox -s $S send --box $R/nobox --status REQUEST --title t hi; echo "exit=$?"
echo "--- where letters landed"; find $R/stack/procs -path "*mailbox/new/*" -maxdepth 5 -name letter.json | sed "s|$R/||"
echo "--- removed row: stack kept? "; ls $R/stack/procs/
echo "--- relative cwd test: sender in another cwd"; (cd /tmp && c aos-mailbox -s $S send --to alive -d $R/stack --status REQUEST --title rel x; echo "exit=$?")
stop_daemon $R
