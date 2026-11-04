#!/usr/bin/env bash
set -eu
module=$(cd "$(dirname "$0")/../.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
node="$tmp/demo"
"$module/aos7-wfnode" init "$node"
"$module/aos7-wfnode" check "$node"
"$module/aos7-wfnode" state "$node" '寫完第一版，下一步跑測試'
"$module/aos7-wfnode" check "$node"
cat "$node/wf/handoffs/NEXT-SESSION.md"
