"""Unprivileged disposable canary probe; leaves its scratch directory for review.

Only the compiled child sets NNP/Landlock. No existing user files are tested.
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile

if os.getuid() == 0:
    raise SystemExit("Do not run as root")
source = Path(__file__).resolve().parent / "landlock-canary.c"
scratch = Path(tempfile.mkdtemp(prefix="aos-landlock-probe-"))
allowed = scratch / "allowed"
denied = scratch / "denied"
allowed.mkdir()
denied.mkdir()
for directory in (allowed, denied):
    (directory / "canary").write_text("self-created canary\n")
binary = scratch / "probe"
subprocess.run(["gcc", "-Wall", "-Wextra", "-O2", str(source), "-o", str(binary)], check=True)
result = subprocess.run([str(binary), str(allowed), str(allowed / "canary"),
                         str(denied / "canary")], capture_output=True, text=True, timeout=10)
# The unrestricted runner must still read both files after the child exits.
runner_reads = all((directory / "canary").read_text().startswith("self-created")
                   for directory in (allowed, denied))
assert (denied / "canary").read_text() == "self-created canary\n"
print(json.dumps({"scratch": str(scratch), "uid": os.getuid(),
                  "kernel": os.uname().release, "returncode": result.returncode,
                  "stdout": result.stdout, "stderr": result.stderr,
                  "unrestricted_runner_reads_both": runner_reads}, indent=2))
raise SystemExit(result.returncode or (0 if runner_reads else 1))
