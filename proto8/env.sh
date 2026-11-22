# aos environment of the home AOS_HOME points at: "source $AOS_HOME/env.sh" (bash or zsh) in every window, or a tree's thin env.sh does it for you; AOS_HOME is yours to set (once per machine), this file never sets it.
# Without AOS_HOME it stops with one line and changes nothing (no guessing from where this file sits; 11-17 L-7 C).
if [ -z "${AOS_HOME:-}" ]; then
  echo "env.sh: error: EnvBad AOS_HOME is not set (once per machine: export AOS_HOME=<the proto8 folder>, e.g. in ~/.bashrc)" >&2
  return 1 2>/dev/null || exit 1
fi
if [ ! -f "$AOS_HOME/install.py" ]; then
  echo "env.sh: error: EnvBad AOS_HOME=$AOS_HOME is not an aos home (no install.py there; it should be the proto8 folder of your aos clone)" >&2
  return 1 2>/dev/null || exit 1
fi
export AOS_HOME
# Sourced straight from another home (say a scratch copy) while AOS_HOME points elsewhere: AOS_HOME still wins, but say so.
_aos_here=$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd -P)
if [ -n "$_aos_here" ] && [ "$_aos_here" != "$(cd "$AOS_HOME" && pwd -P)" ]; then
  echo "env.sh: warning: AOS_HOME is $AOS_HOME, not $_aos_here where this env.sh is; PATH gets $AOS_HOME/bin (export AOS_HOME=$_aos_here first to use this one)" >&2
fi
unset _aos_here
unset CLAUDECODE CLAUDE_CODE_ENTRYPOINT CLAUDE_CODE_SSE_PORT
# Clear every AOS_* except AOS_HOME (an agent's shell carries AOS_STACK etc.; root would inherit them — 11-13 15:24 incident).
for _aos_v in $(env | grep -o '^AOS_[A-Za-z0-9_]*'); do [ "$_aos_v" = AOS_HOME ] || unset "$_aos_v"; done; unset _aos_v
# Put this home's commands first on PATH: bin/ holds everything install.py built (the C++ commands and the Python entries); nothing goes into ~/.local/bin.
# frontend/bin is the optional web page plugin (aos-frontend, and aos-user for the user zone), which install.py leaves alone; it goes on PATH only when that folder is there.
for _aos_d in "$AOS_HOME"/frontend/bin "$AOS_HOME"/bin; do
  if [ -d "$_aos_d" ]; then
    case ":$PATH:" in *":$_aos_d:"*) ;; *) PATH="$_aos_d:$PATH" ;; esac
  fi
done; unset _aos_d
export PATH
[ -x "$AOS_HOME/bin/aos-exec" ] || echo "env.sh: $AOS_HOME/bin/aos-exec not installed yet; run: python3 $AOS_HOME/install.py" >&2
