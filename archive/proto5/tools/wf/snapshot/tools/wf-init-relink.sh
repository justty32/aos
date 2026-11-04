#!/usr/bin/env bash
# wf-init-relink.sh — 非侵入式佈局的連結改寫；由 wf-init.sh source，不單獨執行。
# 用到呼叫端已設好的 $target／$wfdir 與 say()。

normalize() { # 純 bash 路徑正規化（目標可能不存在，不能用 realpath）
  local IFS=/ part; local -a out=()
  for part in $1; do
    case "$part" in ''|.) ;; ..) [[ ${#out[@]} -gt 0 ]] && unset 'out[${#out[@]}-1]' ;; *) out+=("$part") ;; esac
  done
  printf '/%s' "${out[@]}"
}
relpath() { # $1 = from dir (abs), $2 = to path (abs)
  local from=${1%/} to=$2 up=""
  while [[ $from != "" && ${to#$from/} == "$to" ]]; do from=${from%/*}; up="../$up"; done
  printf '%s%s' "$up" "${to#$from/}"
}

rewrite_moved_links() { # 把因為搬進 <wfdir>/ 而斷掉的相對連結指回去
  local f d l path anchor abs rel cand new esc_old esc_new fixed
  # AGENTS.md 開場那行 grep 的路徑（code span，不是連結）
  sed -i.bak "s#grep -c '\^- \\\\\[' SESSION-LOG.md WAIT_USER.md#grep -c '^- \\\\[' $wfdir/SESSION-LOG.md $wfdir/WAIT_USER.md#" "$target/AGENTS.md" && rm -f "$target/AGENTS.md.bak"
  fixed=0
  while IFS= read -r f; do
    d=$(dirname "$f")
    while IFS= read -r l; do
      [[ -z $l ]] && continue
      case $l in http://*|https://*|mailto:*|'#'*) continue ;; esac
      path=${l%%#*}; anchor=${l#"$path"}
      [[ -z $path || -e "$d/$path" ]] && continue
      abs=$(normalize "$d/$path")
      rel=${abs#$target/}
      cand=""
      if [[ $rel == "$wfdir/"* && -e "$target/${rel#$wfdir/}" ]]; then cand="$target/${rel#$wfdir/}"
      elif [[ -e "$target/$wfdir/$rel" ]]; then cand="$target/$wfdir/$rel"
      fi
      [[ -z $cand ]] && continue
      new=$(relpath "$d" "$cand")$anchor
      esc_old=$(printf '%s' "$l" | sed 's/[][\.*^$|/]/\\&/g')
      esc_new=$(printf '%s' "$new" | sed 's/[&|/]/\\&/g')
      sed -i.bak "s|]($esc_old)|]($esc_new)|g" "$f" && rm -f "$f.bak"
      fixed=$((fixed + 1))
    done < <(grep -oE '\]\([^)]+\)' "$f" | sed -E 's/^\]\(//; s/\)$//' | sort -u)
  done < <(find "$target" -name '*.md' -not -path '*/.git/*')
  say "non-invasive: rewrote $fixed link(s) for $wfdir/ layout"
}
