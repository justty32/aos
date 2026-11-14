#!/bin/bash
# test_commit_queue.sh — 在 repo 外的暫存 clone 上測 commit_queue.py（兩線同時、別人 staged、索引列合併、claim 擋下、生成器失敗、CAS、半途被殺、生成物）；不碰來源 repo
# 用法：test_commit_queue.sh <來源 repo> <repo 外的暫存夾>   每次在暫存夾下開一個新的 run-<時間> 子夾，不刪任何東西
set -u
[ -n "${BASH_VERSION:-}" ] || { echo "not bash" >&2; exit 1; }
SRC=$(readlink -f "${1:?source repo}")
WORK=$(readlink -f "${2:?work folder outside the repo}")
case "$WORK/" in "$SRC"/*) echo "work folder must be outside the repo" >&2; exit 1;; esac
TOOL=$(dirname "$(readlink -f "$0")")/../commit_queue.py
RUN="$WORK/run-$(date +%Y%m%d-%H%M%S)-$$"
R="$RUN/repo"; C="$RUN/cache"
mkdir -p "$RUN" || exit 1
git clone -q "$SRC" "$R" || exit 1
cd "$R" || exit 1
# CQ_OVERLAY="路徑 …"：把來源工作樹裡還沒 commit 的這些檔抄進 clone、先 commit 一次（測還沒進 main 的改動）
if [ -n "${CQ_OVERLAY:-}" ]; then
  for f in $CQ_OVERLAY; do mkdir -p "$(dirname "$f")"; cp -p "$SRC/$f" "$f"; git add -- "$f"; done
  git commit -q -m "test overlay" || exit 1
fi
DAY=$(date +%Y-%m-%d); DD=${DAY:8:2}; YM=${DAY:0:7}
DAYDIR="proto8/thinking/$YM/$DD"
if [ ! -f "$DAYDIR/README.md" ]; then echo "SKIP: $DAYDIR/README.md not in the clone" >&2; exit 1; fi
cq() { python3 "$TOOL" --repo "$R" --cache "$C" --wait 60 "$@"; }
PASS=0; FAIL=0
ok()  { PASS=$((PASS+1)); echo "  ok   $*"; }
bad() { FAIL=$((FAIL+1)); echo "  FAIL $*"; }
check() { local d="$1"; shift; if "$@"; then ok "$d"; else bad "$d"; fi; }
msg() { printf '%s\n\nCo-Authored-By: test <t@example.invalid>\n' "$1" > "$RUN/$2"; echo "$RUN/$2"; }
head_() { git rev-parse main; }
in_commit() { git show --name-only --format= "$1" | grep -qxF "$2"; }

echo "== T1 two lines submit at the same time"
B0=$(head_)
printf '# t1a 測試檔\n' > "$DAYDIR/t1a.md"
printf '#!/usr/bin/env python3\n"""t1b — 測試檔一句話。"""\n' > wf/tools/t1b_test.py
cq submit --line ok-a --files "$DAYDIR/t1a.md" --msg-file "$(msg 't1a' m1a)" \
   --op "{\"op\":\"day_upsert\",\"date\":\"$DAY\",\"name\":\"t1a\",\"link\":\"t1a.md\",\"summary\":\"甲線\"}" > "$RUN/t1a.out" 2> "$RUN/t1a.err" & P1=$!
cq submit --line ok-b --files wf/tools/t1b_test.py --msg-file "$(msg 't1b' m1b)" \
   --op "{\"op\":\"log_upsert\",\"key\":\"- **open｜t1b\",\"text\":\"- **open｜t1b**：乙線\"}" > "$RUN/t1b.out" 2> "$RUN/t1b.err" & P2=$!
wait $P1; E1=$?; wait $P2; E2=$?
check "both exit 0 ($E1,$E2)" [ "$E1" = 0 -a "$E2" = 0 ]
check "main moved 2 commits" [ "$(git rev-list --count "$B0"..main)" = 2 ]
CA=$(python3 -c 'import json,sys;print(json.loads(open(sys.argv[1]).read().splitlines()[-1])["commit"])' "$RUN/t1a.out")
CB=$(python3 -c 'import json,sys;print(json.loads(open(sys.argv[1]).read().splitlines()[-1])["commit"])' "$RUN/t1b.out")
check "a's commit has a's file, not b's" bash -c "git show --name-only --format= $CA | grep -qx '$DAYDIR/t1a.md' && ! git show --name-only --format= $CA | grep -q t1b_test"
check "b's commit has b's file and wf/tools/_index.json" bash -c "git show --name-only --format= $CB | grep -qx wf/tools/t1b_test.py && git show --name-only --format= $CB | grep -qx wf/tools/_index.json"
check "HEAD day index has t1a row, SESSION-LOG has t1b line" bash -c "git show main:$DAYDIR/README.md | grep -qF '| [t1a](t1a.md) | 甲線 |' && git show main:wf/SESSION-LOG.md | grep -qF -- '- **open｜t1b**：乙線'"
check "working tree clean for those paths" [ -z "$(git status --porcelain -- "$DAYDIR/t1a.md" wf/tools/t1b_test.py wf/tools/_index.json "$DAYDIR/README.md" wf/SESSION-LOG.md)" ]
check "message kept as written (trailer)" bash -c "git log -1 --format=%B $CA | grep -qx 'Co-Authored-By: test <t@example.invalid>'"

echo "== T2 someone else's staged file stays out"
printf '# foreign\n' > proto8/foreign_staged.md; git add proto8/foreign_staged.md
printf '# t2 檔\n' > "$DAYDIR/t2.md"
cq submit --line ok-a --files "$DAYDIR/t2.md" --msg-file "$(msg t2 m2)" > "$RUN/t2.out" 2>&1; E=$?
check "exit 0" [ $E = 0 ]
check "commit has no foreign file" bash -c "! git show --name-only --format= main | grep -q foreign_staged"
check "foreign file still staged" bash -c "git diff --cached --name-only | grep -qx proto8/foreign_staged.md"
check "t2 not left as staged/modified" [ -z "$(git status --porcelain -- "$DAYDIR/t2.md")" ]

echo "== T3 index rows merge; a hand-added row in the working tree survives"
printf '| [hand](hand.md) | 手加沒交 |\n' >> "$DAYDIR/README.md"
printf '# t3 檔\n' > "$DAYDIR/t3.md"
cat > "$RUN/ops3.json" <<EOF
[{"op":"day_upsert","date":"$DAY","name":"t3","link":"t3.md","summary":"丙線"},
 {"op":"month_bump","date":"$DAY","segment":"丙線一段"},
 {"op":"log_upsert","key":"- **open｜t1b","text":"- **open｜t1b**：乙線改過"}]
EOF
CNT0=$(git show main:proto8/thinking/$YM/README.md | grep -F "| [$DAY]($DD/README.md) |" | awk -F'|' '{print $3+0}')
cq submit --line ok-c --files "$DAYDIR/t3.md" --msg-file "$(msg t3 m3)" --ops-file "$RUN/ops3.json" > "$RUN/t3.out" 2>&1; E=$?
check "exit 0" [ $E = 0 ]
check "HEAD has t1a and t3 rows, no hand row" bash -c "git show main:$DAYDIR/README.md | grep -qF '[t1a](t1a.md)' && git show main:$DAYDIR/README.md | grep -qF '| [t3](t3.md) | 丙線 |' && ! git show main:$DAYDIR/README.md | grep -qF hand.md"
check "shared index holds HEAD's day index (hand row not staged)" [ -z "$(git diff --cached --name-only -- "$DAYDIR/README.md")" ]
check "working tree day index has hand row and t3 row" bash -c "grep -qF hand.md $DAYDIR/README.md && grep -qF '[t3](t3.md)' $DAYDIR/README.md"
CNT1=$(git show main:proto8/thinking/$YM/README.md | grep -F "| [$DAY]($DD/README.md) |" | awk -F'|' '{print $3+0}')
check "month count +1 ($CNT0 -> $CNT1) and segment there" bash -c "[ $CNT1 = $((CNT0+1)) ] && git show main:proto8/thinking/$YM/README.md | grep -F '[$DAY]' | grep -qF '；丙線一段 |'"
check "SESSION-LOG line replaced, only once" [ "$(git show main:wf/SESSION-LOG.md | grep -c -- '- \*\*open｜t1b')" = 1 ]
cq submit --line ok-c --files "$DAYDIR/t3.md" --msg-file "$(msg t3b m3b)" --op "{\"op\":\"month_bump\",\"date\":\"$DAY\",\"segment\":\"丙線一段\"}" > "$RUN/t3b.out" 2>&1; E=$?
check "same month segment again → nothing to commit (BLOCKED $E)" [ $E = 2 ]

echo "== T4 conflict: claimed by another line is blocked"
printf '# t4 檔\n' > "$DAYDIR/t4.md"
cq claim --line ok-a "$DAYDIR/t4.md" > /dev/null 2>&1
cq claim --line ok-b "$DAYDIR/t4.md" > "$RUN/t4c.out" 2>&1; E=$?
check "second claim blocked ($E)" [ $E = 2 ]
B=$(head_)
cq submit --line ok-b --files "$DAYDIR/t4.md" --msg-file "$(msg t4 m4)" > "$RUN/t4.out" 2>&1; E=$?
check "submit blocked exit 2 ($E)" [ $E = 2 ]
check "reply names the holder" grep -q '"holder"' "$RUN/t4.out"
check "main did not move" [ "$(head_)" = "$B" ]
cq submit --line ok-a --files "$DAYDIR/t4.md" --msg-file "$(msg t4a m4a)" > "$RUN/t4a.out" 2>&1; E=$?
check "holder can submit ($E) and claim released" bash -c "[ $E = 0 ] && ! python3 $TOOL --repo $R --cache $C claims | grep -q t4.md"

echo "== T5 generator failure (new file without a one-line header)"
printf '\n\nno header\n' > wf/tools/t5_noheader.py
B=$(head_)
cq submit --line ok-a --files wf/tools/t5_noheader.py --msg-file "$(msg t5 m5)" > "$RUN/t5.out" 2>&1; E=$?
check "exit 4 ($E)" [ $E = 4 ]
check "error text from index_gen" grep -q DescMissing "$RUN/t5.out"
check "main did not move, wf/tools/_index.json untouched" bash -c "[ $(head_) = $B ] && [ -z \"\$(git status --porcelain -- wf/tools/_index.json)\" ]"

echo "== T6 someone commits by hand while the queue works (CAS)"
printf '# t6 hand\n' > "$DAYDIR/t6hand.md"; printf '# t6 queue\n' > "$DAYDIR/t6q.md"
B=$(head_)
CQ_TEST_RUN_AT=before_update_ref CQ_TEST_CMD="[ -e $RUN/t6.done ] || { git -C $R commit -q -m t6hand -- $DAYDIR/t6hand.md 2>/dev/null || { git -C $R add $DAYDIR/t6hand.md && git -C $R commit -q -m t6hand -- $DAYDIR/t6hand.md; }; touch $RUN/t6.done; }" \
  cq submit --line ok-a --files "$DAYDIR/t6q.md" --msg-file "$(msg t6 m6)" > "$RUN/t6.out" 2>&1; E=$?
check "exit 0 ($E)" [ $E = 0 ]
check "both commits on main" bash -c "[ $(git rev-list --count $B..main) = 2 ] && git log --format=%s $B..main | grep -qx t6hand"
check "warned about main moving" grep -q "main moved" "$RUN/t6.out"

echo "== T7 killed right after update-ref; doctor --repair finishes it"
printf '#!/usr/bin/env python3\n"""t7 — 測試檔一句話。"""\n' > wf/tools/t7_test.py
CQ_TEST_DIE_AT=after_update_ref cq submit --line ok-a --files wf/tools/t7_test.py --msg-file "$(msg t7 m7)" > "$RUN/t7.out" 2>&1; E=$?
check "died (exit $E)" [ $E = 9 ]
check "main has t7" bash -c "git show --name-only --format= main | grep -qx wf/tools/t7_test.py"
check "before repair: worktree _index.json differs from HEAD" [ -n "$(git status --porcelain -- wf/tools/_index.json)" ]
cq doctor --repair > "$RUN/t7r.out" 2>&1
check "after repair: t7 and _index.json clean" [ -z "$(git status --porcelain -- wf/tools/t7_test.py wf/tools/_index.json)" ]
check "journal gone" [ ! -e "$C/journal.json" ]

echo "== T8 generated files reflect only this commit"
printf '#!/usr/bin/env python3\n"""t8other — 別條線還沒交的檔。"""\n' > wf/tools/t8_other.py
printf '#!/usr/bin/env python3\n"""t8 — 這次要交的檔。"""\n' > wf/tools/t8_mine.py
cq submit --line ok-a --files wf/tools/t8_mine.py --msg-file "$(msg t8 m8)" > "$RUN/t8.out" 2>&1; E=$?
check "exit 0 ($E)" [ $E = 0 ]
check "HEAD wf/tools/_index.json has t8_mine, not t8_other" bash -c "git show main:wf/tools/_index.json | grep -q t8_mine.py && ! git show main:wf/tools/_index.json | grep -q t8_other"
check "warns 'not claimed'" grep -q "not claimed" "$RUN/t8.out"

echo "== T9 dry run and refusals"
printf '# t9\n' > "$DAYDIR/t9.md"; B=$(head_)
cq submit --line ok-a --files "$DAYDIR/t9.md" --msg-file "$(msg t9 m9)" --dry-run > "$RUN/t9.out" 2>&1; E=$?
check "dry run exit 0, main unchanged" bash -c "[ $E = 0 ] && [ $(head_) = $B ]"
cq submit --line ok-a --files "$DAYDIR/t4.md" --msg-file "$(msg t9b m9b)" > "$RUN/t9b.out" 2>&1; E=$?
check "unchanged file → BLOCKED ($E)" [ $E = 2 ]
cq submit --line ok-a --files "$DAYDIR/README.md" --msg-file "$(msg t9c m9c)" > "$RUN/t9c.out" 2>&1; E=$?
check "shared index file in --files → refused ($E)" [ $E = 3 ]
cq submit --line ok-a --files wf/tools/_index.json --msg-file "$(msg t9d m9d)" > "$RUN/t9d.out" 2>&1; E=$?
check "generated file in --files → refused ($E)" [ $E = 3 ]
check "foreign staged file still staged at the end" bash -c "git diff --cached --name-only | grep -qx proto8/foreign_staged.md"

echo "== T10 Argon fixes: rename a day row, a new day, idempotent resubmit, mode-only change, changed while waiting"
B=$(head_)
cq submit --line ok-a --msg-file "$(msg t10 m10)" --op "{\"op\":\"day_upsert\",\"date\":\"$DAY\",\"name\":\"t3-改名\",\"link\":\"t3.md\",\"summary\":\"丙線改名\"}" > "$RUN/t10.out" 2>&1; E=$?
check "ops-only submit ok ($E), row renamed not duplicated" bash -c "[ $E = 0 ] && [ \$(git show main:$DAYDIR/README.md | grep -c '](t3.md)') = 1 ] && git show main:$DAYDIR/README.md | grep -qF '[t3-改名](t3.md)'"
NEXT="2099-12-31"
printf '# t10 新的一天\n' > "$DAYDIR/t10.md"
cq submit --line ok-a --files "$DAYDIR/t10.md" --msg-file "$(msg t10b m10b)" --op "{\"op\":\"day_upsert\",\"date\":\"$NEXT\",\"name\":\"x\",\"link\":\"x.md\",\"summary\":\"新一天\"}" > "$RUN/t10b.out" 2>&1; E=$?
check "new day index created from template ($E)" bash -c "[ $E = 0 ] && git show main:proto8/thinking/2099-12/31/README.md | head -1 | grep -qF '2099-12-31' && git show main:proto8/thinking/2099-12/31/README.md | grep -qF '| [x](x.md) | 新一天 |'"
cq submit --line ok-a --files "$DAYDIR/t10.md" --msg-file "$RUN/m10b" > "$RUN/t10c.out" 2>&1; E=$?
check "same request again → DONE AlreadyCommitted ($E)" bash -c "[ $E = 0 ] && grep -q AlreadyCommitted $RUN/t10c.out"
chmod +x "$DAYDIR/t10.md"
cq submit --line ok-a --files "$DAYDIR/t10.md" --msg-file "$(msg t10d m10d)" > "$RUN/t10d.out" 2>&1; E=$?
check "mode-only change is committed ($E)" bash -c "[ $E = 0 ] && git ls-tree main -- $DAYDIR/t10.md | grep -q ^100755"
printf '# t10e\n' > "$DAYDIR/t10e.md"
flock "$C/lock" -c "sleep 2" & PL=$!
sleep 0.5
cq submit --line ok-a --files "$DAYDIR/t10e.md" --msg-file "$(msg t10e m10e)" > "$RUN/t10e.out" 2>&1 & PS=$!
sleep 0.5; printf '# t10e 又改了\n' > "$DAYDIR/t10e.md"
wait $PS; E=$?; wait $PL
check "edited while waiting → BLOCKED ($E)" bash -c "[ $E = 2 ] && grep -q ChangedWhileWaiting $RUN/t10e.out"

check "end: nothing staged except the foreign file" [ "$(git diff --cached --name-only)" = proto8/foreign_staged.md ]

echo
echo "run folder: $RUN"
echo "PASS $PASS  FAIL $FAIL"
[ $FAIL = 0 ]
