T=$(mktemp -d /tmp/astra8-core-XXXX)
export T PYTHONDONTWRITEBYTECODE=1
python3 -B - <<'PY'
import json, os, pathlib
p = pathlib.Path(os.environ["T"]) / "inst.json"
p.write_text(json.dumps({
    "arr": ["/bin/true"],
    "argv": [{"$ref": "", "$at": "/arr/" + "0" * 4301}]
}))
PY
PYTHONINTMAXSTRDIGITS=4300 \
  python3 -B proto7-2/bin/aos-exec "$T/inst.json"
printf 'rc=%s\n' "$?"
rm -rf "$T"
