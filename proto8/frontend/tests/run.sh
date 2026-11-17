#!/bin/bash
# run.sh - run the aos-frontend tests with every AOS_* variable unset (wf aos-teams/06 hard rule 2); temp dirs only.
if [ -z "$BASH_VERSION" ]; then echo "run.sh: not bash" >&2; exit 1; fi
for v in $(compgen -e | grep '^AOS_'); do unset "$v"; done
if compgen -e | grep -q '^AOS_'; then echo "run.sh: AOS_* still set" >&2; exit 1; fi
export PYTHONDONTWRITEBYTECODE=1
cd "$(dirname "$0")" || exit 1
if [ $# -eq 0 ]; then set -- test_phase1 test_delivery test_v2 test_compact_quiet test_slash; fi
exec python3 -m unittest -v "$@"
