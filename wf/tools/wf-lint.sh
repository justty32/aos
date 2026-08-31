#!/usr/bin/env bash
# wf-lint.sh — 工作流文檔的機械檢查（bash + grep/sed/awk/find，部分借 python3）
#   wf-lint.sh [--strict] [--quiet] <dir>...   檢查一個（導入後的）專案目錄
#   wf-lint.sh --self                          在模板 repo 內：template/ + examples/ + 各 flavor 合併模擬
#
# 檢查：① 相對連結 ② workflows/ 單檔 >8192 bytes ③ 模板標記殘留 ④ inbox/ 未辦信
#       ⑤ BIGLIST（>1 KB 條列；導航表印 BIGLIST-LINKS）⑥ 資料檔連結（tabledb.py check）
#       ⑦ QUERYCMD（md 殘留查詢指令）⑧ BROKEN-ANCHOR（#錨點不存在，計入 broken）
# 結束碼：BROKEN > 0 → 1；--strict 時 residue / oversize / biglist / querycmd > 0 也 → 1。
set -u

strict=0 self=0 quiet=0
dirs=()
for a in "$@"; do
  case "$a" in
    --strict) strict=1 ;;
    --self) self=1 ;;
    --quiet|-q) quiet=1 ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    *) dirs+=("$a") ;;
  esac
done

tools=$(cd "$(dirname "$0")" && pwd)
have_py=1
command -v python3 >/dev/null 2>&1 || { have_py=0; echo "WARN python3 not found; BIGLIST/data-file checks skipped"; }

total_broken=0 total_residue=0 total_oversize=0 total_biglist=0 total_querycmd=0
checked_broken=0

# 列出檔案裡的相對連結（去掉 fenced code block 與行內 code span 後取 ](…)）
extract_links() {
  awk '/^[[:space:]]*```/{c=!c; next} !c' "$1" \
    | sed -E 's/`[^`]*`//g' \
    | grep -oE '\]\([^)]+\)' \
    | sed -E 's/^\]\(//; s/\)$//; s/ "[^"]*"$//'
}

# 檢查一批檔案的連結；檔案清單由 stdin 提供，$1 = 顯示路徑時要去掉的前綴
check_links() {
  local prefix=${1%/} f d l broken=0
  while IFS= read -r f; do
    d=$(dirname "$f")
    while IFS= read -r l; do
      [[ -z $l ]] && continue
      case $l in http://*|https://*|mailto:*|'#'*|'<'*) continue ;; esac
      l=${l%%#*}
      [[ -z $l ]] && continue
      if [[ ! -e "$d/$l" ]]; then
        echo "BROKEN ${f#$prefix/} -> $l"
        broken=$((broken + 1))
      fi
    done < <(extract_links "$f")
  done
  checked_broken=$broken
}

# archive/reference/vendor 與 .gitmodules 宣告的 submodule 不下鑽。
list_owned_files() {
  local root=${1%/} _ rel
  shift
  local -a prunes=(
    -path '*/.git' -o -path '*/node_modules' -o -path '*/__pycache__'
    -o -path '*/archive' -o -path '*/reference' -o -path '*/references' -o -path '*/vendor'
  )
  while read -r _ rel; do
    [[ -n $rel ]] && prunes+=( -o -path "$root/${rel%/}" )
  done < <(git -C "$root" config --file .gitmodules --get-regexp '^submodule\..*\.path$' 2>/dev/null || true)
  find "$root" \( -type d \( "${prunes[@]}" \) \) -prune \
    -o -type f \( "$@" \) -print | sort
}

list_md() { list_owned_files "$1" -name '*.md'; }
list_data() { list_owned_files "$1" -name '*.json' -o -name '*.csv'; }

count_literal() {
  local needle=$1
  shift
  [[ $# -eq 0 ]] && { echo 0; return; }
  grep -hoF -- "$needle" "$@" 2>/dev/null | wc -l | tr -d ' '
}

# 檢查一個目錄
lint_dir() {
  local root=${1%/} label=${2:-$1}
  local broken=0 oversize=0 ph=0 note=0 judge=0 inbox=0 biglist=0 bl_links=0 querycmd=0
  local out df n rel
  local -a md_files=()

  [[ $quiet -eq 1 ]] || echo "== $label"
  mapfile -t md_files < <(list_md "$root")
  check_links "$root" < <(printf '%s\n' "${md_files[@]}")
  broken=$checked_broken

  if [[ $have_py -eq 1 ]]; then
    out=$(python3 "$tools/check_anchors.py" "$root" 2>/dev/null)
    if [[ -n $out ]]; then
      printf '%s\n' "$out"
      broken=$((broken + $(printf '%s\n' "$out" | grep -c '^BROKEN-ANCHOR ')))
    fi
  fi

  for f in "${md_files[@]}"; do
    case "$f" in */workflows/*) ;; *) continue ;; esac
    n=$(wc -c <"$f")
    [[ $n -le 8192 ]] && continue
    echo "OVERSIZE ${f#$root/} ($n bytes > 8192)"
    oversize=$((oversize + 1))
  done

  if [[ $have_py -eq 1 ]]; then
    if [[ ${#md_files[@]} -gt 0 ]]; then
      out=$(python3 "$tools/find_big_lists.py" --min 1024 \
              --exempt-file AGENTS.md --exempt-file WORKFLOWS.md --exempt-file INDEX.md \
              "${md_files[@]}" 2>/dev/null \
            | awk -F'\t' -v p="$root/" '{
                loc=$2; if (substr(loc,1,length(p))==p) loc=substr(loc,length(p)+1)
                sub(/^links=/, "", $5)
                printf "%s %s (%s bytes, %s, %s rows, %s links)\n",
                       ($6=="linked=all" ? "BIGLIST-LINKS" : "BIGLIST"), loc, $1, $3, $4, $5 }')
      if [[ -n $out ]]; then
        echo "$out"
        biglist=$(printf '%s\n' "$out" | grep -c '^BIGLIST ')
        bl_links=$(printf '%s\n' "$out" | grep -c '^BIGLIST-LINKS ')
      fi
    fi

    while IFS= read -r df; do
      [[ -z $df ]] && continue
      case "$df" in *.json) grep -q '"contract": "wf-table/' "$df" || continue ;; esac
      out=$(python3 "$tools/tabledb.py" check "$df" 2>/dev/null)
      n=$(printf '%s\n' "$out" | grep -c '"target"')
      [[ $n -eq 0 ]] && continue
      rel=${df#$root/}
      printf '%s\n' "$out" | awk -F'"' -v f="$rel" '
        /"index":/  { s=$3; gsub(/[^0-9]/, "", s); idx=s }
        /"column":/ { col=$4 }
        /"target":/ { print "BROKEN " f "[" idx "." col "] -> " $4 }'
      broken=$((broken + n))
    done < <(list_data "$root")
  fi

  # ⑦ QUERYCMD：md 不該教查法；免掃 archive/、wf/、AGENTS.md、契約檔
  for f in "${md_files[@]}"; do
    rel=${f#$root/}
    case "$f" in */archive/*|*/wf/*|*/workflows/tidy/*) continue ;; esac
    case "${f##*/}" in AGENTS.md|data-files.md|data-files-fmt.md|tidy.md) continue ;; esac
    while IFS= read -r ln; do
      echo "QUERYCMD $rel:$ln"; querycmd=$((querycmd + 1))
    done < <(grep -nE 'tabledb\.py' "$f" | grep -E 'python3 |tools/tabledb\.py' | cut -d: -f1)
  done

  ph=$(count_literal '{{' "${md_files[@]}")
  note=$(count_literal '〔模板說明〕' "${md_files[@]}")
  judge=$(count_literal '〔導入判斷〕' "${md_files[@]}")
  if [[ -d "$root/inbox" ]]; then
    inbox=$(find "$root/inbox" -maxdepth 1 -name '*.md' | wc -l | tr -d ' ')
  fi
  local residue=$((ph + note + judge))

  if [[ $quiet -eq 0 || $broken -gt 0 ]]; then
    echo "SUMMARY $label: broken=$broken oversize=$oversize biglist=$biglist biglist_links=$bl_links querycmd=$querycmd residue={{=$ph 模板說明=$note 導入判斷=$judge inbox_pending=$inbox"
  fi
  total_broken=$((total_broken + broken))
  if [[ $strict -eq 1 ]]; then
    total_residue=$((total_residue + residue))
    total_oversize=$((total_oversize + oversize))
    total_biglist=$((total_biglist + biglist))
    total_querycmd=$((total_querycmd + querycmd))
  fi
  return 0
}

if [[ $self -eq 1 ]]; then
  repo=$(cd "$(dirname "$0")/.." && pwd)
  cd "$repo" || exit 2

  # 根文件（只檢連結）
  echo "== repo root files"
  check_links "$repo" < <(printf '%s\n' README.md AGENTS.md CLAUDE.md IMPORT.md CHANGELOG.md docs/README.md docs/non-invasive-import.md \
    | while read -r f; do [[ -f $f ]] && echo "$repo/$f"; done)
  b=$checked_broken; total_broken=$((total_broken + b)); echo "SUMMARY root: broken=$b"

  # 本 repo 規矩：任何檔都不超過 8192 bytes
  while IFS= read -r f; do echo "OVERSIZE ${f#$repo/} ($(wc -c <"$f") bytes > 8192)"; total_broken=$((total_broken + 1)); done \
    < <(find "$repo" -type f -not -path '*/.git/*' -not -path '*/__pycache__/*' -size +8192c | sort)

  lint_dir "$repo/template" template

  for ex in "$repo"/examples/*/; do
    [[ -d $ex ]] || continue
    saved=$strict; strict=1; before=$total_residue
    lint_dir "$ex" "examples/$(basename "$ex")"
    strict=$saved
    [[ $total_residue -gt $before ]] && { echo "RESIDUE examples/$(basename "$ex") must have 0 residue"; total_broken=$((total_broken + 1)); }
  done

  # 各 flavor 單獨 + 全部一起，標準與非侵入式各跑一次
  flavors=()
  for fl in "$repo"/flavors/*/; do flavors+=("$(basename "$fl")"); done
  all=$(IFS=,; echo "${flavors[*]}")
  for combo in "${flavors[@]}" "$all"; do
    for mode in std wf; do
      tmp=$(mktemp -d)
      if [[ $mode == std ]]; then
        "$repo/tools/wf-init.sh" --target "$tmp" --flavor "$combo" --quiet >/dev/null || echo "wf-init failed: $combo ($mode)"
      else
        "$repo/tools/wf-init.sh" --target "$tmp" --flavor "$combo" --non-invasive wf --quiet >/dev/null || echo "wf-init failed: $combo ($mode)"
      fi
      lint_dir "$tmp" "merged[$combo,$mode]"
      rm -rf "$tmp"
    done
  done
else
  [[ ${#dirs[@]} -eq 0 ]] && dirs=(.)
  for d in "${dirs[@]}"; do lint_dir "$d" "$d"; done
fi

echo "TOTAL broken=$total_broken$( [[ $strict -eq 1 ]] && echo " residue=$total_residue oversize=$total_oversize biglist=$total_biglist querycmd=$total_querycmd" )"
[[ $total_broken -gt 0 ]] && exit 1
[[ $strict -eq 1 && $((total_residue + total_oversize + total_biglist + total_querycmd)) -gt 0 ]] && exit 1
exit 0
