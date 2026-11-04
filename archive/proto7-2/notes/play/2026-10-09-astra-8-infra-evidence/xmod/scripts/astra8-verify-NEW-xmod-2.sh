T=$(mktemp -d /tmp/astra8-xmod-compact-XXXX)
export T
PYTHONDONTWRITEBYTECODE=1 python3 -B - <<'PY'
import json, os, subprocess, sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path("proto7-2/modules/compact").resolve()))
import aos7_compact as c

node = Path(os.environ["T"])
(node / "notes").mkdir()
journal = node / "notes/journal.jsonl"
original = "".join(json.dumps({"text": f"已完成工作 {i}"}) + "\n"
                   for i in range(10))
journal.write_text(original)
(node / "compact.json").write_text(json.dumps({
    "files": ["notes/journal.jsonl"], "keep_recent": 1,
    "llm": {"gateway": "fake", "reserve": 1}
}))

def delivered(argv, **kwargs):
    receipt = {"outcome": "answered", "billing": "overrun",
               "text": "十件工作的完整摘要", "used": 2, "overrun": 1}
    body = json.dumps(receipt)
    Path(argv[argv.index("--out") + 1]).write_text(body)
    return subprocess.CompletedProcess(argv, 4, body, "")

with patch.object(c.subprocess, "run", side_effect=delivered):
    for attempt in (1, 2):
        rc = c.main(["now", str(node), "--force"])
        print("attempt", attempt, "rc", rc,
              "pending", (node / "compact/pending.json").exists(),
              "unchanged", journal.read_text() == original)
PY
rm -rf "$T"
