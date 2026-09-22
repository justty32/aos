"""管理 aos-run 的檔案請求迴圈；不替 kernel 排程。"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import secrets
import signal
import subprocess
import sys
import tempfile
import time

__all__ = ["DaemonError", "home", "read_state", "request", "serve", "main", "ctl_main"]
GRACE = 5.0
POLL = 0.02
RUN_CLI = str(Path(__file__).resolve().parents[1] / "cli" / "aos-run")


class DaemonError(Exception):
    def __init__(self, code, msg):
        self.code, self.msg = code, msg
        super().__init__("%s: %s" % (code, msg))


def home(path=None):
    return os.path.realpath(os.path.expanduser(os.fspath(path) if path is not None else
                            os.environ.get("AOS_DAEMON_HOME", "~/.aos-daemon")))


def _read(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (UnicodeError, ValueError) as e:
        raise DaemonError("JsonSyntax", "%s：%s" % (path, e))
    except OSError as e:
        raise DaemonError("ReadFailed", "%s：%s" % (path, e))


def _write(path, obj):
    path = Path(path)
    fd, tmp = tempfile.mkstemp(prefix="." + path.name + "-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _check_home(path):
    p = Path(path)
    if not p.is_dir() or not (p / "requests").is_dir() or not (p / "requests/done").is_dir():
        raise DaemonError("NotAHome", "%s 不是 daemon 家" % p)
    return p


def _target(value):
    if not isinstance(value, str) or not value or "\0" in value or not value.endswith(".json"):
        raise DaemonError("FieldTypeMismatch", "target 必須是非空 .json 路徑")
    return os.path.realpath(value)


def _args(value):
    if not isinstance(value, list) or any(not isinstance(x, str) for x in value) or len(value) % 2:
        raise DaemonError("FieldTypeMismatch", "args 必須是 aos-run 旗標與整數值的字串陣列")
    for flag, number in zip(value[::2], value[1::2]):
        if flag not in ("--interval-ms", "--timeout-ms", "--max-runs", "--stop-exit"):
            raise DaemonError("FieldTypeMismatch", "不允許的 aos-run 旗標：%s" % flag)
        try:
            n = int(number)
        except ValueError:
            raise DaemonError("FieldTypeMismatch", "%s 必須帶整數" % flag)
        if n < 0 or (flag == "--stop-exit" and n > 255):
            raise DaemonError("FieldTypeMismatch", "%s 的數值超出範圍" % flag)
    return value


def read_state(path=None):
    """讀最後快照；正常停止後 pid=0、runs={}，不把快照當互斥鎖。"""
    p = _check_home(home(path))
    obj = _read(p / "state.json")
    if (not isinstance(obj, dict) or type(obj.get("pid")) is not int or obj["pid"] < 0
            or not isinstance(obj.get("runs"), dict)):
        raise DaemonError("FieldTypeMismatch", "%s/state.json 的 pid／runs 壞了" % p)
    for key, entry in obj["runs"].items():
        if (not isinstance(entry, dict)
                or not {"pid", "target", "args", "state", "ready", "running", "runs", "last_exit", "last_kind"} <= entry.keys()
                or not os.path.isabs(key)
                or entry.get("target") != key or type(entry.get("pid")) is not int
                or entry["pid"] <= 0 or entry.get("state") not in ("running", "stopping")
                or any(type(entry.get(k)) is not bool for k in ("ready", "running"))
                or type(entry.get("runs")) is not int or entry["runs"] < 0
                or (entry.get("last_exit") is not None and type(entry["last_exit"]) is not int)
                or entry.get("last_kind") not in (None, "child", "aos", "usage")):
            raise DaemonError("FieldTypeMismatch", "%s/state.json 的 entry %s 壞了" % (p, key))
        _args(entry.get("args"))
    return obj


def _active(p):
    try:
        with open(p / ".daemon.lock", "rb") as f:
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return True
    except FileNotFoundError:
        pass
    return False


def request(op, target=None, args=None, home=None, timeout=10):
    """送請求、等同名 done；remove 回傳收尾後 entry，stop 在所有 runner 已收屍後回覆。"""
    p = _check_home(globals()["home"](home))
    if op == "ls":
        return read_state(p)
    try:
        active = _active(p)
    except OSError as e:
        raise DaemonError("ReadFailed", str(e))
    if not active:
        raise DaemonError("NotRunning", "%s 的 daemon 沒在跑" % p)
    obj = {"op": op}
    if target is not None:
        obj["target"] = _target(os.fspath(target))
    if args is not None:
        obj["args"] = _args(args)
    name = "%d-%d-%s.json" % (time.time_ns(), os.getpid(), secrets.token_hex(2))
    path = p / "requests" / name
    try:
        _write(path, obj)
        until = time.monotonic() + timeout
        done = p / "requests/done" / name
        while time.monotonic() < until:
            if done.exists():
                response = _read(done)
                if not isinstance(response, dict) or type(response.get("ok")) is not bool or "result" not in response:
                    raise DaemonError("FieldTypeMismatch", "%s 的回應格式錯誤" % done)
                if response["ok"]:
                    return response["result"]
                result = response["result"]
                if not isinstance(result, dict) or not all(isinstance(result.get(k), str) for k in ("code", "msg")):
                    raise DaemonError("FieldTypeMismatch", "%s 的錯誤回應格式錯誤" % done)
                raise DaemonError(result["code"], result["msg"])
            time.sleep(POLL)
        raise DaemonError("ReadFailed", "等待 %s 的 done 超過 %g 秒；請求保留" % (name, timeout))
    except OSError as e:
        raise DaemonError("ReadFailed", str(e))


def _finish_request(path, obj, ok, result):
    """發布順序不可顛倒；重跑看見 done 就只收原单，不重做副作用。"""
    response = dict(obj) if isinstance(obj, dict) else {"request": obj}
    response.update(ok=ok, result=result)
    _write(path.parent / "done" / path.name, response)
    path.unlink()


def _signal(proc, sig):
    try:
        os.killpg(proc.pid, sig)
    except ProcessLookupError:
        pass


class _Daemon:
    def __init__(self, p, log):
        self.p, self.log = p, log
        self.jobs, self.pending = {}, {}
        self.stopping = False

    def snapshot(self, pid=None):
        return {"pid": os.getpid() if pid is None else pid,
                "runs": {key: job["entry"].copy() for key, job in self.jobs.items()}}

    def save(self, pid=None):
        _write(self.p / "state.json", self.snapshot(pid))

    def add(self, target, args):
        if target in self.jobs:
            raise DaemonError("AlreadyRunning", "%s 已登記" % target)
        rd, wr = os.pipe()
        try:
            proc = subprocess.Popen([sys.executable, RUN_CLI, target, *args, "--status-fd", str(wr)],
                                    pass_fds=(wr,), start_new_session=True, stdin=subprocess.DEVNULL,
                                    env=dict(os.environ, AOS_DAEMON_HOME=str(self.p)),
                                    stdout=self.log, stderr=self.log)
        except BaseException:
            os.close(rd)
            raise
        finally:
            os.close(wr)
        os.set_blocking(rd, False)
        entry = {"pid": proc.pid, "target": target, "args": args, "state": "running",
                 "ready": False, "running": False, "runs": 0, "last_exit": None, "last_kind": None}
        self.jobs[target] = {"proc": proc, "fd": rd, "buffer": b"", "entry": entry, "deadline": None}
        if self.stopping:
            self.stop_job(self.jobs[target])
        self.save()
        return entry.copy()

    def stop_job(self, job):
        if job["deadline"] is None:
            job["entry"]["state"] = "stopping"
            job["deadline"] = time.monotonic() + GRACE
            _signal(job["proc"], signal.SIGTERM)

    def stop(self):
        self.stopping = True
        for job in self.jobs.values():
            self.stop_job(job)

    def events(self, job):
        while True:
            try:
                data = os.read(job["fd"], 65536)
            except BlockingIOError:
                break
            if not data:
                break
            job["buffer"] += data
        lines = job["buffer"].split(b"\n")
        job["buffer"] = lines.pop()
        e = job["entry"]
        for raw in lines:
            line = raw.decode("utf-8", "replace")
            if line == "ready":
                e["ready"] = True
            elif re.fullmatch(r"start #\d+", line):
                e["running"] = True
            elif (m := re.fullmatch(r"done #(\d+) exit=(\d+) kind=(child|aos|usage)", line)):
                e.update(running=False, runs=int(m[1]), last_exit=int(m[2]), last_kind=m[3])
            elif line.startswith("stop "):
                e.update(running=False, state="stopping")

    def reap(self):
        for key, job in list(self.jobs.items()):
            self.events(job)
            if job["deadline"] is not None and time.monotonic() >= job["deadline"]:
                _signal(job["proc"], signal.SIGKILL)
            if job["proc"].poll() is None:
                continue
            self.events(job)
            os.close(job["fd"])
            entry = job["entry"].copy()
            entry.update(running=False, state="stopping")
            del self.jobs[key]
            self.save()
            for path, (obj, target) in list(self.pending.items()):
                if target == key:
                    _finish_request(path, obj, True, entry)
                    del self.pending[path]

    def requests(self):
        for path in sorted((self.p / "requests").glob("*.json")):
            if path in self.pending or not path.is_file():
                continue
            if (path.parent / "done" / path.name).exists():
                path.unlink()
                continue
            obj = None
            try:
                obj = _read(path)
                if not isinstance(obj, dict) or obj.get("op") not in ("add", "remove", "ls", "stop"):
                    raise DaemonError("FieldTypeMismatch", "%s 的 op 只認 add／remove／ls／stop" % path)
                op = obj["op"]
                if op == "ls":
                    result = self.snapshot()
                elif op == "stop":
                    self.stop()
                    self.pending[path] = (obj, None)
                    continue
                elif self.stopping:
                    raise DaemonError("NotRunning", "daemon 正在停止")
                else:
                    target = _target(obj.get("target"))
                    if not os.path.isabs(obj["target"]):
                        raise DaemonError("FieldTypeMismatch", "請求 target 必須是絕對路徑")
                    if op == "add":
                        result = self.add(target, _args(obj.get("args", [])))
                    else:
                        if target not in self.jobs:
                            raise DaemonError("NotRunning", "%s 沒在跑" % target)
                        self.stop_job(self.jobs[target])
                        self.pending[path] = (obj, target)
                        continue
                _finish_request(path, obj, True, result)
            except DaemonError as e:
                _finish_request(path, obj, False, {"code": e.code, "msg": e.msg})


def serve(path=None):
    p = Path(home(path))
    if p.exists() and not p.is_dir():
        raise DaemonError("NotAHome", "%s 不是資料夾" % p)
    try:
        (p / "requests/done").mkdir(parents=True, exist_ok=True)
        with open(p / ".daemon.lock", "a+") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise DaemonError("AlreadyRunning", "%s 的 daemon 已在跑" % p)
            with open(p / "daemon.log", "ab", buffering=0) as log:
                daemon = _Daemon(p, log)
                old = {sig: signal.signal(sig, lambda *_: daemon.stop()) for sig in (signal.SIGTERM, signal.SIGINT)}
                try:
                    (p / "daemon.pid").write_text(str(os.getpid()) + "\n", encoding="ascii")
                    daemon.save()
                    while True:
                        daemon.reap()
                        daemon.requests()
                        daemon.save()
                        if daemon.stopping and not daemon.jobs:
                            break
                        time.sleep(POLL)
                finally:
                    daemon.stop()
                    while daemon.jobs:
                        try:
                            daemon.reap()
                        except OSError:
                            # reap 已先收屍／移除 entry；磁碟壞了也要繼續收其他 runner。
                            pass
                        time.sleep(POLL)
                    try:
                        daemon.save(pid=0)
                        (p / "daemon.pid").unlink(missing_ok=True)
                        for request_path, (obj, _) in daemon.pending.items():
                            _finish_request(request_path, obj, True, {"stopped": True})
                    finally:
                        for sig, handler in old.items():
                            signal.signal(sig, handler)
        return 0
    except OSError as e:
        raise DaemonError("ReadFailed", str(e))


def _error(e):
    sys.stderr.write("aos-daemon: %s\n" % " ".join(str(e).split()))
    return 1


def main(argv=None):
    ap = argparse.ArgumentParser(prog="aos-daemon", description="前景管理 aos-run")
    ap.add_argument("--home")
    a = ap.parse_args(argv)
    try:
        return serve(a.home)
    except DaemonError as e:
        return _error(e)


def ctl_main(argv=None):
    ap = argparse.ArgumentParser(prog="aos-daemon-ctl", description="交件或直接讀 daemon 狀態")
    ap.add_argument("--home")
    sub = ap.add_subparsers(dest="op", required=True)
    add = sub.add_parser("add")
    add.add_argument("target")
    for flag in ("interval-ms", "timeout-ms", "max-runs"):
        add.add_argument("--" + flag, type=int)
    add.add_argument("--stop-exit", type=int, action="append", default=[])
    rm = sub.add_parser("rm")
    rm.add_argument("target")
    sub.add_parser("ls")
    sub.add_parser("stop")
    a = ap.parse_args(argv)
    args = []
    if a.op == "add":
        for flag in ("interval-ms", "timeout-ms", "max-runs"):
            val = getattr(a, flag.replace("-", "_"))
            if val is not None:
                args += ["--" + flag, str(val)]
        for val in a.stop_exit:
            args += ["--stop-exit", str(val)]
        try:
            _args(args)
        except DaemonError as e:
            ap.error(e.msg)
    try:
        result = request("remove" if a.op == "rm" else a.op, getattr(a, "target", None),
                         args if a.op == "add" else None, home=a.home)
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
        return 0
    except (DaemonError, OSError) as e:
        return _error(e if isinstance(e, DaemonError) else DaemonError("ReadFailed", str(e)))


if __name__ == "__main__":
    sys.exit(main())
