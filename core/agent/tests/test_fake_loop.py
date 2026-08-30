#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
from pathlib import Path


loop = Path(__file__).with_name("fake_loop.py")
with tempfile.TemporaryDirectory() as temp:
    world = Path(temp)
    inbox = world / ".aos" / "inbox"
    inbox.mkdir(parents=True)
    commands = {
        "echo.json": {"id": "echo", "argv": ["sh", "-lc", "echo hi; echo err >&2"]},
        "fail.json": {"id": "fail", "argv": ["sh", "-lc", "exit 3"]},
    }
    for name, command in commands.items():
        path = inbox / name
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(command), encoding="utf-8")
        tmp.replace(path)

    subprocess.run([sys.executable, str(loop), str(world)], check=True)
    out = world / ".aos" / "batch" / "1" / "out"
    echo = json.loads((out / "echo.json").read_text(encoding="utf-8"))
    fail = json.loads((out / "fail.json").read_text(encoding="utf-8"))
    assert echo["stdout"] == "hi\n"
    assert echo["stderr"] == "err\n"
    assert echo["exit"] == 0 and echo["signal"] is None
    assert fail["exit"] == 3 and fail["signal"] is None
    assert (world / ".aos" / "turn").read_text(encoding="utf-8").strip() == "2"
    assert (world / ".aos" / "state.json").is_file()

    subprocess.run([sys.executable, str(loop), str(world)], check=True)
    assert not (world / ".aos" / "batch" / "2").exists()
    assert (world / ".aos" / "turn").read_text(encoding="utf-8").strip() == "3"
