"""所有 cpu 的父行程：daemon.md §1～§6 的握手、孩子表、重拉與停機。

工作 request 使用 aos_home 的信封與對帳；目標的讀驗與 fork 交給
aos_exec.spawn_target，daemon 只在孩子表寫好後送 go。
"""
import argparse
import contextlib
import fcntl
import io
import json
import os
from pathlib import Path
import signal
import sys
import time

import aos_client
import aos_exec
import aos_home


class DaemonError(aos_home.HomeError):
    def __init__(self, code, msg, rpc_code=-32000, position=None):
        super().__init__(code, msg)
        self.rpc_code, self.position = rpc_code, position


def daemon_home(value=None):
    return os.path.abspath(os.path.expanduser(value or os.environ.get("AOS_DAEMON_HOME", "~/.aos-daemon")))


def is_alive(home):
    """共享 flock 只探測獨占主人；state 裡的 pid 不作生死判斷。"""
    try:
        fd = os.open(os.path.join(home, ".daemon.lock"), os.O_RDONLY | os.O_CLOEXEC)
    except FileNotFoundError:
        return False
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    finally:
        os.close(fd)


def read_state(home):
    return aos_home.read_state(home, {"pid": 0, "stopping": False, "current": None, "children": {}})


def _signal_pid(pid, sig, group=False):
    try:
        (os.killpg if group else os.kill)(pid, sig)
    except ProcessLookupError:
        pass


def _pid_exists(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _previous_children(state, info):
    """接手沒有 pipe 的上一任孩子：TERM、等兩段、KILL、等 pid 消失。"""
    pids = {child["pid"] for child in state.get("children", {}).values()
            if type(child.get("pid")) is int and child["pid"] > 0}
    pids = {pid for pid in pids if _pid_exists(pid)}
    for pid in pids:
        _signal_pid(pid, signal.SIGTERM)
    deadline = time.monotonic() + (info["stop_wait_ms"] + info["kill_wait_ms"]) / 1000
    killed = False
    while pids:
        pids = {pid for pid in pids if _pid_exists(pid)}
        if pids and not killed and time.monotonic() >= deadline:
            for pid in pids:
                _signal_pid(pid, signal.SIGKILL, group=True)
            killed = True
        if pids:
            time.sleep(info["poll_ms"] / 1000)


class Daemon:
    """一個活著的主人；執行中期限只放記憶體，state 只放持久身分。"""

    def __init__(self, home, info, state=None):
        self.home, self.info = Path(home), info
        self.state = state if state is not None else {
            "pid": os.getpid(), "stopping": False, "current": None, "children": {}}
        self.procs = {}
        self.stages = {}                     # name -> (stop / term / kill, deadline)
        self.restarts = {}
        self.pending = {}                    # 非阻塞寫暫時塞住的控制行
        self.stop_requested = False

    @property
    def children(self):
        return self.state["children"]

    def save(self):
        aos_home.write_state(self.home, self.state)

    def _params(self, params, spawning=False):
        def bad(key, msg):
            raise DaemonError("FieldTypeMismatch", msg, -32602, ["params", key])
        if not isinstance(params, dict):
            raise DaemonError("FieldTypeMismatch", "params 必須是物件", -32602, ["params"])
        name = params.get("name")
        if not isinstance(name, str) or name in ("", ".", "..") or "/" in name or "\0" in name:
            bad("name", "name 必須是合法單一檔名")
        if not spawning:
            return name
        target, dir_target, restart = params.get("target"), params.get("dir_target", ".aos/inst.json"), params.get("restart", False)
        if not isinstance(target, str) or "\0" in target or not os.path.isabs(target):
            bad("target", "target 必須是絕對路徑")
        if not isinstance(dir_target, str) or "\0" in dir_target:
            bad("dir_target", "dir_target 必須是字串")
        if type(restart) is not bool:
            bad("restart", "restart 必須是布林")
        return name, target, dir_target, restart

    def _term(self, name):
        _signal_pid(self.children[name]["pid"], signal.SIGTERM)
        self.stages[name] = ("term", time.monotonic() + self.info["kill_wait_ms"] / 1000)
        self.pending.pop(name, None)

    def _send(self, name, method):
        data = (json.dumps({"jsonrpc": "2.0", "method": method}) + "\n").encode()
        self.pending[name] = data
        self._flush(name)

    def _flush(self, name):
        try:
            os.write(self.procs[name].process.stdin.fileno(), self.pending[name])
        except BlockingIOError:
            return
        except BrokenPipeError:
            self._term(name)                 # EPIPE 不等於死亡，直接升一階
        else:
            self.pending.pop(name, None)

    def _launch(self, name, target, dir_target, restart, previous=None):
        try:
            handle = aos_exec.spawn_target(target, dir_target=dir_target)
        except aos_exec.SpawnError as exc:
            if exc.code == "Usage":
                raise DaemonError("Usage", exc.msg, -32602, ["params", "target"]) from exc
            raise DaemonError("SpawnFailed", exc.msg) from exc
        self.procs[name] = handle            # save 失敗時 finally 也能關 pipe，孩子不會收到 go
        self.children[name] = {"target": target, "dir_target": dir_target, "restart": restart,
            "pid": handle.process.pid, "alive": True, "state": "running",
            "exits": previous["exits"] if previous else 0,
            "last_exit": previous["last_exit"] if previous else None, "since": time.time()}
        self.restarts.pop(name, None)
        self.save()                         # fork → 寫孩子表 → go
        self._send(name, "go")
        return {"pid": handle.process.pid}

    def spawn(self, params):
        name, target, dir_target, restart = self._params(params, True)
        if self.state["stopping"]:
            raise DaemonError("Stopping", "daemon 正在停機")
        child = self.children.get(name)
        if child is not None:
            if (child["target"], child["dir_target"]) != (target, dir_target):
                raise DaemonError("NameTaken", "名字已由另一個目標使用：%s" % name)
            if child["state"] == "killing":
                raise DaemonError("Killing", "孩子正在停止：%s" % name)
            if child["state"] == "running":
                if child["restart"] != restart:
                    child["restart"] = restart
                    self.save()
                return {"pid": child["pid"]}
        return self._launch(name, target, dir_target, restart, child)

    def _start_stop(self, name):
        self.children[name]["state"] = "killing"
        self.save()
        self.stages[name] = ("stop", time.monotonic() + self.info["stop_wait_ms"] / 1000)
        self._send(name, "stop")

    def kill(self, params):
        name = self._params(params)
        child = self.children.get(name)
        if child is None:
            raise DaemonError("NotFound", "沒有這個孩子：%s" % name)
        result = {"pid": child["pid"]}
        if child["state"] == "dead":
            del self.children[name]
            self.restarts.pop(name, None)
            self.save()
        elif child["state"] == "running":
            self._start_stop(name)
        return result

    def request_stop(self):
        if self.state["stopping"]:
            return
        self.state["stopping"] = True
        self.save()
        for name in list(self.children):
            self.kill({"name": name})

    def process_request(self, name):
        path = self.home / "requests" / name
        env = aos_home.read_request(path)
        self.state["current"] = {"name": name, "id": env.id, "notify": env.notify}
        self.save()
        response = env.error
        if response is None:
            try:
                if env.method == "spawn":
                    result = self.spawn(env.params)
                elif env.method == "kill":
                    result = self.kill(env.params)
                else:
                    raise DaemonError("MethodNotFound", "不認得 method：%s" % env.method, -32601)
                response = aos_home.result_response(env.id, result)
            except DaemonError as exc:
                data = None if exc.rpc_code == -32601 else {"code": exc.code}
                if exc.position is not None:
                    data["position"] = exc.position
                response = aos_home.error_response(env.id, exc.rpc_code, exc.msg, data)
        if not env.notify:
            aos_home.write_json(self.home / "responses" / name, response)
        path.unlink()
        self.state["current"] = None
        self.save()

    def reap(self):
        for name, handle in list(self.procs.items()):
            raw_code = handle.process.poll()
            if raw_code is None:
                continue
            code = raw_code if raw_code >= 0 else 128 - raw_code
            diagnostic = io.StringIO()
            with contextlib.redirect_stderr(diagnostic):
                _, kind = handle.finish(code)
            if kind == "aos":
                _log("WriteFailed", "孩子 %s 的 exit 檔收尾失敗（退出碼 %d）：%s" %
                     (name, code, diagnostic.getvalue().strip()))
            child = self.children[name]
            child.update(alive=False, exits=child["exits"] + 1, last_exit=code)
            self._close(name)
            if child["restart"] and code != 0 and child["state"] == "running" and not self.state["stopping"]:
                child["state"] = "dead"
                self.restarts[name] = time.monotonic() + self.info["restart_delay_ms"] / 1000
            else:
                del self.children[name]
            self.save()

    def restart_due(self):
        if self.stop_requested:
            self.request_stop()
        for name, deadline in list(self.restarts.items()):
            if self.stop_requested and not self.state["stopping"]:
                self.request_stop()
            if name not in self.children:
                continue
            if self.state["stopping"]:
                self.children.pop(name, None)
                self.restarts.pop(name, None)
                self.save()
            elif time.monotonic() >= deadline:
                child = self.children[name]
                try:
                    self._launch(name, child["target"], child["dir_target"], child["restart"], child)
                except DaemonError as exc:
                    _log(exc.code, exc.msg)
                    self.restarts[name] = time.monotonic() + self.info["restart_delay_ms"] / 1000

    def advance_stops(self):
        for name, (stage, deadline) in list(self.stages.items()):
            if self.procs[name].process.poll() is not None or time.monotonic() < deadline:
                continue
            if stage == "stop":
                self._term(name)
            elif stage == "term":
                _signal_pid(self.children[name]["pid"], signal.SIGKILL, group=True)
                self.stages[name] = ("kill", float("inf"))

    def drain(self):
        for name, handle in list(self.procs.items()):
            if name in self.pending:
                self._flush(name)
            # 每圈限制讀量，會不停吐 stdout 的孩子也不能餓死其他孩子。
            for _ in range(16):
                try:
                    if not os.read(handle.process.stdout.fileno(), 65536):
                        break
                except BlockingIOError:
                    break

    def _close(self, name):
        handle = self.procs.pop(name)
        handle.process.stdin.close()
        handle.process.stdout.close()
        self.stages.pop(name, None)
        self.pending.pop(name, None)

    def close(self):
        for name in list(self.procs):
            self._close(name)

    def step(self):
        if self.stop_requested:
            self.request_stop()
        aos_home.scan_controls(self.home, self.request_stop)
        for name in aos_home.list_requests(self.home):
            if self.stop_requested:
                self.request_stop()
            self.process_request(name)
        self.drain()
        self.reap()
        self.restart_due()
        self.advance_stops()
        return self.state["stopping"] and not self.children


def _log(code, msg):
    sys.stderr.write("aos-daemon: %s: %s\n" % (code, str(msg).replace("\n", " ")))


def run(home):
    home = Path(home).absolute()
    home.mkdir(parents=True, exist_ok=True)
    if not (home / "info.json").exists():
        aos_home.write_json(home / "info.json", {"_metainfo": {"_type": "daemon", "_version": 1},
            "poll_ms": 20, "restart_delay_ms": 1000, "stop_wait_ms": 5000, "kill_wait_ms": 5000})
    info = aos_home.load_info(home, "daemon")
    for key, default in (("restart_delay_ms", 1000), ("stop_wait_ms", 5000), ("kill_wait_ms", 5000)):
        if type(info.setdefault(key, default)) is not int or info[key] < 0:
            raise DaemonError("FieldTypeMismatch", "%s 必須是非負整數" % key)
    lock = os.open(home / ".daemon.lock", os.O_RDWR | os.O_CREAT | os.O_CLOEXEC, 0o600)
    handlers = {}
    owner = None
    try:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise DaemonError("AlreadyRunning", "同家已有 daemon 在跑") from exc
        aos_home.ensure_queue(home)
        old_state = read_state(home)
        owner = Daemon(home, info)
        def on_signal(signum, frame):
            owner.stop_requested = True
        for sig in (signal.SIGTERM, signal.SIGINT):
            handlers[sig] = signal.signal(sig, on_signal)
        handlers[signal.SIGPIPE] = signal.signal(signal.SIGPIPE, signal.SIG_IGN)
        _previous_children(old_state, info)
        aos_home.reconcile(home, old_state.get("current"))
        owner.save()
        while not owner.step():
            time.sleep(info["poll_ms"] / 1000)
        owner.state["pid"] = 0
        owner.save()
        return 0
    finally:
        if owner is not None:
            owner.close()
        for sig, previous in handlers.items():
            signal.signal(sig, previous)
        os.close(lock)


serve = run


def stop(home, wait_ms=30000):
    """放 stop notification 後，以 flock 等主人退出；逾時保留已送通知。"""
    if not is_alive(home):
        print("not running")
        return 0
    aos_home.post_request(home, aos_client.new_name("stop"),
                          {"jsonrpc": "2.0", "method": "stop"})
    deadline = time.monotonic() + wait_ms / 1000
    while is_alive(home):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise DaemonError("Timeout", "等 daemon 退出逾時；stop 通知已送出，未撤回")
        time.sleep(min(.02, remaining))
    print("stopped")
    return 0


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(prog="aos-daemon", description="執行 daemon；stop 子命令送出停機通知並等待退出")
    parser.add_argument("--home", metavar="D", help="daemon 家（預設 AOS_DAEMON_HOME 或 ~/.aos-daemon）")
    commands = parser.add_subparsers(dest="command")
    stopping = commands.add_parser("stop", help="停止 daemon 並等待退出")
    stopping.add_argument("--home", metavar="D", default=argparse.SUPPRESS,
                          help="daemon 家（預設 AOS_DAEMON_HOME 或 ~/.aos-daemon）")
    stopping.add_argument("--wait-ms", type=int, default=30000, metavar="N",
                          help="等退出的上限，非負毫秒（預設 30000）")
    try:
        options = parser.parse_args(args)
        if options.home == "":
            parser.error("--home 不可為空")
        if options.command == "stop" and options.wait_ms < 0:
            stopping.error("--wait-ms 必須是非負整數")
    except SystemExit as exc:
        return exc.code
    home = daemon_home(options.home)
    try:
        return stop(home, options.wait_ms) if options.command == "stop" else run(home)
    except aos_home.HomeError as exc:
        _log(exc.code, exc.msg)
    except (OSError, ValueError, TypeError) as exc:
        _log("IOFailed", exc)
    return 1


if __name__ == "__main__":
    sys.exit(main())
