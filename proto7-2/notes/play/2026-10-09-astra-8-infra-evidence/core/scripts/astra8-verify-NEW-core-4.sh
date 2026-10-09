T=$(mktemp -d /tmp/astra8-core-XXXX)
export T PYTHONDONTWRITEBYTECODE=1
python3 -B proto7-2/modules/events/aos7-events pub \
  --events "$T/events" --create --node n \
  --kind hello --event-id e1 --payload '{}'

python3 -B - <<'PY'
import errno, os, sys
from unittest.mock import patch
sys.path[:0] = ["proto7-2/modules/events", "proto7-2/lib"]
import aos7_events_read as reader

events = os.path.join(os.environ["T"], "events")
original = open
def fault(path, *args, **kwargs):
    if os.fspath(path) == os.path.join(events, "obs.active.jsonl"):
        raise OSError(errno.EIO, "astra8 read failure")
    return original(path, *args, **kwargs)

with patch("builtins.open", fault):
    sys.exit(reader.main(["--events", events]))
PY
printf 'read rc=%s\n' "$?"
rm -rf "$T"
