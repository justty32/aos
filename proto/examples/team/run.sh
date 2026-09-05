#!/bin/sh
# run-all 用的短版入口：沿用完整 team 劇本，但 25 秒內沒完成就失敗。
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
AOS_TEAM_MAX_SECONDS=25 AOS_TEAM_EVERY=1 sh "$HERE/../../play-team.sh"
test -f "$HERE/lead/state/done.json"
test -f "$HERE/lead/report.md"
