# aos environment: run "source <proto8>/env.sh" (bash or zsh) in every window before using aos; AOS_HOME becomes this proto8 folder.
unset CLAUDECODE CLAUDE_CODE_ENTRYPOINT CLAUDE_CODE_SSE_PORT
# Clear every AOS_* (an agent's shell carries AOS_STACK etc.; root would inherit them — 11-13 15:24 incident).
for _aos_v in $(env | grep -o '^AOS_[A-Za-z0-9_]*'); do unset "$_aos_v"; done; unset _aos_v
export AOS_HOME=$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)
# Put this home's commands first on PATH (path rule one, 11-17: aos programs live only in AOS_HOME; nothing goes into ~/.local/bin).
# bin/ holds what install.py built: the C++ commands and the Python commands' entries (11-18 S5: cmd/ is gone).
# frontend/bin (aos-frontend, the optional web page) goes on PATH too; it is harmless when unused.
for _aos_d in "$AOS_HOME"/frontend/ "$AOS_HOME"/; do
  if [ -d "${_aos_d}bin" ]; then
    case ":$PATH:" in *":${_aos_d}bin:"*) ;; *) PATH="${_aos_d}bin:$PATH" ;; esac
  fi
done; unset _aos_d
export PATH
[ -x "$AOS_HOME/bin/aos-exec" ] || echo "env.sh: $AOS_HOME/bin/aos-exec not installed yet; run: python3 $AOS_HOME/install.py" >&2
