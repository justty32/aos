#!/usr/bin/env bash
# install.sh [--dry-run] [目的地] - 把 aos 的指令 symlink 進一個 PATH 裡的資料夾（預設 ~/.local/bin），之後每個殼都找得到、不用 source env.sh。
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
# 不改 PATH、不寫殼的設定檔：目的地不在 PATH 上就印一句提醒。只在 Linux／WSL 的檔案系統上用（/mnt/c 底下每個檔都 +x，見 dev-env）。
set -u

dry=0
dest=""
for a in "$@"; do
  case "$a" in
    --dry-run) dry=1 ;;
    -h|--help) sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) echo "install.sh: ArgumentsBad 不認得的旗標 $a" >&2; exit 1 ;;
    *) if [ -n "$dest" ]; then echo "install.sh: ArgumentsBad 目的地只能一個" >&2; exit 1; fi; dest=$a ;;
  esac
done
[ -n "$dest" ] || dest="$HOME/.local/bin"

here=$(cd "$(dirname "$(readlink -f "$0")")" && pwd -P)   # proto8/
case "$here" in /mnt/*) echo "install.sh: 注意 repo 在 $here（Windows 磁碟），aos 在這裡跑會把每個檔當執行檔；請用 Linux 檔案系統的 clone" >&2 ;; esac

if [ ! -d "$dest" ]; then
  if [ $dry = 1 ]; then echo "建資料夾 $dest（dry-run，沒建）"; else mkdir -p "$dest" && echo "建資料夾 $dest"; fi
fi

n_new=0; n_same=0; n_skip=0; n_none=0
link_one() {   # $1＝repo 裡那支的絕對路徑
  local src=$1 name dst cur
  name=$(basename "$src"); dst="$dest/$name"
  if [ -L "$dst" ]; then
    cur=$(readlink "$dst")
    if [ "$cur" = "$src" ]; then echo "已裝 $name"; n_same=$((n_same+1)); return; fi
    echo "跳過 $name：$dst 已是連結、指向 $cur（不是這份 repo 的 $src；要換先自己 rm 再跑）"; n_skip=$((n_skip+1)); return
  fi
  if [ -e "$dst" ]; then
    echo "跳過 $name：$dst 已有別的檔（不蓋；要換先自己挪開再跑）"; n_skip=$((n_skip+1)); return
  fi
  if [ $dry = 1 ]; then echo "會裝 $name -> $src"; else ln -s "$src" "$dst" && echo "裝 $name -> $src"; fi
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
[ $found = 1 ] || { echo "install.sh: 一支都沒找到（$here 不像 proto8？）" >&2; exit 1; }
ls "$here"/impls/*/bin/* >/dev/null 2>&1 || { echo "注意 impls 一支都沒建（impls/*/bin 是空的）：先照 wf/workflows/testing.md「proto8」那行建好再跑一次"; n_none=1; }

# 目的地裡指進這份 repo、目標已不在的連結：只報不刪
for l in "$dest"/*; do
  [ -L "$l" ] || continue
  t=$(readlink "$l")
  case "$t" in "$here"/*) [ -e "$t" ] || echo "斷了 $(basename "$l") -> $t（那支已不在；不要了就 rm $l）" ;; esac
done

case ":$PATH:" in *":$dest:"*) ;; *) echo "注意 $dest 不在 PATH 上：在 ~/.bashrc 加一行 export PATH=\"$dest:\$PATH\"（本腳本不改）" ;; esac
verb=裝; [ $dry = 1 ] && verb=會裝
echo "完成：$verb $n_new 支、已裝 $n_same 支、跳過 $n_skip 支（目的地 $dest）"
[ $n_skip = 0 ] && [ $n_none = 0 ]
