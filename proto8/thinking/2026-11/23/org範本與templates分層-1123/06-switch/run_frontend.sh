#!/bin/bash
# run_frontend.sh - run proto8/frontend/tests through its own run.sh (it wants no AOS_* at all) inside a tree run_all.sh already installed.
# usage: run_frontend.sh OUTDIR     (OUTDIR as given to run_all.sh; log in OUTDIR/logs/frontend-run.log)
if [ -z "$BASH_VERSION" ]; then echo "run_frontend.sh: not bash" >&2; exit 1; fi
[ $# -eq 1 ] || { echo "run_frontend.sh: error: ArgumentsBad (usage: run_frontend.sh OUTDIR)" >&2; exit 1; }
OUT=$(realpath "$1")
for v in $(compgen -e | grep '^AOS_'); do unset "$v"; done
export PATH="$OUT/tree/proto8/bin:$PATH" VIEW_TEST_TMP="$OUT/tmp/view-fe"
mkdir -p "$VIEW_TEST_TMP"
timeout 2400 bash "$OUT/tree/proto8/frontend/tests/run.sh" > "$OUT/logs/frontend-run.log" 2>&1
rc=$?
grep -HE '^(FAIL|ERROR): ' "$OUT/logs/frontend-run.log" | sed -E 's#^.*/logs/([^:]*)\.log:(FAIL|ERROR): #\1\t\2\t#' > "$OUT/fails-frontend.tsv"
echo "run_frontend.sh: exit $rc, $(grep -E '^Ran ' "$OUT/logs/frontend-run.log" | tail -1), $(wc -l < "$OUT/fails-frontend.tsv") failing"
