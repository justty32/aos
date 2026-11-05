#!/usr/bin/env bash
# install.sh [--dry-run] [--uninstall] [DEST] - symlink the aos commands into a folder on PATH (default ~/.local/bin), so every shell finds them without sourcing env.sh.
#
# What gets linked (scanned by folder; only executables):
#   impls/*/bin/*            the C++ ones (aos-exec, aos-loop, aos-fsm, aos-daemon, aos-post, aos-json, aos-llm, aos-llm-kernel...; build them first)
#   bin/aos-*                the Python ones (aos-daemon-ctl, aos-tools, aos-tick, aos-eca-turn, aos-eca-screen; aos_flags.py is not a command)
#   extras/agent/bin/*       aos-agent
#   extras/ai_tools/bin/*    aos-mcp
#   extras/sandbox/bin/*     aos-sandbox
#   extras/grow/aos-grow     aos-grow
# Symlinks, not copies: the Python commands find their neighbour files through realpath(__file__). If the repo moves, run this again
#   (old links are reported as pointing elsewhere; rm them and rerun).
# Idempotent: a link to the same file = "already", left alone; something else with the same name in DEST = "skip" (not overwritten), exit 1.
#   Links in DEST into this repo whose target is gone = reported as "broken", not removed.
# --dry-run: only print what would be done. Every line says what was done; the last line is a summary.
# --uninstall: remove the links in DEST that point into this repo (broken ones too); nothing else is touched.
# Another command with the same name earlier on PATH = one warning line; installs anyway.
# Does not change PATH or shell rc files: prints a reminder if DEST is not on PATH. Use on a Linux / WSL file system only (not /mnt/c).
#
# ---- 中文說明（-h 只印上面英文那段）----
# install.sh [--dry-run] [--uninstall] [目的地] - 把 aos 的指令 symlink 進一個 PATH 裡的資料夾（預設 ~/.local/bin），之後每個殼都找得到、不用 source env.sh。
#
# 裝哪些（照資料夾掃，有就裝、執行檔才算）：
#   impls/*/bin/*            C++ 的（aos-exec、aos-loop、aos-fsm、aos-daemon、aos-post、aos-json、aos-llm、aos-llm-kernel…；要先建，見 wf/workflows/testing.md「proto8」）
#   bin/aos-*                Python 的（aos-daemon-ctl、aos-tools、aos-tick、aos-eca-turn、aos-eca-screen；aos_flags.py 不是指令、不裝）
#   extras/agent/bin/*       aos-agent
#   extras/ai_tools/bin/*    aos-mcp
#   extras/sandbox/bin/*     aos-sandbox
#   extras/grow/aos-grow     aos-grow
# 為什麼 symlink 不 cp：Python 那幾支靠 realpath(__file__) 找旁邊的檔（aos_flags.py、using-aos-agent.sh、lib/aos/aos_ws.py…），
#   單檔 cp 過去會斷；symlink 解得回 repo 裡的原位。所以 repo 搬了位置要重跑一次（舊的連結會被報「指向別處」，自己 rm 再跑）。
#
# 冪等：已經是指向同一支的連結＝「已裝」、不動；目的地已有同名的別的東西（指向別處的連結、一般檔）＝印一行「跳過」、不蓋，最後退 1。
#   目的地裡指進這份 repo 但目標已不在的連結（指令改名或刪了）＝印「斷了」提醒，不自己刪。
# --dry-run：只印會做什麼、不動。每一行都印出做了什麼；最後一行是統計。
# --uninstall：拿掉目的地裡指進這份 repo 的連結（含斷了的），別的不碰（11-05 B 線）。
# PATH 上同名的另一支排在前面（例 /usr/local/bin/aos-exec）＝印一行 warning，裝照裝（11-05 B 線）。
# 不改 PATH、不寫殼的設定檔：目的地不在 PATH 上就印一句提醒。只在 Linux／WSL 的檔案系統上用（/mnt/c 底下每個檔都 +x，見 dev-env）。
set -u

dry=0
un=0
dest=""
for a in "$@"; do
  case "$a" in
    --dry-run) dry=1 ;;
    --uninstall) un=1 ;;
    -h|--help) sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) echo "install.sh: ArgumentsBad unknown flag $a" >&2; exit 1 ;;
    *) if [ -n "$dest" ]; then echo "install.sh: ArgumentsBad only one DEST allowed" >&2; exit 1; fi; dest=$a ;;
  esac
done
[ -n "$dest" ] || dest="$HOME/.local/bin"

here=$(cd "$(dirname "$(readlink -f "$0")")" && pwd -P)   # proto8/
case "$here" in /mnt/*) echo "install.sh: note: the repo is at $here (a Windows drive), where every file looks executable to aos; use a clone on the Linux file system" >&2 ;; esac

if [ -e "$dest" ] && [ ! -d "$dest" ]; then
  echo "install.sh: DestBad $dest exists and is not a directory" >&2; exit 1
fi

if [ $un = 1 ]; then   # 11-05 B 線：拿掉指進這份 repo 的連結
  n=0
  for l in "$dest"/*; do
    [ -L "$l" ] || continue
    case "$(readlink "$l")" in "$here"/*)
      if [ $dry = 1 ]; then echo "would remove $(basename "$l")"; else rm -f "$l" && echo "removed $(basename "$l")"; fi
      n=$((n+1)) ;;
    esac
  done
  echo "done: removed $n link(s) pointing into $here (dest $dest)"
  exit 0
fi

if [ ! -d "$dest" ]; then
  if [ $dry = 1 ]; then echo "would create folder $dest"; else mkdir -p "$dest" && echo "created folder $dest"; fi
fi

n_new=0; n_same=0; n_skip=0; n_none=0
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
  else echo "install.sh: LinkFailed $dst" >&2; n_skip=$((n_skip+1)); return   # 11-05 B 線：原本失敗也算「裝」
  fi
  n_new=$((n_new+1))
}

found=0
for src in "$here"/impls/*/bin/* "$here"/bin/aos-* "$here"/extras/agent/bin/* "$here"/extras/ai_tools/bin/* \
           "$here"/extras/sandbox/bin/* "$here"/extras/grow/aos-grow; do
  [ -f "$src" ] && [ -x "$src" ] || continue
  case "$src" in "$here"/impls/*/bin/*)   # 只裝現役的 impls（有 CMakeLists.txt 的）；改名前留下的舊 build 產物（aos-llm-send 之類）不裝
    [ -f "${src%/bin/*}/CMakeLists.txt" ] || continue ;;
  esac
  found=1
  link_one "$src"
done
[ $found = 1 ] || { echo "install.sh: CommandMissing no command found ($here does not look like proto8?)" >&2; exit 1; }
ls "$here"/impls/*/bin/* >/dev/null 2>&1 || { echo "note: no impls built (impls/*/bin is empty): build them first (wf/workflows/testing.md, proto8) and run again"; n_none=1; }

# 目的地裡指進這份 repo、目標已不在的連結：只報不刪
for l in "$dest"/*; do
  [ -L "$l" ] || continue
  t=$(readlink "$l")
  case "$t" in "$here"/*) [ -e "$t" ] || echo "broken $(basename "$l") -> $t (target is gone; rm $l if unwanted)" ;; esac
done

# 11-05 B 線：PATH 上排在前面的同名指令會蓋掉裝的這支
for src in "$dest"/*; do
  [ -L "$src" ] || continue
  case "$(readlink "$src")" in "$here"/*) ;; *) continue ;; esac
  name=$(basename "$src"); got=$(command -v "$name" 2>/dev/null) || continue
  [ "$got" = "$src" ] || [ "$(readlink -f "$got")" = "$(readlink -f "$src")" ] || echo "warning: $name on PATH resolves to $got first (not $src)"
done
case ":$PATH:" in *":$dest:"*) ;; *) echo "note: $dest is not on PATH: add export PATH=\"$dest:\$PATH\" to ~/.bashrc (this script does not)" ;; esac
verb=linked; [ $dry = 1 ] && verb="would link"
echo "done: $verb $n_new, already $n_same, skipped $n_skip (dest $dest)"
[ $n_skip = 0 ] && [ $n_none = 0 ]
