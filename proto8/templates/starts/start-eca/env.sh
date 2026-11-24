# This tree's env.sh: "cd <this tree> && source env.sh" (bash or zsh) in every window; it hands over to $AOS_HOME/env.sh, the real one, so it hardly ever goes stale.
if [ -z "${AOS_HOME:-}" ]; then
  echo "env.sh: error: EnvBad AOS_HOME is not set (once per machine: export AOS_HOME=<the proto8 folder>, e.g. in ~/.bashrc)" >&2
  return 1 2>/dev/null || exit 1
fi
if [ ! -f "$AOS_HOME/install.py" ] || [ ! -f "$AOS_HOME/env.sh" ]; then
  echo "env.sh: error: EnvBad AOS_HOME=$AOS_HOME is not an aos home (no install.py and env.sh there; it should be the proto8 folder of your aos clone)" >&2
  return 1 2>/dev/null || exit 1
fi
. "$AOS_HOME/env.sh" || { return 1 2>/dev/null || exit 1; }
# This tree's own additions go below (plain export lines; not AOS_*: those belong to aos, which sets them for each proc).
