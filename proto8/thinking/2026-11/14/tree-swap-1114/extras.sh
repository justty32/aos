#!/bin/bash
# extras.sh - 11-14 換樹：swap.sh 不管的幾件（agents/ 定義、.env、~/.local/bin 兩條連結、defs/gpt-* 的 brain_notify）。
# 用法：extras.sh --ref <commit> [check | hooks | env | brainnotify | guard | links | verify ...]（不給段＝check）
#   hooks       ~/aos-home/agents 每個 eca 定義的 hooks.json 換成 <ref> 的 templates/eca-claude/hooks.json（加 screen_linger 兩格）；
#               只換「跟某一版範本逐位元相同」的，有人手改過就 RED、不動。
#   env         agents/{opus-kernel,fable-kernel,xiaosi}/.env 寫一行 PATH=${HOME}/repo/aos/wf/tools:${PATH}；已有別的內容就 RED。
#   brainnotify defs/gpt-lead、defs/gpt-worker 的 hooks.json 加 <ref> 的 agent-fsm 範本 brain_notify 一格（使用者還沒裁，裁了才跑）。
#   guard       defs/shared/guard 換成 <ref> 的 wf/public/tools/fsm-guard/guard（線星 ADV 313ce20ec），換完照 ok-astra 的五條對 gpt-lead、gpt-worker 驗退出碼。
#   links       ~/.local/bin 的 commit-request、aos-llm-kernel 兩條連結搬進備份夾（不刪；要等 agent 裡 which commit-request 找得到 wf/tools 那支才跑）。
#   verify      核對上面各段的結果。
# 不含 kill／shutdown；hooks、env、brainnotify 要樹停著（swap.sh 同一套判定）。不刪任何東西：換下來的檔都搬進
# $TS_BACKUP_ROOT/run-<時間>-<pid>-extras/，MANIFEST 記「原路徑<TAB>備份路徑」（備份路徑是 - ＝原本沒有這個檔）；退回用 extras-rollback.sh。
[ -n "$BASH_VERSION" ] || { echo "extras.sh: not bash, refuse" >&2; exit 2; }
set -euo pipefail
TS_REPO=${TS_REPO:-$HOME/repo/aos}
. "$TS_REPO/proto8/extras/tree-swap/common.sh"
TS_LINK_DIR=${TS_LINK_DIR:-$HOME/.local/bin}
ECA_DEFS=${ECA_DEFS:-"eca_main fable-kernel opus-kernel repo-aos xiaosi"}
ENV_DEFS=${ENV_DEFS:-"opus-kernel fable-kernel xiaosi"}
GPT_DEFS=${GPT_DEFS:-"gpt-lead gpt-worker"}
LINKS=${LINKS:-"commit-request aos-llm-kernel"}
ENV_LINE='PATH=${HOME}/repo/aos/wf/tools:${PATH}'

REF=""; STEPS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --ref) REF=$2; shift 2 ;;
    -h|--help) sed -n 2,12p "$0"; exit 0 ;;
    check|hooks|env|brainnotify|guard|links|verify) STEPS+=("$1"); shift ;;
    *) echo "extras.sh: unknown arg $1" >&2; exit 2 ;;
  esac
done
[ -n "$REF" ] || { echo "extras.sh: --ref <commit> is required" >&2; exit 2; }
[ ${#STEPS[@]} -gt 0 ] || STEPS=(check)
ts_refuse_agent_env
REF=$(git -C "$TS_REPO" rev-parse --verify "$REF^{commit}") || ts_red "ref not found in $TS_REPO"
ts_run_dir extras
trap ts_kept_report EXIT
MAN="$TS_RUN/MANIFEST"; : > "$MAN"
printf 'ref=%s\ntree=%s\nlink_dir=%s\ntime=%s\n' "$REF" "$TS_TREE" "$TS_LINK_DIR" "$(date -Is)" > "$TS_RUN/META"
echo "tree=$TS_TREE ref=$REF link_dir=$TS_LINK_DIR run=$TS_RUN"

NEW_ECA=$(git -C "$TS_REPO" show "$REF:proto8/templates/eca-claude/hooks.json")
# 這個 commit 以前每一版 eca-claude 範本 hooks.json 的 md5（活樹定義是當時範本的原樣抄本）
known_eca_md5() { local c; for c in $(git -C "$TS_REPO" log --format=%h "$REF" -- proto8/templates/eca-claude/hooks.json); do git -C "$TS_REPO" show "$c:proto8/templates/eca-claude/hooks.json" | md5sum | cut -c1-32; done; }
new_md5() { printf '%s\n' "$NEW_ECA" | md5sum | cut -c1-32; }

# 換一個檔：舊的搬進備份、新的寫旁邊再改名；$1＝目標 $2＝新內容檔 $3＝權限（預設 644）
put_file() {
  local dst=$1 src=$2 mode=${3:-644} keep
  if [ -e "$dst" ] || [ -L "$dst" ]; then
    keep="$TS_RUN/files$dst"; mkdir -p "$(dirname "$keep")"; cp -a "$dst" "$keep"
  else keep=-; fi
  cp "$src" "$dst.extras-new"; chmod "$mode" "$dst.extras-new"; mv -f "$dst.extras-new" "$dst"
  printf '%s\t%s\n' "$dst" "$keep" >> "$MAN"
}

step_check() {
  local a f m known g n=0
  known=$(known_eca_md5)
  for a in $ECA_DEFS; do
    f="$TS_TREE/agents/$a/hooks.json"; [ -f "$f" ] || ts_red "$f missing"
    m=$(md5sum < "$f" | cut -c1-32)
    if [ "$m" = "$(new_md5)" ]; then echo "hooks $a: already the $REF template"
    elif grep -qx "$m" <<< "$known"; then echo "hooks $a: an older template copy, will be replaced"; n=$((n+1))
    else ts_red "hooks $a: $f is not any template version (edited by hand?); merge it by hand"; fi
  done
  for a in $ENV_DEFS; do
    f="$TS_TREE/agents/$a/.env"
    if [ ! -e "$f" ]; then echo "env $a: no .env, will write one line"
    elif grep -qxF "$ENV_LINE" "$f"; then echo "env $a: already has the line"
    else ts_red "env $a: $f exists with other content; merge it by hand"; fi
  done
  for g in $GPT_DEFS; do
    f="$TS_TREE/defs/$g/hooks.json"; [ -f "$f" ] || { echo "brainnotify $g: no $f (skipped)"; continue; }
    python3 -c 'import json,sys; h=json.load(open(sys.argv[1]))["hooks"]; print("brainnotify %s: %s" % (sys.argv[2], "already has brain_notify" if "brain_notify" in h else "no brain_notify (only added if you run the brainnotify step)"))' "$f" "$g"
  done
  f="$TS_TREE/defs/shared/guard"
  if [ ! -f "$f" ]; then echo "guard: no $f (guard step skips it)"
  elif git -C "$TS_REPO" show "$REF:wf/public/tools/fsm-guard/guard" | cmp -s - "$f"; then echo "guard: already the $REF version"
  else echo "guard: differs from $REF wf/public/tools/fsm-guard/guard, guard step will replace it"; fi
  for l in $LINKS; do
    f="$TS_LINK_DIR/$l"
    if [ -L "$f" ]; then echo "link $l -> $(readlink "$f")"; else echo "link $l: not there (links step skips it)"; fi
  done
  echo "check: green ($n eca hooks.json to replace)"
}

step_hooks() {
  ts_require_stopped
  local a f known tmp
  known=$(known_eca_md5)
  tmp="$TS_RUN/new-eca-hooks.json"; printf '%s\n' "$NEW_ECA" > "$tmp"
  for a in $ECA_DEFS; do
    f="$TS_TREE/agents/$a/hooks.json"
    m=$(md5sum < "$f" | cut -c1-32)
    [ "$m" = "$(new_md5)" ] && { echo "hooks $a: already new"; continue; }
    grep -qx "$m" <<< "$known" || ts_red "hooks $a: not a template copy; nothing more changed (earlier ones are in $MAN)"
    put_file "$f" "$tmp"; echo "hooks $a: replaced"
  done
}

step_env() {
  ts_require_stopped
  local a f tmp
  tmp="$TS_RUN/new.env"; printf '%s\n' "$ENV_LINE" > "$tmp"
  for a in $ENV_DEFS; do
    f="$TS_TREE/agents/$a/.env"
    if [ -e "$f" ]; then grep -qxF "$ENV_LINE" "$f" && { echo "env $a: already there"; continue; }; ts_red "env $a: $f has other content"; fi
    put_file "$f" "$tmp"; echo "env $a: written"
  done
}

step_brainnotify() {
  ts_require_stopped
  local g f tmp entry
  entry=$(git -C "$TS_REPO" show "$REF:proto8/templates/agent-fsm/hooks.json" | python3 -c 'import json,sys; print(json.dumps(json.load(sys.stdin)["hooks"]["brain_notify"]))')
  for g in $GPT_DEFS; do
    f="$TS_TREE/defs/$g/hooks.json"; [ -f "$f" ] || continue
    tmp="$TS_RUN/new-$g-hooks.json"
    rc=0
    python3 - "$f" "$entry" "$tmp" <<'PY' || rc=$?
import json, sys
d = json.load(open(sys.argv[1]))
if "brain_notify" in d["hooks"]:
    sys.exit(5)
d["hooks"]["brain_notify"] = json.loads(sys.argv[2])
open(sys.argv[3], "w").write(json.dumps(d, ensure_ascii=False, indent=1) + "\n")
PY
    [ $rc = 5 ] && { echo "brainnotify $g: already there"; continue; }
    put_file "$f" "$tmp"; echo "brainnotify $g: added"
  done
}

# ok-astra 11-14 的驗法：清 AOS_* 後餵五條。gpt-worker 要 0 0 10 0 10；gpt-lead 的 guard.json 沒有 rm 那條（新舊 guard 都放行 cd x && rm y），要 0 0 0 0 10
guard_probe() {
  local W=$1 T got="" c
  T="$TS_RUN/guard-probe-$(basename "$W")"; mkdir -p "$T"
  while IFS= read -r c; do
    got="$got $(printf '%s\n' "$c" | env -u AOS_KERNEL AOS_WS="$T" AOS_STACK="$T" "$W/guard" >/dev/null 2>&1; echo $?)"
  done <<'J'
{"name":"shell","arguments":{"command":"rg -n 'rm accepted' x"}}
{"name":"shell","arguments":{"command":"pgrep -u \"$USER\" -af aos-daemon"}}
{"name":"shell","arguments":{"command":"cd x && rm y"}}
{"name":"shell","arguments":{"command":"uniq a b"}}
{"name":"write","arguments":{"path":"/etc/x","content":""}}
J
  echo "${got# }"
}

step_guard() {
  ts_require_stopped
  local f tmp g r want
  f="$TS_TREE/defs/shared/guard"; [ -f "$f" ] || { echo "guard: no $f"; return 0; }
  tmp="$TS_RUN/new-guard"; git -C "$TS_REPO" show "$REF:wf/public/tools/fsm-guard/guard" > "$tmp"
  if cmp -s "$tmp" "$f"; then echo "guard: already new"; else put_file "$f" "$tmp" 755; echo "guard: replaced"; fi
  for g in $GPT_DEFS; do
    [ -x "$TS_TREE/defs/$g/guard" ] || continue
    case $g in gpt-lead) want="0 0 0 0 10" ;; *) want="0 0 10 0 10" ;; esac
    r=$(guard_probe "$TS_TREE/defs/$g")
    [ "$r" = "$want" ] || ts_red "guard probe $g gave [$r], want [$want]; roll back with extras-rollback.sh $TS_RUN"
    echo "guard probe $g: $r (ok)"
  done
}

step_links() {
  local l f keep
  for l in $LINKS; do
    f="$TS_LINK_DIR/$l"
    [ -L "$f" ] || { echo "link $l: not there"; continue; }
    keep="$TS_RUN/files$f"; mkdir -p "$(dirname "$keep")"
    mv -T "$f" "$keep"; printf '%s\t%s\n' "$f" "$keep" >> "$MAN"
    echo "link $l: moved to $keep (not deleted)"
  done
}

step_verify() {
  local a bad=0
  for a in $ECA_DEFS; do
    [ "$(md5sum < "$TS_TREE/agents/$a/hooks.json" | cut -c1-32)" = "$(new_md5)" ] && echo "verify hooks $a: ok" || { echo "verify hooks $a: NOT the $REF template"; bad=1; }
  done
  for a in $ENV_DEFS; do
    grep -qxF "$ENV_LINE" "$TS_TREE/agents/$a/.env" 2>/dev/null && echo "verify env $a: ok" || { echo "verify env $a: missing"; bad=1; }
  done
  [ $bad = 0 ] || ts_red "verify failed"
  echo "verify: green"
}

for s in "${STEPS[@]}"; do ts_t0; "step_$s"; ts_t1 "$s"; done
[ -s "$MAN" ] && { echo "manifest: $MAN"; cat "$MAN"; } || true
