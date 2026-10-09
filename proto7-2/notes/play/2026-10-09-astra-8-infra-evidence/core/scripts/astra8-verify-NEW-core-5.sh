T=$(mktemp -d /tmp/astra8-core-XXXX)
export T PYTHONDONTWRITEBYTECODE=1
python3 -B - <<'PY'
import json, os, pathlib, subprocess, sys
events = pathlib.Path(os.environ["T"]) / "events"
p = subprocess.run([
    sys.executable, "-B", "proto7-2/modules/events/aos7-events",
    "pub", "--events", str(events), "--create", "--node", "n",
    "--kind", "big", "--event-id", "big-1",
    "--payload", json.dumps("x" * 65536)
], capture_output=True, text=True)
print("rc =", p.returncode)
print(p.stdout.strip())
print(p.stderr.strip())
print("files =", sorted(x.name for x in events.iterdir())
      if events.exists() else [])
PY
rm -rf "$T"
