T=$(mktemp -d /tmp/astra8-core-XXXX)
export T PYTHONDONTWRITEBYTECODE=1
python3 -B - <<'PY'
import json, os, pathlib, subprocess, sys, time

t = pathlib.Path(os.environ["T"])
root = t / "root"
(root / ".aosd").mkdir(parents=True)
(root / "n/.aos").mkdir(parents=True)

def put(path, obj):
    path.write_text(json.dumps(obj))

def read(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}

put(root / ".aosd/nodes.json", {"nodes": {"n": {}}})
put(root / ".aosd/paused.json",
    {"paused": {}, "steps": {"n": {"k": 2}}})
put(root / "n/.aos/tasks.json", {"tasks": []})
put(root / "n/.aos/timeline.json", {"interval_ms": 50})

hook = t / "hook.py"
hook.write_text("""
import errno, os, signal
writes = 0
closed = 0
def inject(op, path):
    global writes
    if op == "write" and os.path.basename(path) == "paused.json":
        writes += 1
        if writes > 1:  # 啟動時保存成功；之後持續 EIO
            raise OSError(errno.EIO, "astra8 paused write")
def test_point(name):
    global closed
    if name == "round-closed-before-steps":
        closed += 1
        if closed == 2:
            os.kill(os.getpid(), signal.SIGKILL)
""")

cmd = [sys.executable, "-B", "proto7-2/bin/aos7-daemon", str(root)]
env = dict(os.environ)
env.pop("AOS7_TEST_HOOKS", None)
processes = []
try:
    with (t / "daemon.log").open("w") as log:
        first = subprocess.Popen(
            cmd, env=dict(env, AOS7_TEST_HOOKS=str(hook)),
            stdout=log, stderr=log)
        processes.append(first)
        try:
            first.wait(timeout=8)
        except subprocess.TimeoutExpired:
            first.kill()
            first.wait()
        print("first_round =", read(root / "n/.aos/round.json").get("round"))
        print("saved =", read(root / ".aosd/paused.json"))

        second = subprocess.Popen(cmd, env=env, stdout=log, stderr=log)
        processes.append(second)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            row = read(root / ".aosd/status.json").get("nodes", {}).get("n", {})
            if row.get("phase") == "paused":
                break
            if second.poll() is not None:
                raise RuntimeError("second daemon exited; inspect daemon.log")
            time.sleep(.05)
        else:
            raise RuntimeError("did not pause")
        print("final_round =", read(root / "n/.aos/round.json").get("round"))
finally:
    for p in processes:
        if p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()
PY
rm -rf "$T"
