#!/bin/sh
set -eu
P=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
R=$(mktemp -d)
trap 'rm -rf "$R"' EXIT HUP INT TERM
export AOS_MAIL_ROOT="$R"
M="$P/modules/mail/aos7-mail"
"$M" send alice bob REQUEST '請 bob 檢查範例'
test -f "$R/bob/inbox/"*.md
"$M" read bob | tee "$R/bob-read"
grep -q '請 bob 檢查範例' "$R/bob-read"
"$M" done bob 1 DONE 'bob 已完成範例檢查'
test -f "$R/alice/inbox/"*.md
"$M" read alice | tee "$R/alice-read"
grep -q 'bob 已完成範例檢查' "$R/alice-read"
"$M" done alice 1
"$M" audit
printf 'OK\n'
