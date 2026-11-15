#!/bin/bash
# vendor.sh - fill ui/v2/node_modules from two projects already on this machine (no network; 03 §12.8 #8).
# pnpm --offline and npm --offline both fail here (no metadata / tarballs), so we copy (cp -rL) the packages we need.
# The source projects are only read. node_modules/ is not committed; this script and the versions below are.
#   vite 8.3.5, rolldown, postcss 8.5.x, @oxc-project, lightningcss  <- ~/repo/game_dev/mecha-srpg
#   react 19.2.4, react-dom 19.2.4, scheduler, tailwindcss 4.3.0, @tailwindcss/postcss 4.3.0,
#   typescript 5.9.3, @types/react 19.2.x, @types/react-dom, csstype     <- ~/code/web-template/frontend
set -euo pipefail
cd "$(dirname "$0")"
VITE_SRC=${VITE_SRC:-$HOME/repo/game_dev/mecha-srpg/node_modules}
WEB_SRC=${WEB_SRC:-$HOME/code/web-template/frontend/node_modules}
[ -d "$VITE_SRC/vite" ] || { echo "vendor.sh: no vite in $VITE_SRC" >&2; exit 1; }
[ -d "$WEB_SRC/react" ] || { echo "vendor.sh: no react in $WEB_SRC" >&2; exit 1; }
mkdir -p node_modules
# 1. the vite toolchain: every top-level package of mecha-srpg except its own app deps we do not need
for d in "$VITE_SRC"/*; do
  n=$(basename "$d")
  case $n in happy-dom|ws|whatwg-mimetype|buffer-image-size|entities|undici-types|typescript|playwright|playwright-core|@playwright|@types) continue;; esac
  if [[ $n == @* ]]; then
    for s in "$d"/*; do mkdir -p "node_modules/$n"; [ -e "node_modules/$n/$(basename "$s")" ] || cp -rL "$s" "node_modules/$n/"; done
  else
    [ -e "node_modules/$n" ] || cp -rL "$d" node_modules/
  fi
done
# 2. react + tailwind + typescript + types from the web template (pnpm layout: take each package and its deps)
copy_pnpm() {  # copy every package found under .pnpm/<glob>/node_modules/
  local pd d n s
  for pd in "$WEB_SRC"/.pnpm/$1; do
    [ -d "$pd/node_modules" ] || continue
    for d in "$pd"/node_modules/*; do
      n=$(basename "$d")
      if [[ $n == @* ]]; then
        for s in "$d"/*; do mkdir -p "node_modules/$n"; [ -e "node_modules/$n/$(basename "$s")" ] || cp -rL "$s" "node_modules/$n/"; done
      else
        [ -e "node_modules/$n" ] || cp -rL "$d" node_modules/
      fi
    done
  done
}
for g in 'react@19.2.4' 'react-dom@19.2.4*' 'scheduler@*' 'tailwindcss@4.3.0' '@tailwindcss+*' '@alloc+*' '@jridgewell+*' \
         'enhanced-resolve@*' 'jiti@*' 'magic-string@*' 'tapable@*' 'graceful-fs@*' 'detect-libc@*' \
         'typescript@5.9.3' '@types+react@19*' '@types+react-dom@19*' 'csstype@*'; do
  copy_pnpm "$g"
done
for p in vite rolldown postcss react react-dom tailwindcss @tailwindcss/postcss typescript @types/react; do
  [ -e "node_modules/$p/package.json" ] || { echo "vendor.sh: missing $p" >&2; exit 1; }
  printf '%-22s %s\n' "$p" "$(node -p "require('./node_modules/$p/package.json').version")"
done
