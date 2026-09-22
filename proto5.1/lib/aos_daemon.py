"""管理 aos-run 的檔案請求迴圈；不替 kernel 排程。"""
import argparse
import fcntl
import json
import os
from pathlib import Path
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
    if not (p / "info.json").is_file():
        raise DaemonError("NotAHome", "%s 不是 daemon 家" % p)
    info = _read(p / "info.json")
    meta = info.get("_metainfo") if isinstance(info, dict) else None
    if not isinstance(meta, dict) or meta.get("_type") != "daemon":
        raise DaemonError("NotAHome", "%s 不是 daemon 家" % p)
    if type(meta.get("_version")) is not int or meta["_version"] != 1:
        raise DaemonError("UnsupportedVersion", "%s 的 _version 只認整數 1" % p)
    if not (p / "requests").is_dir() or not (p / "requests/done").is_dir():
        raise DaemonError("NotAHome", "%s 缺少 daemon 請求目錄" % p)
    return p


def _target(value):
    if not isinstance(value, str) or not value or "\0" in value or not value.endswith(".json"):
        raise DaemonError("FieldTypeMismatch", "target 必須是非空 .json 路徑")
    return os.path.abspath(value)


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
                or not {"pid", "target", "args", "state", "home"} <= entry.keys()
                or not os.path.isabs(key)
                or entry.get("target") != key or type(entry.get("pid")) is not int
                or entry["pid"] <= 0 or entry.get("state") not in ("running", "stopping")
                or not isinstance(entry.get("home"), str) or not os.path.isabs(entry["home"])):
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


def request(op, target=None, args=None, home=None, timeout=15, kill_tree=False):
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
    if op == "add":
        if type(kill_tree) is not bool:
            raise DaemonError("FieldTypeMismatch", "kill_tree 必須是布林")
        obj["kill_tree"] = kill_tree
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
                if not isinstance(response, dict) or type(response.get("ok")) is not bool:
                    raise DaemonError("FieldTypeMismatch", "%s 的回應格式錯誤" % done)
                if response["ok"]:
                    if "result" not in response:
                        raise DaemonError("FieldTypeMismatch", "%s 缺少 result" % done)
                    return response["result"]
                if not all(isinstance(response.get(k), str) for k in ("code", "msg")):
                    raise DaemonError("FieldTypeMismatch", "%s 的錯誤回應格式錯誤" % done)
                raise DaemonError(response["code"], response["msg"])
            time.sleep(POLL)
        raise DaemonError("ReadFailed", "等待 %s 的 done 超過 %g 秒；請求保留" % (name, timeout))
    except OSError as e:
        raise DaemonError("ReadFailed", str(e))


def _finish_request(path, obj, ok, result):
    """發布順序不可顛倒；重跑看見 done 就只收原单，不重做副作用。"""
    if ok:
        response = dict(obj) if isinstance(obj, dict) else {"request": obj}
        response.update(ok=True, result=result)
    else:
        response = {"ok": False, "code": result["code"], "msg": result["msg"]}
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

    def add(self, target, args, kill_tree=False):
        if target in self.jobs:
            raise DaemonError("AlreadyRunning", "%s 已登記" % target)
        if type(kill_tree) is not bool:
            raise DaemonError("FieldTypeMismatch", "kill_tree 必須是布林")
        runner_home = self.p / "runners" / ("%d-%s" % (time.time_ns(), secrets.token_hex(2)))
        runner_home.mkdir(parents=True)
        command = [sys.executable, RUN_CLI, target, *args, "--home", str(runner_home)]
        if kill_tree:
            command.append("--kill-tree")
        proc = subprocess.Popen(command, start_new_session=True, stdin=subprocess.DEVNULL,
                                env=dict(os.environ, AOS_DAEMON_HOME=str(self.p)),
                                stdout=self.log, stderr=self.log)
        entry = {"pid": proc.pid, "target": target, "args": args, "state": "running",
                 "home": str(runner_home)}
        self.jobs[target] = {"proc": proc, "entry": entry, "deadline": None, "escalated": False, "kill_tree": kill_tree}
        if self.stopping:
            self.stop_job(self.jobs[target])
        self.save()
        return entry.copy()

    def stop_job(self, job):
        if job["deadline"] is None:
            job["entry"]["state"] = "stopping"
            job["deadline"] = time.monotonic() + GRACE
            _signal(job["proc"], signal.SIGTERM)
            return True
        return False

    def stop(self):
        self.stopping = True
        changed = False
        for job in self.jobs.values():
            if self.stop_job(job):
                changed = True
        if changed:
            self.save()

    def reap(self):
        for key, job in list(self.jobs.items()):
            if job["proc"].poll() is None:
                if job["deadline"] is not None and time.monotonic() >= job["deadline"]:
                    if not job["kill_tree"] and not job["escalated"]:
                        _signal(job["proc"], signal.SIGTERM)
                        job["escalated"] = True
                        job["deadline"] = time.monotonic() + GRACE
                    else:
                        _signal(job["proc"], signal.SIGKILL)
                continue
            entry = job["entry"].copy()
            entry["state"] = "stopping"
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
                if not isinstance(obj, dict) or obj.get("op") not in ("add", "remove", "stop"):
                    raise DaemonError("FieldTypeMismatch", "%s 的 op 只認 add／remove／stop" % path)
                op = obj["op"]
                if op == "stop":
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
                        result = self.add(target, _args(obj.get("args", [])), obj.get("kill_tree", False))
                    else:
                        if target not in self.jobs:
                            raise DaemonError("NotRunning", "%s 沒在跑" % target)
                        if self.stop_job(self.jobs[target]):
                            self.save()
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
            if not (p / "info.json").exists():
                _write(p / "info.json", {"_metainfo": {"_type": "daemon", "_version": 1}})
            _check_home(p)
            for path in (p / "runners").glob("*/run.json"):
                status = _read(path)
                pid = status.get("pid") if isinstance(status, dict) else None
                if type(pid) is not int or pid <= 0:
                    raise DaemonError("FieldTypeMismatch", "%s 的 pid 必須是正整數" % path)
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    continue
                except PermissionError:
                    pass
                raise DaemonError("AlreadyRunning", "%s 的 runner %d 還在跑" % (path, pid))
            with open(p / "daemon.log", "ab", buffering=0) as log:
                daemon = _Daemon(p, log)
                old = {sig: signal.signal(sig, lambda *_: daemon.stop()) for sig in (signal.SIGTERM, signal.SIGINT)}
                try:
                    (p / "daemon.pid").write_text(str(os.getpid()) + "\n", encoding="ascii")
                    daemon.save()
                    while True:
                        daemon.reap()
                        daemon.requests()
                        if daemon.stopping and not daemon.jobs:
                            break
                        time.sleep(POLL)
                finally:
                    try:
                        daemon.stop()
                    except OSError:
                        pass
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
    add.add_argument("--kill-tree", action="store_true")
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
                         args if a.op == "add" else None, home=a.home,
                         kill_tree=getattr(a, "kill_tree", False))
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
        return 0
    except (DaemonError, OSError) as e:
        return _error(e if isinstance(e, DaemonError) else DaemonError("ReadFailed", str(e)))


if __name__ == "__main__":
    sys.exit(main())
