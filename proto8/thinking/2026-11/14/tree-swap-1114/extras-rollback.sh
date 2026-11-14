#!/bin/bash
# extras-rollback.sh - 退回 extras.sh 某一次跑的改動：照那次的 MANIFEST 倒著做。
# 用法：extras-rollback.sh <run 夾>（extras.sh 結束時印的 run=…）
# 原本有的檔：從備份抄回（寫旁邊再改名）；原本沒有的檔（備份路徑 -）：搬進這次退回的 run 夾（不刪）。搬走的連結搬回原處。
# 不含 kill；改 agents/、defs/ 的檔要樹停著。
[ -n "$BASH_VERSION" ] || { echo "extras-rollback.sh: not bash, refuse" >&2; exit 2; }
set -euo pipefail
TS_REPO=${TS_REPO:-$HOME/repo/aos}
. "$TS_REPO/proto8/extras/tree-swap/common.sh"
R=${1:?usage: extras-rollback.sh <run folder>}
[ -f "$R/MANIFEST" ] && [ -f "$R/META" ] || ts_red "$R has no MANIFEST/META"
ts_refuse_agent_env
TS_TREE=$(sed -n 's/^tree=//p' "$R/META")
ts_run_dir extras-rollback
trap ts_kept_report EXIT
echo "rollback of $R (tree=$TS_TREE)"
if grep -q "^$TS_TREE/" "$R/MANIFEST"; then ts_require_stopped; fi
tac "$R/MANIFEST" | while IFS=$'\t' read -r dst keep; do
  if [ "$keep" = - ]; then
    k="$TS_RUN/files$dst"; mkdir -p "$(dirname "$k")"; mv -T "$dst" "$k"; echo "$dst: did not exist before, moved to $k"
  elif [ -L "$keep" ] && [ ! -e "$dst" ] && [ ! -L "$dst" ]; then
    mv -T "$keep" "$dst"; echo "$dst: link moved back"
  else
    k="$TS_RUN/files$dst"; mkdir -p "$(dirname "$k")"; cp -a "$dst" "$k"
    cp -a "$keep" "$dst.extras-rb"; mv -f "$dst.extras-rb" "$dst"
    cmp -s "$keep" "$dst" || ts_red "$dst differs from $keep after rollback"
    echo "$dst: restored"
  fi
done
echo "extras rollback: done"
