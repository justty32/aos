#!/usr/bin/env bash
# wf-init.sh — 把 kernel + 選定的 flavor 包合成到一個專案（純 bash + cp/sed/awk/grep）
#
#   tools/wf-init.sh --target <專案根> [--flavor a,b,c] [--non-invasive [子資料夾]] [--redirect f1,f2] [--skills a,b,c|all] [--quiet]
#
#   --flavor         逗號分隔的 flavor 名（flavors/ 底下的資料夾名）；可省略＝只裝 kernel
#   --non-invasive   頂層只留 AGENTS.md / CLAUDE.md / .claude/（與各 flavor 的頂層項目如 inbox/），
#                    其餘收進 <子資料夾>（預設 wf）；連結自動改寫
#   --redirect       逗號分隔的轉址檔名（預設只產 CLAUDE.md）：把轉址內容另存成其他 agent 工具讀的
#                    入口檔名，例 GEMINI.md、.github/copilot-instructions.md
#   --skills         逗號分隔的技能名（skills/ 底下含 SKILL.md 的資料夾名）或 all＝全裝；
#                    整包複製到 <wfroot>/skills/，並在 <target>/.claude/skills/<name>/ 產轉址
#   工具（wf-lint.sh 與 check_anchors.py／tabledb.py／tabledb_links.py／tabledb_fmt.py／tabledb_fmt_vars.py／find_big_lists.py／fix_moved_links.py／fix_moved_links_fmt.py 與 fmt-vars.json，
#   不含測試）一併複製到 <wfroot>/tools/。結束時印出殘留清單（{{ 佔位、〔導入判斷〕）並跑 wf-lint。
# 無法自動化的只有兩件事：填 {{}}（要專案事實）與判斷〔導入判斷〕——交給人或 agent 收尾（見 IMPORT.md）。
set -u

repo=$(cd "$(dirname "$0")/.." && pwd)
target="" flavors="" wfdir="" redirects="" skills="" quiet=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) target=$2; shift 2 ;;
    --flavor|--flavors) flavors=$2; shift 2 ;;
    --non-invasive)
      wfdir=wf
      if [[ $# -ge 2 && $2 != --* ]]; then wfdir=$2; shift; fi
      shift ;;
    --redirect|--redirects) redirects=$2; shift 2 ;;
    --skills|--skill) skills=$2; shift 2 ;;
    --quiet|-q) quiet=1; shift ;;
    -h|--help) sed -n '2,17p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done
[[ -z $target ]] && { echo "--target is required" >&2; exit 2; }
say() { [[ $quiet -eq 1 ]] || echo "$@"; }

# 非侵入式的連結改寫拆到同目錄的 wf-init-relink.sh（母檔已到 8 KB 上限）。
. "$repo/tools/wf-init-relink.sh" || { echo "FATAL missing $repo/tools/wf-init-relink.sh" >&2; exit 2; }
# --skills 的複製與轉址拆到同目錄的 wf-init-skills.sh（母檔已到 8 KB 上限）。
. "$repo/tools/wf-init-skills.sh" || { echo "FATAL missing $repo/tools/wf-init-skills.sh" >&2; exit 2; }

# 驗 flavor 存在
IFS=',' read -r -a flist <<< "$flavors"
for fl in "${flist[@]}"; do
  [[ -z $fl ]] && continue
  [[ -d "$repo/flavors/$fl" ]] || { echo "no such flavor: $fl (see flavors/)" >&2; exit 2; }
done

# 驗 skills 存在（all＝skills/ 底下所有含 SKILL.md 的資料夾）
[[ $skills == all ]] && skills=$(skills_all_names)
IFS=',' read -r -a sklist <<< "$skills"
for sk in "${sklist[@]}"; do
  [[ -z $sk ]] && continue
  [[ -f "$repo/skills/$sk/SKILL.md" ]] || { echo "no such skill: $sk (see skills/)" >&2; exit 2; }
done

mkdir -p "$target"
target=$(cd "$target" && pwd)
[[ -e "$target/AGENTS.md" ]] && { echo "refuse: $target/AGENTS.md already exists (won't overwrite an existing import)" >&2; exit 1; }
wfroot=$target
[[ -n $wfdir ]] && wfroot="$target/$wfdir"
mkdir -p "$wfroot"

# ---------- 1. kernel ----------
# 留在專案根的項目：AGENTS.md 是中立入口；CLAUDE.md 是轉址檔、.claude/ 是 Claude Code 適配層
# （該工具只讀專案根那一層，故非侵入式佈局也留在根）
root_items=(AGENTS.md CLAUDE.md .claude)
copy_tree() { # $1 = src dir, $2 = dst dir（合併，不清空）
  mkdir -p "$2"; cp -R "$1/." "$2/"
}
for entry in "$repo"/template/* "$repo"/template/.claude; do
  name=$(basename "$entry")
  dest=$wfroot
  for r in "${root_items[@]}"; do [[ $name == "$r" ]] && dest=$target; done
  if [[ -d $entry ]]; then copy_tree "$entry" "$dest/$name"; else cp "$entry" "$dest/$name"; fi
done
mkdir -p "$wfroot/tools"
# wf-lint-checks.sh 是被 source 的函式庫，跟著 wf-lint.sh 一起複製
for sh in wf-lint.sh wf-lint-checks.sh; do cp "$repo/tools/$sh" "$wfroot/tools/$sh"; done
chmod +x "$wfroot/tools/wf-lint.sh"
cp "$repo/tools/fmt-vars.json" "$wfroot/tools/fmt-vars.json"
for py in "$repo"/tools/*.py; do
  case "$(basename "$py")" in test_*) continue ;; esac
  cp "$py" "$wfroot/tools/"
done
say "kernel → $wfroot${wfdir:+ (AGENTS.md / CLAUDE.md / .claude/ → $target)}"

# 轉址檔：其他 agent 工具的入口檔名（內容同 CLAUDE.md，都只是指回 AGENTS.md）
IFS=',' read -r -a rdlist <<< "$redirects"
for rd in "${rdlist[@]}"; do
  [[ -z $rd || $rd == CLAUDE.md ]] && continue
  mkdir -p "$(dirname "$target/$rd")"
  up=""; rdd=$(dirname "$rd")
  while [[ $rdd != . && $rdd != / && -n $rdd ]]; do up="../$up"; rdd=$(dirname "$rdd"); done
  sed "s#](AGENTS.md)#](${up}AGENTS.md)#" "$target/CLAUDE.md" > "$target/$rd"
  say "  redirect → $rd"
done

# ---------- 2. flavors ----------
marker_candidates() { # 只在合法能持有 marker 的檔案裡找，避免 examples/ 之類的誤中
  if [[ -n $wfdir ]]; then
    find "$wfroot" -name '*.md' 2>/dev/null
    for f in "$target"/*.md; do [[ -f $f ]] && echo "$f"; done
  else
    for f in "$target"/*.md; do [[ -f $f ]] && echo "$f"; done
    [[ -d "$target/workflows/common" ]] && find "$target/workflows/common" -name '*.md' 2>/dev/null
  fi
}
insert_fragment() { # $1 = marker name, $2 = fragment file
  local marker="<!-- wf-insert:$1 -->" hit=""
  while IFS= read -r f; do grep -q -F "$marker" "$f" 2>/dev/null && { hit=$f; break; }; done < <(marker_candidates)
  [[ -z $hit ]] && { echo "  ! no marker $marker found for $(basename "$2")" >&2; return 1; }
  awk -v marker="$marker" -v frag="$2" '
    index($0, marker) { while ((getline line < frag) > 0) print line; close(frag) }
    { print }' "$hit" > "$hit.tmp" && mv "$hit.tmp" "$hit"
  # 第一次貼派發表時拿掉 kernel 的〔導入判斷〕佔位行
  [[ $1 == WORKFLOWS ]] && sed -i.bak '/^〔導入判斷〕尚未貼入任何 flavor 派發表/d' "$hit" && rm -f "$hit.bak"
  say "  fragment $(basename "$2") → ${hit#$target/}"
}
for fl in "${flist[@]}"; do
  [[ -z $fl ]] && continue
  src="$repo/flavors/$fl"
  say "flavor $fl:"
  for entry in "$src"/* "$src"/.[!.]*; do
    [[ -e $entry ]] || continue
    name=$(basename "$entry")
    case "$name" in
      README.md) continue ;;
      *."$fl".md) continue ;;                       # 片段，稍後處理
      workflows) copy_tree "$entry" "$wfroot/workflows" ;;
      *) if [[ -d $entry ]]; then copy_tree "$entry" "$target/$name"; else cp "$entry" "$target/$name"; fi ;;
    esac
  done
  for frag in "$src"/*."$fl".md; do
    [[ -e $frag ]] || continue
    insert_fragment "$(basename "$frag" ".$fl.md")" "$frag"
  done
done

# ---------- 3. 非侵入式：改寫因搬家而斷的相對連結（見 wf-init-relink.sh）----------
[[ -n $wfdir ]] && rewrite_moved_links

# ---------- 3.5 skills（見 wf-init-skills.sh；須排在非侵入式改寫之後，避免路徑被誤改）----------
[[ -n $skills ]] && install_skills

# ---------- 4. 殘留清單 + lint ----------
if [[ $quiet -eq 0 ]]; then
  echo
  echo "== 殘留 {{ 佔位（要填專案事實）=="
  grep -rn --include='*.md' -o '{{[^}]*}}' "$target" | sed "s#^$target/##" | sort | uniq -c | sort -rn | head -60
  echo
  echo "== 〔導入判斷〕（要人決定、決定後刪段並同步）=="
  grep -rn --include='*.md' '〔導入判斷〕' "$target" | sed "s#^$target/##"
  echo
  echo "== 〔模板說明〕 $(grep -rn --include='*.md' '〔模板說明〕' "$target" | wc -l | tr -d ' ') 段（讀完刪）=="
  echo
  bash "$wfroot/tools/wf-lint.sh" "$target"
fi
