# aos-home environment: run "cd ~/aos-home && source env.sh" in every window first.
unset CLAUDECODE CLAUDE_CODE_ENTRYPOINT CLAUDE_CODE_SSE_PORT
# Clear every AOS_* (an agent's shell carries AOS_STACK etc.; root would inherit them — 11-13 15:24 incident).
for _aos_v in $(env | grep -o '^AOS_[A-Za-z0-9_]*'); do unset "$_aos_v"; done; unset _aos_v
export AOS_HOME=$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)
command -v aos-exec >/dev/null || echo "env.sh: aos-exec not on PATH; run ~/repo/aos/proto8/install.sh once" >&2
