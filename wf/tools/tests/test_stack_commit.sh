#!/bin/bash
# test_stack_commit.sh — 11-23 起退場：stack 不再跟著 git 搬（使用者「直接變成.stack，然後把它git ignore，就這樣。換機那一套就不用了。」），留著等使用者決定刪不刪。原本在 repo 外的暫存 clone 上測換機工具 stack_commit.py（daemon 沒停就拒、_stack 外髒檔、llm kernel 還沒回的信、金鑰樣式、只挑該帶走的檔、第二次沒東西、改／刪／加、index_gen 照綠、arrive 清執行期檔與查殼、pull 會蓋掉被忽略的檔）；不碰來源 repo
# 用法：test_stack_commit.sh <來源 repo> <repo 外的暫存夾>   每次在暫存夾下開一個新的 run-<時間> 子夾，不刪任何東西；殼裡要先清掉 AOS_*（有 aos-exec 就用真的 daemon，沒有就用一支握鎖的小行程代替）
set -u
[ -n "${BASH_VERSION:-}" ] || { echo "not bash" >&2; exit 1; }
SRC=$(readlink -f "${1:?source repo}")
WORK=$(readlink -f "${2:?work folder outside the repo}")
case "$WORK/" in "$SRC"/*) echo "work folder must be outside the repo" >&2; exit 1;; esac
for v in $(compgen -e | grep '^AOS_' | grep -v '^AOS_HOME$'); do echo "$v is set: clear AOS_* first (AOS_HOME may stay)" >&2; exit 1; done
TOOL=$(dirname "$(readlink -f "$0")")/../stack_commit.py
RUN="$WORK/run-$(date +%Y%m%d-%H%M%S)-$$"
R="$RUN/repo"; C="$RUN/cache"; ST="$R/_stack"
mkdir -p "$RUN" || exit 1
git clone -q "$SRC" "$R" || exit 1
cd "$R" || exit 1
PASS=0; FAIL=0
ok()  { PASS=$((PASS+1)); echo "  ok   $*"; }
bad() { FAIL=$((FAIL+1)); echo "  FAIL $*"; }
check() { local d="$1"; shift; if "$@"; then ok "$d"; else bad "$d"; fi; }
sc() { local cmd="$1"; shift; if [ "$cmd" = leave ]; then python3 "$TOOL" leave --repo "$R" --cache "$C" --wait 60 "$@"; else python3 "$TOOL" "$cmd" --repo "$R" "$@"; fi; }
code_of() { tail -1 "$1" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("code"))'; }
head_() { git rev-parse main; }
export -f code_of
in_head() { git cat-file -e "main:$1" 2>/dev/null; }
# 自己起的行程：只 kill 記下的 pid，kill 前確認 cwd 在 RUN 裡（硬規則第 4 條）
PIDS=()
kill_mine() { local p; for p in "${PIDS[@]}"; do kill -0 "$p" 2>/dev/null || continue; case "$(readlink /proc/$p/cwd)/" in "$RUN"/*) kill "$p";; *) echo "  not killing $p: cwd outside $RUN" >&2;; esac; done; }
trap kill_mine EXIT
holder() { (cd "$RUN" && exec python3 -c 'import fcntl,os,sys,time; fd=os.open(sys.argv[1],os.O_RDONLY|os.O_DIRECTORY); fcntl.flock(fd,fcntl.LOCK_EX); open(sys.argv[2],"w").close(); time.sleep(600)' "$1" "$2") & PIDS+=($!); for _ in $(seq 50); do [ -f "$2" ] && break; sleep 0.1; done; }
REAL=0; command -v aos-exec >/dev/null && command -v aos-daemon-ctl >/dev/null && [ -d wf/tree/root ] && REAL=1
start_daemon() {   # $1 = stack (absolute), $2 = log
  (cd "$RUN" && exec env -u AOS_DAEMON -u AOS_STACK -u AOS_CLOCK aos-exec --stack "$1" "$R/wf/tree/root") > "$2" 2>&1 & PIDS+=($!)
  for _ in $(seq 100); do [ -f "$1/state.json" ] && aos-daemon-ctl -d "$1" ping >/dev/null 2>&1 && return 0; sleep 0.2; done; return 1; }
stop_daemon() { echo "  shutdown $1" ; case "$1/" in "$RUN"/*) aos-daemon-ctl -d "$1" shutdown >/dev/null 2>&1;; *) echo "refuse: $1 not in $RUN" >&2;; esac
  for _ in $(seq 100); do python3 -c 'import fcntl,os,sys; fcntl.flock(os.open(sys.argv[1],os.O_RDONLY|os.O_DIRECTORY),fcntl.LOCK_EX|fcntl.LOCK_NB)' "$1" 2>/dev/null && return 0; sleep 0.2; done; return 1; }

echo "== T1 no _stack yet"
sc leave > "$RUN/t1.out" 2>&1; E=$?
check "leave without _stack → StackMissing, exit 3 ($E)" bash -c "[ $E = 3 ] && grep -q StackMissing $RUN/t1.out"
sc arrive > "$RUN/t1b.out" 2>&1; E=$?
check "arrive without _stack → says so, exit 0 ($E)" bash -c "[ $E = 0 ] && grep -q 'does not exist here yet' $RUN/t1b.out"

echo "== T2 refuses while a daemon holds _stack (real daemon: $REAL)"
if [ $REAL = 1 ]; then
  check "root daemon started on _stack" start_daemon "$ST" "$RUN/root.log"
else
  mkdir -p "$ST"; holder "$ST" "$RUN/held1"
fi
sc leave > "$RUN/t2.out" 2>&1; E=$?
check "leave → DaemonRunning, exit 2 ($E)" bash -c "[ $E = 2 ] && grep -q DaemonRunning $RUN/t2.out && grep -q 'aos-daemon-ctl -d $ST shutdown' $RUN/t2.out"
sc arrive > "$RUN/t2b.out" 2>&1; E=$?
check "arrive → DaemonRunning, exit 2 ($E)" bash -c "[ $E = 2 ] && grep -q DaemonRunning $RUN/t2b.out"
sc status > "$RUN/t2c.out" 2>&1; E=$?
check "status says running, exit 0 ($E)" bash -c "[ $E = 0 ] && tail -1 $RUN/t2c.out | grep -q '\"running\": true'"
if [ $REAL = 1 ]; then check "root daemon shut down" stop_daemon "$ST"; else kill_mine; PIDS=(); fi
mkdir -p "$ST/procs/sub"; holder "$ST/procs/sub" "$RUN/held2"
sc leave > "$RUN/t2d.out" 2>&1; E=$?
check "a nested daemon stack still locked → refused ($E), names it" bash -c "[ $E = 2 ] && grep -q '_stack/procs/sub' $RUN/t2d.out"
kill_mine; PIDS=(); rmdir "$ST/procs/sub"

echo "== T3 fake agent files: what travels and what stays"
A="$ST/procs/ann"
mkdir -p "$A/mailbox/new/l1" "$A/mailbox/cur" "$A/mailbox/tmp" "$A/think/reply/new/r1" "$A/tools/subagent" "$A/transcripts" "$A/claude" "$A/hookeds/x" "$A/procs_requests/reply/z"
printf '{"role":"user","content":"hi"}\n' > "$A/history.jsonl"
echo '{"phase":"running"}' > "$A/state.json"; echo think > "$A/stage.txt"; echo l-123 > "$A/think/pending.txt"
echo '{"title":"a letter"}' > "$A/mailbox/new/l1/letter.json"; echo '{"x":1}' > "$A/think/reply/new/r1/letter.json"
echo '{}' > "$A/tools/subagent/subagents.json"
for f in lock .flock live.jsonl turns.jsonl stderr.txt endpoints.json cooldown.json think/request.json think/sent.json think/wait_warned.txt \
         mailbox/tmp/half x.sock sender.flock .session_home transcripts/t.txt claude/env.json claude/session.txt hookeds/x/event.json \
         procs_requests/reply/z/a state.json.bad-1 counter_turns.txt .state.json.tmp; do echo junk > "$A/$f"; done
TRAVEL="history.jsonl state.json stage.txt claude/session.txt think/pending.txt mailbox/new/l1/letter.json think/reply/new/r1/letter.json tools/subagent/subagents.json"
STAY="lock .flock live.jsonl turns.jsonl stderr.txt endpoints.json cooldown.json think/request.json think/sent.json think/wait_warned.txt mailbox/tmp/half x.sock sender.flock .session_home transcripts/t.txt claude/env.json hookeds/x/event.json procs_requests/reply/z/a state.json.bad-1 counter_turns.txt .state.json.tmp"
sc status > "$RUN/t3.out" 2>&1
check "status lists the travelling files as only on this machine" bash -c "grep -q 'new _stack/procs/ann/history.jsonl' $RUN/t3.out && grep -q 'git clean -fdx' $RUN/t3.out"

echo "== T4 uncommitted files outside _stack"
echo dirty > wf/dirty-outside.md
sc leave --dry-run > "$RUN/t4.out" 2>&1; E=$?
check "refused DirtyOutside ($E), lists the file" bash -c "[ $E = 2 ] && grep -q DirtyOutside $RUN/t4.out && grep -q 'wf/dirty-outside.md' $RUN/t4.out"
sc leave --dry-run --leave-dirty > "$RUN/t4b.out" 2>&1; E=$?
check "--leave-dirty goes on ($E)" bash -c "[ $E = 0 ] && [ \"\$(code_of $RUN/t4b.out)\" = DryRun ]"
rm wf/dirty-outside.md

echo "== T5 brain letters from _stack still in the llm kernel"
K="$RUN/llm-stack"; mkdir -p "$K/requests/new/q1" "$K/requests/cur" "$K/requests/tmp"
printf '{"sender": "%s", "reply_to": "%s"}\n' "$A" "$A/think/reply" > "$K/requests/new/q1/letter.json"
AOS_LLM_KERNEL="$K" sc leave --dry-run > "$RUN/t5.out" 2>&1; E=$?
check "absolute AOS_LLM_KERNEL: refused LlmLetters ($E), names new/q1" bash -c "[ $E = 2 ] && grep -q LlmLetters $RUN/t5.out && grep -q 'new/q1: from _stack/procs/ann' $RUN/t5.out"
mv "$K/requests/new/q1" "$K/requests/cur/q1"
AOS_DAEMON="$RUN" AOS_LLM_KERNEL=llm-stack sc leave --dry-run > "$RUN/t5b.out" 2>&1; E=$?
check "relative AOS_LLM_KERNEL (from AOS_DAEMON), letter in cur/: refused ($E)" bash -c "[ $E = 2 ] && grep -q 'cur/q1' $RUN/t5b.out"
AOS_LLM_KERNEL="$K" sc leave --dry-run --ignore-llm > "$RUN/t5c.out" 2>&1; E=$?
check "--ignore-llm goes on ($E)" bash -c "[ $E = 0 ] && grep -q 'not answered yet (--ignore-llm)' $RUN/t5c.out"
printf '{"sender": "/somewhere/else", "reply_to": "/somewhere/else/r"}\n' > "$K/requests/cur/q1/letter.json"
AOS_LLM_KERNEL="$K" sc leave --dry-run > "$RUN/t5d.out" 2>&1; E=$?
check "a letter from another stack does not count ($E)" bash -c "[ $E = 0 ] && grep -q 'no letters from _stack waiting' $RUN/t5d.out"
sc leave --dry-run > "$RUN/t5e.out" 2>&1; E=$?
check "AOS_LLM_KERNEL not set: skipped with one line ($E)" bash -c "[ $E = 0 ] && grep -q 'AOS_LLM_KERNEL is not set: skipped' $RUN/t5e.out"

echo "== T6 secret-like text"
KEY="sk-$(printf 'A%.0s' $(seq 24))"
printf '{"role":"tool","content":"%s"}\n' "$KEY" >> "$A/history.jsonl"
sc leave --dry-run > "$RUN/t6.out" 2>&1; E=$?
check "refused SecretFound ($E), file:line named" bash -c "[ $E = 2 ] && grep -q SecretFound $RUN/t6.out && grep -q '_stack/procs/ann/history.jsonl:2: key-openai' $RUN/t6.out"
check "the secret text itself is not printed" bash -c "! grep -qF '$KEY' $RUN/t6.out"
sc leave --dry-run --secret-ok _stack/procs/ann/history.jsonl > "$RUN/t6b.out" 2>&1; E=$?
check "--secret-ok FILE lets it through ($E)" [ $E = 0 ]
printf '{"role":"user","content":"hi"}\n' > "$A/history.jsonl"

echo "== T7 dry run changes nothing"
B=$(head_)
sc leave --dry-run > "$RUN/t7.out" 2>&1; E=$?
check "DryRun ($E), main unchanged, no claims left" bash -c "[ $E = 0 ] && [ \"\$(code_of $RUN/t7.out)\" = DryRun ] && [ $(head_) = $B ] && ! python3 $(dirname "$TOOL")/commit_queue.py --repo $R --cache $C claims | grep -q _stack/"

echo "== T8 leave commits only what should travel"
sc leave > "$RUN/t8.out" 2>&1; E=$?
C8=$(head_)
check "Committed ($E), main moved one commit" bash -c "[ $E = 0 ] && [ \"\$(code_of $RUN/t8.out)\" = Committed ] && [ \$(git rev-list --count $B..main) = 1 ]"
miss=""; for f in $TRAVEL; do in_head "_stack/procs/ann/$f" || miss="$miss $f"; done
check "every travelling file is in the commit${miss:+ (missing:$miss)}" [ -z "$miss" ]
extra=""; for f in $STAY; do in_head "_stack/procs/ann/$f" && extra="$extra $f"; done
check "no lock, live.jsonl, socket, cooldown, .session_home, claude/… in the commit${extra:+ (has:$extra)}" [ -z "$extra" ]
if [ $REAL = 1 ]; then
  check "the daemon's own files travel (state.json, procs_state.json, clock), .sweeper.lock does not" bash -c "git cat-file -e main:_stack/procs_state.json && git cat-file -e main:_stack/clock && ! git cat-file -e main:_stack/.sweeper.lock 2>/dev/null"
fi
check "message names the machine, says not pushed" bash -c "git log -1 --format=%B main | grep -q \"from $(python3 -c 'import socket;print(socket.gethostname())') at\" && git log -1 --format=%B main | grep -q 'Not pushed'"
check "commit touches only _stack/ (index_gen generated nothing else)" bash -c "[ -z \"\$(git show --name-only --format= main | grep -v '^_stack/')\" ]"
check "shared index has them: git status -- _stack is clean" [ -z "$(git status --porcelain -- _stack)" ]
check "index_gen check passes with _stack tracked" python3 wf/tools/index_gen.py --root "$R" --quiet
check "not pushed: origin main unchanged" [ "$(git rev-parse origin/main)" = "$B" ]
check "output warns about stash / reset --hard / clean -fdx" grep -q 'git clean -fdx' "$RUN/t8.out"

echo "== T9 second leave without changes"
sc leave > "$RUN/t9.out" 2>&1; E=$?
check "NothingToCommit ($E), main unchanged" bash -c "[ $E = 0 ] && [ \"\$(code_of $RUN/t9.out)\" = NothingToCommit ] && [ $(head_) = $C8 ]"

echo "== T10 changed, removed and new files"
printf '{"role":"assistant","content":"ok"}\n' >> "$A/history.jsonl"
rm "$A/tools/subagent/subagents.json"
mkdir -p "$A/mailbox/new/l2"; echo '{"title":"two"}' > "$A/mailbox/new/l2/letter.json"
echo again > "$A/lock"
sc leave > "$RUN/t10.out" 2>&1; E=$?
check "Committed ($E): M history, D subagents.json, A l2, nothing else" bash -c "[ $E = 0 ] && [ \"\$(git show --name-status --format= main | sort | tr '\t' ' ')\" = \"\$(printf 'A _stack/procs/ann/mailbox/new/l2/letter.json\nD _stack/procs/ann/tools/subagent/subagents.json\nM _stack/procs/ann/history.jsonl\n')\" ]"
check "index_gen check still passes" python3 wf/tools/index_gen.py --root "$R" --quiet

echo "== T11 arrive: clean runtime files, keep the rest, check the shell"
sc arrive --dry-run > "$RUN/t11.out" 2>&1; E=$?
check "dry run lists, removes nothing ($E)" bash -c "[ $E = 0 ] && grep -q 'would remove' $RUN/t11.out && [ -f $A/lock ]"
sc arrive > "$RUN/t11b.out" 2>&1; E=$?
gone=""; for f in lock .flock endpoints.json cooldown.json think/request.json think/sent.json think/wait_warned.txt mailbox/tmp/half x.sock sender.flock hookeds/x/event.json procs_requests/reply/z/a .state.json.tmp; do [ -e "$A/$f" ] && gone="$gone $f"; done
check "Arrived ($E); runtime files removed${gone:+ (still there:$gone)}" bash -c "[ $E = 0 ] && [ \"\$(code_of $RUN/t11b.out)\" = Arrived ] && [ -z '$gone' ]"
kept=""; for f in .session_home claude/env.json claude/session.txt live.jsonl turns.jsonl stderr.txt transcripts/t.txt state.json.bad-1 counter_turns.txt; do [ -e "$A/$f" ] || kept="$kept $f"; done
check "kept .session_home, claude/, logs${kept:+ (removed:$kept)}" [ -z "$kept" ]
check "tracked files untouched: git status -- _stack clean" [ -z "$(git status --porcelain -- _stack)" ]
check "notes: AOS_DAEMON, AOS_LLM_KERNEL not set; no permission station" bash -c "grep -q 'AOS_DAEMON is not set' $RUN/t11b.out && grep -q 'AOS_LLM_KERNEL is not set' $RUN/t11b.out && grep -q 'no permission station' $RUN/t11b.out"
check "prints the start line, does not run it" bash -c "grep -qF 'env -u AOS_DAEMON -u AOS_STACK -u AOS_CLOCK aos-exec --stack _stack wf/tree/root' $RUN/t11b.out"
if [ $REAL = 1 ]; then
  check "a second daemon for the ping check" start_daemon "$RUN/k2" "$RUN/k2.log"
  AOS_DAEMON="$ST" AOS_LLM_KERNEL="$RUN/k2" AOS_KERNEL="$RUN/nostation/requests" sc arrive > "$RUN/t11c.out" 2>&1; E=$?
  check "AOS_DAEMON is _stack, llm kernel answers ping, dead station noted ($E)" bash -c "[ $E = 0 ] && grep -q \"this repo's _stack\" $RUN/t11c.out && grep -q 'AOS_LLM_KERNEL = $RUN/k2: replied' $RUN/t11c.out && grep -q 'KernelFailed' $RUN/t11c.out"
  check "second daemon shut down" stop_daemon "$RUN/k2"
fi
AOS_LLM_KERNEL="$RUN/nothing" AOS_STACK=/x sc arrive > "$RUN/t11d.out" 2>&1; E=$?
check "llm kernel not running and AOS_STACK set: noted, not stopped ($E)" bash -c "[ $E = 0 ] && grep -q 'does not answer' $RUN/t11d.out && grep -q 'AOS_STACK set' $RUN/t11d.out"
git config pull.rebase true; git config rebase.autoStash true
sc arrive > "$RUN/t11e.out" 2>&1
check "pull.rebase and rebase.autoStash noted" bash -c "grep -q 'pull.rebase is on' $RUN/t11e.out && grep -q 'rebase.autostash is true' $RUN/t11e.out"
git config --unset pull.rebase; git config --unset rebase.autoStash

echo "== T12 arrive stops when _stack differs from HEAD"
printf '{"role":"user","content":"ran here"}\n' >> "$A/history.jsonl"
sc arrive > "$RUN/t12.out" 2>&1; E=$?
check "changed tracked file → StackDirty ($E), removes nothing" bash -c "[ $E = 2 ] && grep -q StackDirty $RUN/t12.out && grep -q 'changed _stack/procs/ann/history.jsonl' $RUN/t12.out"
git checkout -q -- _stack/procs/ann/history.jsonl
mkdir -p "$A/mailbox/new/l3"; echo '{}' > "$A/mailbox/new/l3/letter.json"
sc arrive > "$RUN/t12b.out" 2>&1; E=$?
check "new travelling file → StackDirty ($E)" bash -c "[ $E = 2 ] && grep -q 'new _stack/procs/ann/mailbox/new/l3/letter.json' $RUN/t12b.out"
rm -r "$A/mailbox/new/l3"

echo "== T13 the other machine: git pull silently overwrites ignored files, arrive before pull catches it"
R2="$RUN/repo2"; git clone -q "$R" "$R2"
A2="$R2/_stack/procs/ann"
echo "B wrote this" > "$A2/mailbox/new/l1/extra.txt"
echo "A wrote this" > "$A/mailbox/new/l1/extra.txt"
sc leave > "$RUN/t13.out" 2>&1
check "machine A committed extra.txt" in_head _stack/procs/ann/mailbox/new/l1/extra.txt
python3 "$TOOL" arrive --repo "$R2" > "$RUN/t13b.out" 2>&1; E=$?
check "machine B: arrive before pull → StackDirty ($E)" bash -c "[ $E = 2 ] && grep -q 'new _stack/procs/ann/mailbox/new/l1/extra.txt' $RUN/t13b.out"
git -C "$R2" pull -q --no-rebase > "$RUN/t13c.out" 2>&1; E=$?
check "git pull did not refuse ($E) and overwrote B's ignored file with A's" bash -c "[ $E = 0 ] && [ \"\$(cat $A2/mailbox/new/l1/extra.txt)\" = 'A wrote this' ]"
mkdir -p "$R/proto8/py/aos"; echo "# t13" > "$R/proto8/py/aos/t13_probe.py"; git add proto8/py/aos/t13_probe.py; git commit -q -m t13-py -- proto8/py/aos/t13_probe.py
git -C "$R2" pull -q --no-rebase
python3 "$TOOL" arrive --repo "$R2" > "$RUN/t13d.out" 2>&1; E=$?
check "after a pull that touched proto8/py: install.py reminder ($E)" bash -c "[ $E = 0 ] && grep -q 'change 1 files under proto8/py or proto8/cpp' $RUN/t13d.out"

echo
echo "run folder: $RUN"
echo "PASS $PASS  FAIL $FAIL"
[ $FAIL = 0 ]
