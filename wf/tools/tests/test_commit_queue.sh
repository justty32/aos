#!/bin/bash
# test_commit_queue.sh — 在 repo 外的暫存 clone 上測 commit_queue.py（兩線同時、別人 staged、索引列合併、claim 擋下、生成器失敗、CAS、半途被殺、生成物、month_set、進度檔 progress.json 的兩個 op、單檔大小門檻與放行名單、--stack-commit 只讓 _stack/ 跳過 .gitignore 檢查）；不碰來源 repo
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
# pj open.<鍵>.<欄>｜keys｜fields.<鍵>：讀 main 上的 wf/progress.json
pj() { git show main:wf/progress.json | python3 -c '
import json, sys
d = json.load(sys.stdin)["open"]; q = sys.argv[1]
if q == "keys": print("\n".join(d))
elif q.startswith("fields."): print(" ".join(d[q[7:]]))
else:
    _, k, f = q.split(".", 2); v = d.get(k, {}).get(f, "")
    print(" ".join(v) if isinstance(v, list) else v)' "$1"; }
export -f pj

echo "== T1 two lines submit at the same time"
B0=$(head_)
printf '# t1a 測試檔\n' > "$DAYDIR/t1a.md"
printf '#!/usr/bin/env python3\n"""t1b — 測試檔一句話。"""\n' > wf/tools/t1b_test.py
cq submit --line ok-a --files "$DAYDIR/t1a.md" --msg-file "$(msg 't1a' m1a)" \
   --op "{\"op\":\"day_upsert\",\"date\":\"$DAY\",\"name\":\"t1a\",\"link\":\"t1a.md\",\"summary\":\"甲線\"}" > "$RUN/t1a.out" 2> "$RUN/t1a.err" & P1=$!
cq submit --line ok-b --files wf/tools/t1b_test.py --msg-file "$(msg 't1b' m1b)" \
   --op '{"op":"progress_upsert","key":"t1b","entry":{"title":"t1b","status":"open","what":"乙線"}}' > "$RUN/t1b.out" 2> "$RUN/t1b.err" & P2=$!
wait $P1; E1=$?; wait $P2; E2=$?
check "both exit 0 ($E1,$E2)" [ "$E1" = 0 -a "$E2" = 0 ]
check "main moved 2 commits" [ "$(git rev-list --count "$B0"..main)" = 2 ]
CA=$(python3 -c 'import json,sys;print(json.loads(open(sys.argv[1]).read().splitlines()[-1])["commit"])' "$RUN/t1a.out")
CB=$(python3 -c 'import json,sys;print(json.loads(open(sys.argv[1]).read().splitlines()[-1])["commit"])' "$RUN/t1b.out")
check "a's commit has a's file, not b's" bash -c "git show --name-only --format= $CA | grep -qx '$DAYDIR/t1a.md' && ! git show --name-only --format= $CA | grep -q t1b_test"
check "b's commit has b's file and wf/tools/_index.json" bash -c "git show --name-only --format= $CB | grep -qx wf/tools/t1b_test.py && git show --name-only --format= $CB | grep -qx wf/tools/_index.json"
check "HEAD day index has t1a row, progress.json has t1b entry" bash -c "git show main:$DAYDIR/README.md | grep -qF '| [t1a](t1a.md) | 甲線 |' && [ \"\$(pj open.t1b.what)\" = 乙線 ]"
check "new entry: last key, all fields, since is today" bash -c "[ \"\$(pj keys | tail -1)\" = t1b ] && [ \"\$(pj fields.t1b)\" = 'title status flow what next see since' ] && [ \"\$(pj open.t1b.since)\" = $DAY ]"
check "working tree clean for those paths" [ -z "$(git status --porcelain -- "$DAYDIR/t1a.md" wf/tools/t1b_test.py wf/tools/_index.json "$DAYDIR/README.md" wf/progress.json)" ]
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
 {"op":"progress_upsert","key":"t1b","entry":{"title":"t1b","status":"等使用者","what":"乙線改過","see":["[x](x.md)"],"since":"2000-01-01"}}]
EOF
CNT0=$(git show main:proto8/thinking/$YM/README.md | grep -F "| [$DAY]($DD/README.md) |" | awk -F'|' '{print $3+0}')
cq submit --line ok-c --files "$DAYDIR/t3.md" --msg-file "$(msg t3 m3)" --ops-file "$RUN/ops3.json" > "$RUN/t3.out" 2>&1; E=$?
check "exit 0" [ $E = 0 ]
check "HEAD has t1a and t3 rows, no hand row" bash -c "git show main:$DAYDIR/README.md | grep -qF '[t1a](t1a.md)' && git show main:$DAYDIR/README.md | grep -qF '| [t3](t3.md) | 丙線 |' && ! git show main:$DAYDIR/README.md | grep -qF hand.md"
check "shared index holds HEAD's day index (hand row not staged)" [ -z "$(git diff --cached --name-only -- "$DAYDIR/README.md")" ]
check "working tree day index has hand row and t3 row" bash -c "grep -qF hand.md $DAYDIR/README.md && grep -qF '[t3](t3.md)' $DAYDIR/README.md"
CNT1=$(git show main:proto8/thinking/$YM/README.md | grep -F "| [$DAY]($DD/README.md) |" | awk -F'|' '{print $3+0}')
check "month count +1 ($CNT0 -> $CNT1) and segment there" bash -c "[ $CNT1 = $((CNT0+1)) ] && git show main:proto8/thinking/$YM/README.md | grep -F '[$DAY]' | grep -qF '；丙線一段 |'"
check "progress entry replaced in place, only once" bash -c "[ \"\$(pj open.t1b.what)\" = 乙線改過 ] && [ \"\$(pj open.t1b.status)\" = 等使用者 ] && [ \"\$(pj open.t1b.since)\" = 2000-01-01 ] && [ \"\$(pj keys | grep -cx t1b)\" = 1 ] && [ \"\$(pj keys | tail -1)\" = t1b ]"
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

echo "== T11 month_set: set the day count, summary untouched, same value again is a no-op, bad count refused"
MROW0=$(git show main:proto8/thinking/$YM/README.md | grep -F "| [$DAY]($DD/README.md) |" | awk -F'|' '{print $4}')
cq submit --line ok-a --msg-file "$(msg t11 m11)" --op "{\"op\":\"month_set\",\"date\":\"$DAY\",\"count\":77}" > "$RUN/t11.out" 2>&1; E=$?
CNT=$(git show main:proto8/thinking/$YM/README.md | grep -F "| [$DAY]($DD/README.md) |" | awk -F'|' '{print $3+0}')
MROW1=$(git show main:proto8/thinking/$YM/README.md | grep -F "| [$DAY]($DD/README.md) |" | awk -F'|' '{print $4}')
check "month_set ok ($E), count is 77, one row for the day" bash -c "[ $E = 0 ] && [ $CNT = 77 ] && [ \$(git show main:proto8/thinking/$YM/README.md | grep -cF '| [$DAY]($DD/README.md) |') = 1 ]"
check "summary cell untouched" [ "$MROW0" = "$MROW1" ]
check "working tree month index clean" [ -z "$(git status --porcelain -- proto8/thinking/$YM/README.md)" ]
B=$(head_)
cq submit --line ok-a --msg-file "$(msg t11b m11b)" --op "{\"op\":\"month_set\",\"date\":\"$DAY\",\"count\":77}" > "$RUN/t11b.out" 2>&1; E=$?
check "same count again → nothing to commit (BLOCKED $E), main unchanged" bash -c "[ $E = 2 ] && [ $(head_) = $B ]"
cq submit --line ok-a --msg-file "$(msg t11c m11c)" --op "{\"op\":\"month_set\",\"date\":\"$DAY\",\"count\":\"7\"}" > "$RUN/t11c.out" 2>&1; E=$?
check "count as a string → refused ($E)" [ $E = 3 ]
cq submit --line ok-a --msg-file "$(msg t11d m11d)" --op "{\"op\":\"month_set\",\"date\":\"$DAY\",\"count\":-1}" > "$RUN/t11d.out" 2>&1; E=$?
check "negative count → refused ($E)" [ $E = 3 ]
cq submit --line ok-a --msg-file "$(msg t11e m11e)" --op "{\"op\":\"month_set\",\"date\":\"$YM-00\",\"count\":1}" > "$RUN/t11e.out" 2>&1; E=$?
check "no row for that day → BLOCKED ($E), main unchanged" bash -c "[ $E = 2 ] && [ $(head_) = $B ]"
cq submit --line ok-a --msg-file "$(msg t11f m11f)" --op "{\"op\":\"month_bump\",\"date\":\"$DAY\",\"segment\":\"丁線一段\"}" --op "{\"op\":\"month_set\",\"date\":\"$DAY\",\"count\":5}" > "$RUN/t11f.out" 2>&1; E=$?
CNT=$(git show main:proto8/thinking/$YM/README.md | grep -F "| [$DAY]($DD/README.md) |" | awk -F'|' '{print $3+0}')
check "bump then set in one request ($E): count is 5 and the new segment is there" bash -c "[ $E = 0 ] && [ $CNT = 5 ] && git show main:proto8/thinking/$YM/README.md | grep -F '[$DAY]' | grep -qF '；丁線一段 |'"

echo "== T12 knowledge _index.json is hand-written: accepted; other _index.json still refused"
KI=proto8/knowledge/aos/cli/_index.json
if [ -f "$KI" ]; then
  python3 -c "import json,sys;p=sys.argv[1];d=json.load(open(p,encoding='utf-8'));d['_t12']={'description':'t12 test entry'};open(p,'w',encoding='utf-8').write(json.dumps(d,ensure_ascii=False,indent=2)+'\n')" "$KI"
  cq submit --line ok-a --files "$KI" --msg-file "$(msg t12 m12)" > "$RUN/t12.out" 2>&1; E=$?
  check "knowledge _index.json submitted ($E) and in the commit" bash -c "[ $E = 0 ] && git show main:$KI | grep -q _t12"
  check "it is listed under files, not generated" python3 -c "import json,sys;d=json.loads(open(sys.argv[1]).read().strip().splitlines()[-1]);sys.exit(0 if sys.argv[2] in d['files'] and sys.argv[2] not in d['generated'] else 1)" "$RUN/t12.out" "$KI"
else
  bad "T12 needs $KI in the clone"
fi
OI=proto8/py/aos/apps/agent/_index.json
printf ' ' >> "$OI"
cq submit --line ok-a --files "$OI" --msg-file "$(msg t12b m12b)" > "$RUN/t12b.out" 2>&1; E=$?
check "proto8 code _index.json still refused as generated ($E)" bash -c "[ $E = 3 ] && grep -q 'generated file' $RUN/t12b.out"
git checkout -q -- "$OI"
cq submit --line ok-a --files wf/tools/_index.json --msg-file "$(msg t12c m12c)" > "$RUN/t12c.out" 2>&1; E=$?
check "wf _index.json still refused as generated ($E)" bash -c "[ $E = 3 ] && grep -q 'generated file' $RUN/t12c.out"

echo "== T13 progress.json: since kept on update, same entry again is a no-op, delete, refusals"
cq submit --line ok-a --msg-file "$(msg t13 m13)" --op '{"op":"progress_upsert","key":"t1b","entry":{"title":"t1b","status":"open","what":"乙線三改"}}' > "$RUN/t13.out" 2>&1; E=$?
check "update without since ($E): since kept, see cleared" bash -c "[ $E = 0 ] && [ \"\$(pj open.t1b.since)\" = 2000-01-01 ] && [ -z \"\$(pj open.t1b.see)\" ] && [ \"\$(pj open.t1b.what)\" = 乙線三改 ]"
check "file stays indent-2 JSON ending in a newline" bash -c "git show main:wf/progress.json | python3 -c 'import json,sys;t=sys.stdin.read();sys.exit(0 if t==json.dumps(json.loads(t),ensure_ascii=False,indent=2)+chr(10) else 1)'"
B=$(head_)
cq submit --line ok-a --msg-file "$(msg t13b m13b)" --op '{"op":"progress_upsert","key":"t1b","entry":{"title":"t1b","status":"open","what":"乙線三改","since":"2000-01-01"}}' > "$RUN/t13b.out" 2>&1; E=$?
check "same entry again → nothing to commit (BLOCKED $E), main unchanged" bash -c "[ $E = 2 ] && [ $(head_) = $B ]"
N0=$(pj keys | wc -l)
cq submit --line ok-a --msg-file "$(msg t13c m13c)" --op '{"op":"progress_delete","key":"t1b"}' > "$RUN/t13c.out" 2>&1; E=$?
check "delete ($E): key gone, one entry fewer" bash -c "[ $E = 0 ] && ! pj keys | grep -qx t1b && [ \$(pj keys | wc -l) = $((N0-1)) ]"
check "working tree progress.json clean" [ -z "$(git status --porcelain -- wf/progress.json)" ]
printf '# t13d\n' > "$DAYDIR/t13d.md"
cq submit --line ok-a --files "$DAYDIR/t13d.md" --msg-file "$(msg t13d m13d)" --op '{"op":"progress_delete","key":"t1b"}' > "$RUN/t13d.out" 2>&1; E=$?
check "delete a missing key → warning, rest committed ($E)" bash -c "[ $E = 0 ] && grep -q \"progress_delete: no key 't1b'\" $RUN/t13d.out"
B=$(head_)
cq submit --line ok-a --msg-file "$(msg t13e m13e)" --op '{"op":"progress_upsert","key":"T 1","entry":{"title":"x","status":"open","what":"x"}}' > "$RUN/t13e.out" 2>&1; E=$?
check "bad key → refused ($E)" [ $E = 3 ]
cq submit --line ok-a --msg-file "$(msg t13f m13f)" --op '{"op":"progress_upsert","key":"t13f","entry":{"title":"x","status":"done","what":"x"}}' > "$RUN/t13f.out" 2>&1; E=$?
check "bad status → refused ($E)" [ $E = 3 ]
cq submit --line ok-a --msg-file "$(msg t13g m13g)" --op '{"op":"progress_upsert","key":"t13g","entry":{"title":"x","status":"open"}}' > "$RUN/t13g.out" 2>&1; E=$?
check "missing what → refused ($E)" [ $E = 3 ]
cq submit --line ok-a --msg-file "$(msg t13h m13h)" --op '{"op":"progress_upsert","key":"t13h","entry":{"title":"x","status":"open","what":"x","owner":"me"}}' > "$RUN/t13h.out" 2>&1; E=$?
check "unknown field → refused ($E)" [ $E = 3 ]
cq submit --line ok-a --msg-file "$(msg t13i m13i)" --op '{"op":"log_upsert","key":"- **open｜x","text":"- **open｜x**：y"}' > "$RUN/t13i.out" 2>&1; E=$?
check "old log_upsert op → refused ($E)" [ $E = 3 ]
printf ' ' >> wf/progress.json
cq submit --line ok-a --files wf/progress.json --msg-file "$(msg t13j m13j)" > "$RUN/t13j.out" 2>&1; E=$?
check "progress.json in --files → refused ($E)" bash -c "[ $E = 3 ] && grep -q 'shared index file' $RUN/t13j.out"
git checkout -q -- wf/progress.json
check "main unchanged by the refusals" [ "$(head_)" = "$B" ]

echo "== T14 single-file size limit: over the limit refused, big_ok from main lets it in, a lower limit refuses, bad config falls back"
CFG=wf/tools/commit_queue.json
cfg() { printf '{\n "description": "t14 test config.",\n %s\n}\n' "$1" > "$CFG"; }
big() { { printf '# %s\n' "$1"; head -c "$2" /dev/zero | tr '\0' x; } > "$DAYDIR/$1.md"; }
LIM=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["max_file_bytes"])' "$CFG")
check "default config in main says 1 MB ($LIM)" [ "$LIM" = 1048576 ]
big t14big 1048576; printf '# t14 small\n' > "$DAYDIR/t14small.md"
B=$(head_)
cq submit --line ok-a --files "$DAYDIR/t14small.md" "$DAYDIR/t14big.md" --msg-file "$(msg t14a m14a)" > "$RUN/t14a.out" 2>&1; E=$?
check "over 1 MB → refused RequestBad ($E), names the file and its size" bash -c "[ $E = 3 ] && grep -q RequestBad $RUN/t14a.out && grep -qF '$DAYDIR/t14big.md is 1048585 bytes' $RUN/t14a.out"
check "whole request refused: main unchanged, small file not committed" bash -c "[ $(head_) = $B ] && ! git show --name-only --format= main | grep -q t14small"
check "hint says temp/ or big_ok" grep -q 'temp/.*big_ok' "$RUN/t14a.out"
check "the big file was not hashed into .git" bash -c "! git cat-file -e \$(git hash-object $DAYDIR/t14big.md) 2>/dev/null"
{ printf '# t14 edge\n'; head -c $((1048576 - 11)) /dev/zero | tr '\0' x; } > "$DAYDIR/t14edge.md"
cq submit --line ok-a --files "$DAYDIR/t14edge.md" --msg-file "$(msg t14b m14b)" > "$RUN/t14b.out" 2>&1; E=$?
check "exactly at the limit ($(stat -c %s "$DAYDIR/t14edge.md") bytes) passes ($E)" bash -c "[ $E = 0 ] && git show --name-only --format= main | grep -qx $DAYDIR/t14edge.md"
cfg "\"max_file_bytes\": 1048576, \"big_ok\": [\"$DAYDIR/t14b*.md\"]"
B=$(head_)
cq submit --line ok-a --files "$DAYDIR/t14big.md" --msg-file "$(msg t14c m14c)" > "$RUN/t14c.out" 2>&1; E=$?
check "big_ok only in the working tree does not count ($E), main unchanged" bash -c "[ $E = 3 ] && [ $(head_) = $B ]"
cq submit --line ok-a --files "$CFG" --msg-file "$(msg t14d m14d)" > "$RUN/t14d.out" 2>&1; E=$?
check "config with big_ok submitted ($E)" bash -c "[ $E = 0 ] && git show main:$CFG | grep -q t14b"
cq submit --line ok-a --files "$DAYDIR/t14big.md" --msg-file "$(msg t14e m14e)" > "$RUN/t14e.out" 2>&1; E=$?
check "big file listed in big_ok (glob) passes ($E)" bash -c "[ $E = 0 ] && git show --name-only --format= main | grep -qx $DAYDIR/t14big.md"
printf '# t14 two hundred bytes %0180d\n' 0 > "$DAYDIR/t14mid.md"; printf '# t14 tiny\n' > "$DAYDIR/t14tiny.md"
cq submit --line ok-a --files "$DAYDIR/t14mid.md" --msg-file "$(msg t14f m14f)" --dry-run > "$RUN/t14f.out" 2>&1; E=$?
check "a 200-byte file passes under the 1 MB limit (dry run $E)" [ $E = 0 ]
cfg '"max_file_bytes": 100, "big_ok": []'
cq submit --line ok-a --files "$CFG" --msg-file "$(msg t14g m14g)" > "$RUN/t14g.out" 2>&1; E=$?
check "config with a 100-byte limit submitted ($E)" bash -c "[ $E = 0 ] && git show main:$CFG | grep -q '\"max_file_bytes\": 100'"
B=$(head_)
cq submit --line ok-a --files "$DAYDIR/t14mid.md" --msg-file "$(msg t14h m14h)" > "$RUN/t14h.out" 2>&1; E=$?
check "lower limit: the 200-byte file that passed is now refused ($E), main unchanged" bash -c "[ $E = 3 ] && grep -q 'limit 100 bytes' $RUN/t14h.out && [ $(head_) = $B ]"
cq submit --line ok-a --files "$DAYDIR/t14tiny.md" --msg-file "$(msg t14i m14i)" > "$RUN/t14i.out" 2>&1; E=$?
check "a file under 100 bytes still passes ($E)" [ $E = 0 ]
ln -s t14big.md "$DAYDIR/t14link.md"
cq submit --line ok-a --files "$DAYDIR/t14link.md" --msg-file "$(msg t14j m14j)" --dry-run > "$RUN/t14j.out" 2>&1; E=$?
check "symlink counts its own size, not the target's ($E)" bash -c "[ $E = 0 ] && ! grep -q 'too big' $RUN/t14j.out"
mkdir -p _stack; big t14stack 200; mv "$DAYDIR/t14stack.md" _stack/t14stack.md
cq submit --line ok-a --files _stack/t14stack.md --msg-file "$(msg t14k m14k)" --dry-run > "$RUN/t14k.out" 2>&1
check "files under _stack/ are not size-checked" bash -c "! grep -q 'too big' $RUN/t14k.out"
cfg '"max_file_bytes": "big", "big_ok": "x"'
cq submit --line ok-a --files "$CFG" --msg-file "$(msg t14l m14l)" > "$RUN/t14l.out" 2>&1; E=$?
check "config with wrong types submitted ($E)" [ $E = 0 ]
cq submit --line ok-a --files "$DAYDIR/t14mid.md" --msg-file "$(msg t14m m14m)" > "$RUN/t14m.out" 2>&1; E=$?
check "wrong-type config → default 1 MB: the 200-byte file passes ($E), both keys warned about" bash -c "[ $E = 0 ] && grep -q 'max_file_bytes must be a positive integer' $RUN/t14m.out && grep -q 'big_ok must be a list' $RUN/t14m.out"
rm -f "$CFG" && git commit -q -m t14-no-config -- "$CFG"
printf '# t14 no config\n' > "$DAYDIR/t14nocfg.md"
cq submit --line ok-a --files "$DAYDIR/t14nocfg.md" --msg-file "$(msg t14n m14n)" > "$RUN/t14n.out" 2>&1; E=$?
check "config missing in main → default and a warning ($E)" bash -c "[ $E = 0 ] && grep -q 'not in main; using the default size limit 1048576' $RUN/t14n.out"
rm -rf _stack "$DAYDIR/t14link.md"

echo "== T15 --stack-commit: only _stack/ skips the .gitignore check (stack-commit's flag)"
mkdir -p _stack/p wf/temp; printf 't15\n' > _stack/p/t15.txt; printf 't15\n' > wf/temp/t15.txt
B=$(head_)
cq submit --line ok-a --files _stack/p/t15.txt --msg-file "$(msg t15a m15a)" > "$RUN/t15a.out" 2>&1; E=$?
check "without the flag a new _stack/ file is refused as ignored ($E), main unchanged" bash -c "[ $E = 3 ] && grep -q 'ignored by .gitignore' $RUN/t15a.out && [ $(head_) = $B ]"
cq submit --line ok-a --stack-commit --files _stack/p/t15.txt wf/temp/t15.txt --msg-file "$(msg t15b m15b)" > "$RUN/t15b.out" 2>&1; E=$?
check "with the flag an ignored file outside _stack/ is still refused ($E)" bash -c "[ $E = 3 ] && grep -q \"ignored by .gitignore: \['wf/temp/t15.txt'\]\" $RUN/t15b.out && [ $(head_) = $B ]"
cq submit --line ok-a --stack-commit --files _stack/p/t15.txt --msg-file "$(msg t15c m15c)" > "$RUN/t15c.out" 2>&1; E=$?
check "with the flag the _stack/ file is committed ($E), shared index has it" bash -c "[ $E = 0 ] && [ -z \"\$(git status --porcelain -- _stack/p/t15.txt)\" ]"
check "the commit holds _stack/p/t15.txt" in_commit main _stack/p/t15.txt
rm -f wf/temp/t15.txt

check "end: nothing staged except the foreign file" [ "$(git diff --cached --name-only)" = proto8/foreign_staged.md ]

echo
echo "run folder: $RUN"
echo "PASS $PASS  FAIL $FAIL"
[ $FAIL = 0 ]
