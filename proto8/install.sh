#!/usr/bin/env bash
# install.sh [--dry-run] [--uninstall] [DEST] - symlink the aos commands onto PATH (default ~/.local/bin) and register the Python import paths in the user site.
#
# What gets linked (scanned by folder; only executables):
#   impls/*/bin/*            the C++ ones (aos-exec, aos-loop, aos-fsm, aos-daemon, aos-post, aos-json, aos-llm, aos-llm-kernel...; build them first)
#   cmd/*/bin/*              the Python commands (aos-daemon-ctl, aos-tools, aos-tick, aos-eca-turn, aos-eca-screen, aos-agent, aos-mcp, aos-sandbox, aos-grow)
# Also write aos-proto8.pth in the enabled Python user site with absolute py/ and lib/ paths; warn and continue if unavailable.
# Symlinks, not copies: the Python commands find their neighbour files through realpath(__file__). If the repo moves, run this again
#   (old links are reported as pointing elsewhere; rm them and rerun).
# Idempotent: a link to the same file = "already", left alone; something else with the same name in DEST = "skip" (not overwritten).
#   Links in DEST into this repo whose target is gone = a warning ("broken"), not removed.
# --dry-run: only print what would be done. Every stdout line says what was done; the last line is a summary.
# --uninstall: remove links into this repo (broken ones too) and aos-proto8.pth only when its entire content matches this repo.
# Another command with the same name earlier on PATH = one warning line; installs anyway.
# Does not change PATH or shell rc files: warns if DEST is not on PATH. Use on a Linux / WSL file system only (not /mnt/c).
# stderr: warnings are `install.sh: warning: SENTENCE`; errors are `install.sh: error: CODE reason` and mean exit 1:
#   ArgumentsBad, FlagUnknown, DestBad, CommandMissing, ImplsMissing (no impls built), LinkFailed (some names were skipped or
#   could not be installed; the last stderr line says how many).
#
# ---- 中文說明（--help 只印上面英文那段，到 stdout、退 0；11-05 stdio-unify R3、R13）----
# install.sh [--dry-run] [--uninstall] [目的地] - 把 aos 的指令 symlink 進一個 PATH 裡的資料夾（預設 ~/.local/bin），之後每個殼都找得到、不用 source env.sh。
#
# 裝哪些（照資料夾掃，有就裝、執行檔才算）：
#   impls/*/bin/*            C++ 的（aos-exec、aos-loop、aos-fsm、aos-daemon、aos-post、aos-json、aos-llm、aos-llm-kernel…；要先建，見 wf/workflows/testing.md「proto8」）
#   cmd/*/bin/*              Python 的指令（aos-daemon-ctl、aos-tools、aos-tick、aos-eca-turn、aos-eca-screen、aos-agent、aos-mcp、aos-sandbox、aos-grow）
# 也在 Python 啟用的 user site 寫 aos-proto8.pth，精確兩行為這份 repo 的 py/、lib/ 絕對路徑；不可用只提醒、其餘照裝，相同內容不動，不同內容不蓋。
# 為什麼 symlink 不 cp：Python 那幾支靠 realpath(__file__) 找旁邊的檔（aos_flags.py、using-aos-agent.sh、py/aos_ws.py…），
#   單檔 cp 過去會斷；symlink 解得回 repo 裡的原位。所以 repo 搬了位置要重跑一次（舊的連結會被報「指向別處」，自己 rm 再跑）。
#
# 冪等：已經是指向同一支的連結＝「已裝」、不動；目的地已有同名的別的東西（指向別處的連結、一般檔）＝印一行「跳過」、不蓋，
#   最後 stderr 補一行錯誤行 `install.sh: error: LinkFailed N names already taken by something else`、退 1（11-05 D3：使用者要的名字沒裝上＝沒做成）。
#   目的地裡指進這份 repo 但目標已不在的連結（指令改名或刪了）＝提醒行「broken」，不自己刪。
# stderr 只有兩種行（11-05 R1、R13）：提醒 `install.sh: warning: 句子`（PATH 上同名的排前面、目的地不在 PATH、repo 在 /mnt、斷掉的連結）、
#   錯誤 `install.sh: error: 代號 原因`（有它就退 1）：ArgumentsBad、FlagUnknown、DestBad、CommandMissing、ImplsMissing（impls 一支都沒建）、LinkFailed。
# --dry-run：只印會做什麼、不動。每一行都印出做了什麼；最後一行是統計。
# --uninstall：拿掉目的地裡指進這份 repo 的連結（含斷了的），也只刪內容完全相符的 aos-proto8.pth，別的不碰（11-05 B 線）。
# PATH 上同名的另一支排在前面（例 /usr/local/bin/aos-exec）＝印一行 warning，裝照裝（11-05 B 線）。
# 不改 PATH、不寫殼的設定檔：目的地不在 PATH 上就印一句提醒。只在 Linux／WSL 的檔案系統上用（/mnt/c 底下每個檔都 +x，見 dev-env）。
set -u

dry=0
un=0
dest=""
warn() { echo "install.sh: warning: $*" >&2; }
die() { echo "install.sh: error: $*" >&2; exit 1; }
usage="(usage: install.sh [--dry-run] [--uninstall] [DEST])"
for a in "$@"; do
  case "$a" in
    --dry-run) dry=1 ;;
    --uninstall) un=1 ;;
    --help) sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) die "FlagUnknown unknown flag $a $usage" ;;
    *) if [ -n "$dest" ]; then die "ArgumentsBad only one DEST allowed, extra: $a $usage"; fi; dest=$a ;;
  esac
done
[ -n "$dest" ] || dest="$HOME/.local/bin"

here=$(cd "$(dirname "$(readlink -f "$0")")" && pwd -P)   # proto8/
case "$here" in /mnt/*) warn "the repo is at $here (a Windows drive), where every file looks executable to aos; use a clone on the Linux file system" ;; esac

if [ -e "$dest" ] && [ ! -d "$dest" ]; then
  die "DestBad $dest exists and is not a directory"
fi

pth=""
if user_site=$(python3 -m site --user-site 2>/dev/null) && [ -n "$user_site" ]; then
  pth="$user_site/aos-proto8.pth"
else
  warn "Python user site is unavailable or disabled; skipping aos-proto8.pth"
fi
pth_matches() { [ -f "$pth" ] && cmp -s "$pth" <(printf '%s\n' "$here/py" "$here/lib"); }

if [ $un = 1 ]; then   # 11-05 B 線：拿掉指進這份 repo 的連結
  n=0
  for l in "$dest"/*; do
    [ -L "$l" ] || continue
    case "$(readlink "$l")" in "$here"/*)
      if [ $dry = 1 ]; then echo "would remove $(basename "$l")"; else rm -f "$l" && echo "removed $(basename "$l")"; fi
      n=$((n+1)) ;;
    esac
  done
  if [ -n "$pth" ] && pth_matches; then
    if [ $dry = 1 ]; then echo "would remove $pth"
    elif rm -f "$pth" 2>/dev/null; then echo "removed $pth"
    else die "LinkFailed cannot remove $pth"; fi
  fi
  echo "done: removed $n link(s) pointing into $here (dest $dest)"
  exit 0
fi

if [ ! -d "$dest" ]; then
  if [ $dry = 1 ]; then echo "would create folder $dest"; else mkdir -p "$dest" && echo "created folder $dest"; fi
fi

n_new=0; n_same=0; n_skip=0; n_fail=0; n_none=0
link_one() {   # $1＝repo 裡那支的絕對路徑
  local src=$1 name dst cur
  name=$(basename "$src"); dst="$dest/$name"
  if [ -L "$dst" ]; then
    cur=$(readlink "$dst")
    if [ "$cur" = "$src" ]; then echo "already linked $name"; n_same=$((n_same+1)); return; fi
    echo "skip $name: $dst is already a link to $cur (not $src of this repo; rm it yourself and rerun to replace)"; n_skip=$((n_skip+1)); return
  fi
  if [ -e "$dst" ]; then
    echo "skip $name: $dst is something else (not overwritten; move it away yourself and rerun to replace)"; n_skip=$((n_skip+1)); return
  fi
  if [ $dry = 1 ]; then echo "would link $name -> $src"
  elif ln -s "$src" "$dst"; then echo "linked $name -> $src"
  else warn "cannot link $dst"; n_fail=$((n_fail+1)); return   # 11-05 B 線：原本失敗也算「裝」；錯誤行最後一起補
  fi
  n_new=$((n_new+1))
}

found=0
for src in "$here"/impls/*/bin/* "$here"/cmd/*/bin/*; do
  [ -f "$src" ] && [ -x "$src" ] || continue
  case "$src" in "$here"/impls/*/bin/*)   # 只裝現役的 impls（有 CMakeLists.txt 的）；改名前留下的舊 build 產物（aos-llm-send 之類）不裝
    [ -f "${src%/bin/*}/CMakeLists.txt" ] || continue ;;
  esac
  found=1
  link_one "$src"
done
[ $found = 1 ] || die "CommandMissing no command found ($here does not look like proto8?)"
ls "$here"/impls/*/bin/* >/dev/null 2>&1 || n_none=1   # 錯誤行最後補（ImplsMissing）

if [ -n "$pth" ]; then
  if pth_matches; then
    echo "already registered $pth"
  elif [ -e "$pth" ] || [ -L "$pth" ]; then
    echo "skip aos-proto8.pth: $pth is something else (not overwritten; move it away yourself and rerun to replace)"
    n_skip=$((n_skip+1))
  elif [ $dry = 1 ]; then
    echo "would write $pth -> $here/py, $here/lib"
  elif (mkdir -p "$user_site" && printf '%s\n' "$here/py" "$here/lib" > "$pth") 2>/dev/null; then
    echo "wrote $pth -> $here/py, $here/lib"
  else
    warn "cannot write $pth"; n_fail=$((n_fail+1))
  fi
fi

# 目的地裡指進這份 repo、目標已不在的連結：只報不刪
for l in "$dest"/*; do
  [ -L "$l" ] || continue
  t=$(readlink "$l")
  case "$t" in "$here"/*) [ -e "$t" ] || warn "broken $(basename "$l") -> $t (target is gone; rm $l if unwanted)" ;; esac
done

# 11-05 B 線：PATH 上排在前面的同名指令會蓋掉裝的這支
for src in "$dest"/*; do
  [ -L "$src" ] || continue
  case "$(readlink "$src")" in "$here"/*) ;; *) continue ;; esac
  name=$(basename "$src"); got=$(command -v "$name" 2>/dev/null) || continue
  [ "$got" = "$src" ] || [ "$(readlink -f "$got")" = "$(readlink -f "$src")" ] || warn "$name on PATH resolves to $got first (not $src)"
done
case ":$PATH:" in *":$dest:"*) ;; *) warn "$dest is not on PATH: add export PATH=\"$dest:\$PATH\" to ~/.bashrc (this script does not)" ;; esac
verb=linked; [ $dry = 1 ] && verb="would link"
echo "done: $verb $n_new, already $n_same, skipped $n_skip (dest $dest)"
rc=0
if [ $n_none = 1 ]; then
  echo "install.sh: error: ImplsMissing no impls built (impls/*/bin is empty): build them first (wf/workflows/testing.md, proto8) and run again" >&2; rc=1
fi
if [ $n_skip != 0 ] || [ $n_fail != 0 ]; then
  if [ $n_fail = 0 ]; then why="$n_skip names already taken by something else"
  else why="$((n_skip+n_fail)) names not installed ($n_skip already taken by something else, $n_fail failed to install)"; fi
  echo "install.sh: error: LinkFailed $why" >&2; rc=1
fi
exit $rc
