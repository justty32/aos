#!/bin/bash
# run_all.sh - copy one commit of a repo with git archive, install it there with every AOS_* unset, run every test folder one by one, write a summary.
# usage: run_all.sh REPO COMMIT OUTDIR      (OUTDIR gets the tree in OUTDIR/tree, logs in OUTDIR/logs, summary in OUTDIR/summary.tsv)
if [ -z "$BASH_VERSION" ]; then echo "run_all.sh: not bash" >&2; exit 1; fi
[ $# -eq 3 ] || { echo "run_all.sh: error: ArgumentsBad (usage: run_all.sh REPO COMMIT OUTDIR)" >&2; exit 1; }
REPO=$1; COMMIT=$2; OUT=$(realpath -m "$3")
for v in $(compgen -e | grep '^AOS_'); do unset "$v"; done
if compgen -e | grep -q '^AOS_'; then echo "run_all.sh: AOS_* still set" >&2; exit 1; fi
export PYTHONDONTWRITEBYTECODE=1
[ -e "$OUT/tree" ] && { echo "run_all.sh: error: PathExists $OUT/tree" >&2; exit 1; }
mkdir -p "$OUT/tree" "$OUT/logs" "$OUT/tmp" || exit 1
git -C "$REPO" archive "$COMMIT" | tar -x -C "$OUT/tree" || exit 1
cd "$OUT/tree/proto8" || exit 1
python3 install.py -j 8 > "$OUT/logs/install.log" 2>&1 || { echo "run_all.sh: error: InstallFailed see $OUT/logs/install.log" >&2; exit 1; }
export AOS_HOME=$PWD
source "$AOS_HOME/env.sh" >> "$OUT/logs/install.log" 2>&1
export VIEW_TEST_TMP="$OUT/tmp/view"
mkdir -p "$VIEW_TEST_TMP"
: > "$OUT/summary.tsv"
cd "$OUT/tree" || exit 1
mapfile -t DIRS < <(find proto8 wf/tools -name 'test_*.py' -not -path '*/thinking/*' -not -path 'proto8/lib/*' \
    -not -path '*/archive/*' -not -path '*/node_modules/*' -printf '%h\n' | sort -u)
for d in "${DIRS[@]}"; do
    mods=$(cd "$d" && ls test_*.py | sed 's/\.py$//' | tr '\n' ' ')
    log="$OUT/logs/$(echo "$d" | tr '/' '_').log"
    start=$(date +%s)
    (cd "$d" && timeout 2400 python3 -m unittest $mods) > "$log" 2>&1
    rc=$?
    ran=$(grep -E '^Ran [0-9]+ test' "$log" | tail -1 | awk '{print $2}')
    res=$(tail -3 "$log" | grep -E '^(OK|FAILED)' | tail -1)
    printf '%s\t%s\t%s\t%s\t%ss\n' "$d" "$rc" "${ran:-?}" "${res:-?}" "$(( $(date +%s) - start ))" >> "$OUT/summary.tsv"
done
for c in proto8/templates/tests/image-move-check/check.py proto8/templates/kernel/tests/kernel-chain-check/check.py \
         proto8/templates/kernels/tests/kernel-chain-check/check.py; do
    [ -f "$c" ] || continue
    log="$OUT/logs/$(echo "$c" | tr '/' '_').log"
    timeout 1200 python3 "$c" > "$log" 2>&1
    printf '%s\t%s\t-\t-\t-\n' "$c" "$?" >> "$OUT/summary.tsv"
done
# failing test ids, one per line: dir<TAB>FAIL|ERROR<TAB>test id
grep -HE '^(FAIL|ERROR): ' "$OUT"/logs/*.log | sed -E 's#^.*/logs/([^:]*)\.log:(FAIL|ERROR): #\1\t\2\t#' > "$OUT/fails.tsv"
echo "run_all.sh: done $(wc -l < "$OUT/summary.tsv") folders, $(wc -l < "$OUT/fails.tsv") failing tests"
