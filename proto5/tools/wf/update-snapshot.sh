#!/usr/bin/env bash
# update-snapshot.sh — 從 workflows repo 的某個 commit 重做 snapshot/（給人用；模型的工具只讀快照）。
#   tools/wf/update-snapshot.sh <commit> [workflows repo，預設 ~/repo/workflows]
# 一律從 commit 取（git archive），不抄工作樹；去掉 tools/test_* 與 __pycache__；寫 SNAPSHOT.json。
set -eu
commit=${1:?usage: update-snapshot.sh <commit> [repo]}
repo=${2:-$HOME/repo/workflows}
here=$(cd "$(dirname "$0")" && pwd)
full=$(git -C "$repo" rev-parse --verify "$commit^{commit}")
tmp=$(mktemp -d "$here/.snapshot-new.XXXXXX")
chmod 755 "$tmp"
trap 'rm -rf "$tmp"' EXIT
git -C "$repo" archive "$full" -- tools template flavors docs IMPORT.md README.md CHANGELOG.md skills/README.md \
  | tar -x -C "$tmp"
rm -f "$tmp"/tools/test_*
find "$tmp" -name __pycache__ -prune -exec rm -rf {} +
kernel=$(grep -o 'wf-kernel v[0-9.]*' "$tmp/template/AGENTS.md" | tail -1 | sed 's/wf-kernel //')
count=$(find "$tmp" -type f | wc -l | tr -d ' ')
printf '{\n  "repo": "%s",\n  "commit": "%s",\n  "kernel": "%s",\n  "made": "%s",\n  "files": %s,\n  "contents": ["tools (no tests)", "template", "flavors", "docs", "IMPORT.md", "README.md", "CHANGELOG.md", "skills/README.md"]\n}\n' \
  "${repo/#$HOME/\~}" "$full" "$kernel" "$(date +%F)" "$count" > "$tmp/SNAPSHOT.json"
rm -rf "$here/snapshot.old"
[[ -d "$here/snapshot" ]] && mv "$here/snapshot" "$here/snapshot.old"
mv "$tmp" "$here/snapshot"
trap - EXIT
rm -rf "$here/snapshot.old"
echo "snapshot -> $full (kernel $kernel, $count files)"
