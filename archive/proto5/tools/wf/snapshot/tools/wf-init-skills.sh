#!/usr/bin/env bash
# wf-init-skills.sh — --skills 的複製與轉址；由 wf-init.sh source，不單獨執行。
# 用到呼叫端已設好的 $repo／$target／$wfroot／$wfdir／$sklist（陣列）與 say()／copy_tree()。

skills_all_names() { # skills/ 底下所有含 SKILL.md 的資料夾名，逗號分隔
  local names=() d
  for d in "$repo"/skills/*/; do
    [[ -f "${d}SKILL.md" ]] || continue
    names+=("$(basename "$d")")
  done
  local IFS=,
  echo "${names[*]}"
}

write_skill_redirect() { # $1 = 技能名；在 <target>/.claude/skills/<name>/ 產轉址
  local sk=$1 src="$repo/skills/$sk/SKILL.md" dst="$target/.claude/skills/$sk/SKILL.md"
  local fm name_line desc_line rel
  fm=$(sed -n '/^---$/,/^---$/p' "$src" | sed '1d;$d')
  name_line=$(printf '%s\n' "$fm" | grep '^name:')
  desc_line=$(printf '%s\n' "$fm" | grep '^description:')
  rel="skills/$sk/SKILL.md"
  [[ -n $wfdir ]] && rel="$wfdir/skills/$sk/SKILL.md"
  mkdir -p "$(dirname "$dst")"
  {
    echo "---"
    echo "$name_line"
    echo "$desc_line"
    echo "---"
    echo
    echo "# $sk（技能轉址）"
    echo
    echo "去讀 [\`$sk/SKILL.md\`](../../../$rel) 並照著做。"
  } > "$dst"
  say "  skill redirect → .claude/skills/$sk/SKILL.md"
}

expand_skills_closure() { # 就地把 $sklist 展開成遞移閉包（技能間 ](../<name>/...) 連結相依）
  local -A seen=()
  local sk f link name grew=1 iter=0
  local -a added=()
  for sk in "${sklist[@]}"; do [[ -n $sk ]] && seen[$sk]=1; done
  while [[ $grew -eq 1 && $iter -lt 20 ]]; do
    grew=0; iter=$((iter + 1))
    for sk in "${!seen[@]}"; do
      while IFS= read -r f; do
        [[ -e $f ]] || continue
        while IFS= read -r link; do
          name=${link#../}; name=${name%%/*}
          [[ -n $name && -z ${seen[$name]:-} && -f "$repo/skills/$name/SKILL.md" ]] || continue
          seen[$name]=1; added+=("$name"); grew=1
        done < <(grep -ohE '\]\(\.\./[^)]+\)' "$f" 2>/dev/null | sed -E 's/^\]\(//; s/\)$//')
      done < <(find "$repo/skills/$sk" -name '*.md')
    done
  done
  sklist=("${!seen[@]}")
  [[ ${#added[@]} -gt 0 ]] && say "  skills 相依補裝：${added[*]}"
}

install_skills() { # 複製 skills/<name>/ 整包到 <wfroot>/skills/，並逐一產轉址
  local sk
  expand_skills_closure
  mkdir -p "$wfroot/skills"
  for sk in "${sklist[@]}"; do
    [[ -z $sk ]] && continue
    copy_tree "$repo/skills/$sk" "$wfroot/skills/$sk"
  done
  [[ -d "$repo/skills/LICENSES" ]] && copy_tree "$repo/skills/LICENSES" "$wfroot/skills/LICENSES"
  for sk in "${sklist[@]}"; do
    [[ -z $sk ]] && continue
    write_skill_redirect "$sk"
  done
  say "skills → $wfroot/skills (${sklist[*]})"
}
