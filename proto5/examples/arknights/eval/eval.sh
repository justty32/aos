#!/usr/bin/env bash
# 一鍵評分：機械檢查＋證據檢查＋評審（claude-opus-5）＋量測。
# 用法：eval.sh <副本路徑> <批號…> [--team 團隊紀錄夾] [--hops 檔] [--no-judge] [--cand-root 目錄] [--label 名]
# 例：  eval.sh ~/tmp/arknights-try 100 143 --team ~/tmp/arknights-try/aos-team --label strong-r1
# 出：  results/<時間>[-label].json 與 .md（每人一列＋評審分最低 3 個）
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ $# -lt 2 ]; then
  sed -n '2,5p' "${BASH_SOURCE[0]}" | sed 's/^# //'
  exit 2
fi
command -v opencc >/dev/null || { echo "需要 opencc（pacman -S opencc）" >&2; exit 2; }
exec python3 "$here/eval_run.py" "$@"
