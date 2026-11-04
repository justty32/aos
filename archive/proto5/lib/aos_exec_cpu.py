"""exec cpu 的主人：逐件執行、控制 pipe 與開機對帳。

照 ../spec/cpu/ §4～§7；共用信封與檔案交接由 aos_home 處理，
目標的三種解讀與執行一律交給 aos_exec.run_target_full。
"""
import fcntl
import hashlib
import os
import signal
import stat
import sys
import time

import aos_exec
import aos_home
import aos_hops


def _control_error(obj):
    if not isinstance(obj, dict) or obj.get("jsonrpc") != "2.0" or not isinstance(obj.get("method"), str):
        return "控制行必須是含 jsonrpc 2.0 與字串 method 的物件"
    if "id" in obj and not aos_home._valid_id(obj["id"]):
        return "id 必須是字串、數字或 null（布林不算數字）"
    if obj["method"] == "stop" and "id" in obj:
        return "stop 必須是沒有 id 的 notification"
    return None


class Control:
    """非阻塞行協議；訊號 handler 只記旗標，主迴圈才處理。"""

    def __init__(self):
        self.fd = 0 if stat.S_ISFIFO(os.fstat(0).st_mode) else None
        self.output_fd = None
        self.buffer = b""
        self.eof = False
        self.stopping = False
        self.force = False
        self.pending_signals = 0
        self.handlers = {}
        if self.fd is not None:
            os.set_blocking(self.fd, False)

    def install(self):
        for sig in (signal.SIGTERM, signal.SIGINT):
            self.handlers[sig] = signal.signal(sig, self._signal)
        self.handlers[signal.SIGPIPE] = signal.signal(signal.SIGPIPE, signal.SIG_IGN)

    def _signal(self, signum, frame):
        self.pending_signals += 1

    def stop(self):
        self.stopping = True

    def _lines(self):
        if self.fd is None or self.eof:
            return []
        while True:
            try:
                chunk = os.read(self.fd, 65536)
            except BlockingIOError:
                break
            if not chunk:
                self.eof = True
                break
            self.buffer += chunk
        lines = self.buffer.split(b"\n")
        self.buffer = b"" if self.eof else lines.pop()
        if self.eof:
            lines.pop()                       # EOF 的最後半行不算一則
        methods = []
        for line in lines:
            try:
                obj = aos_home._loads(line)
            except (ValueError, UnicodeError):
                reason = "控制行不是合法 JSON"
            else:
                reason = _control_error(obj)
                if reason is None:
                    methods.append(obj["method"])
                    continue
            sys.stderr.write("aos-cpu: BadControl: %s\n" % reason)
        return methods

    def wait_go(self):
        if self.fd is None:
            return True
        while True:
            methods = self._lines()
            if "go" in methods:
                if "stop" in methods or self.eof:
                    self.stop()
                return True
            if self.eof or self.pending_signals:
                return False
            time.sleep(0.01)

    def relocate(self):
        if self.fd is None:
            return
        self.fd = fcntl.fcntl(0, fcntl.F_DUPFD_CLOEXEC, 64)
        self.output_fd = fcntl.fcntl(1, fcntl.F_DUPFD_CLOEXEC, 64)
        null = os.open(os.devnull, os.O_RDONLY)
        try:
            os.dup2(null, 0)
        finally:
            os.close(null)
        os.dup2(2, 1)

    def poll(self, process=None):
        while self.pending_signals:
            self.pending_signals -= 1
            if self.stopping:
                self.force = True
            self.stop()
        if "stop" in self._lines() or self.eof:
            self.stop()
        return self.force

    def close(self):
        for sig, previous in self.handlers.items():
            signal.signal(sig, previous)
        for fd in (self.fd, self.output_fd):
            if fd is not None and fd >= 64:
                os.close(fd)


def _params(envelope, timeout_ms):
    params = envelope.params
    if not isinstance(params, dict):
        return None, aos_home.params_error(envelope.id, "params 必須是物件", ["params"])
    checks = {
        "target": lambda v: isinstance(v, str) and "\0" not in v,
        "dir_target": lambda v: isinstance(v, str) and "\0" not in v,
        "timeout_ms": lambda v: type(v) is int and v >= 0,
        "stderr": lambda v: v is None or (isinstance(v, str) and "\0" not in v),
        "args": lambda v: isinstance(v, list) and all(
            isinstance(x, str) and "\0" not in x for x in v),
    }
    if "target" not in params:
        return None, aos_home.params_error(envelope.id, "params 缺少 target", ["params", "target"])
    for key, check in checks.items():
        if key in params and not check(params[key]):
            return None, aos_home.params_error(envelope.id, "%s 型別不合" % key,
                                              ["params", key])
    values = {key: params[key] for key in checks if key in params}
    values.setdefault("timeout_ms", timeout_ms)
    values["xxx"] = values.pop("target")
    return values, None


def _execute(envelope, info, control):
    if envelope.error is not None:
        return envelope.error, False
    if envelope.method != "aos-exec":
        return aos_home.error_response(envelope.id, -32601, "不認得 method：%s" % envelope.method), False
    params, error = _params(envelope, info["timeout_ms"])
    if error is not None:
        return error, False
    result = aos_exec.run_target_full(**params, on_poll=control.poll, poll_ms=info["poll_ms"])
    if result.kind == aos_exec.USAGE:
        return aos_home.params_error(envelope.id, "aos-exec 的目標或參數用法錯誤",
                                     ["params"], code="Usage"), False
    return aos_home.result_response(envelope.id, {
        "code": result.code, "kind": result.kind, "timed_out": result.timed_out,
        "stopped": result.stopped, "ms": result.ms,
    }), True


def _validate_notify(info):
    """cpu-notify §1：`notify` 沒寫就跳過；有寫必須是絕對路徑字串，否則照現有讀驗方式報錯。"""
    if "notify" not in info:
        return
    value = info["notify"]
    if not isinstance(value, str) or not os.path.isabs(value):
        raise aos_home.HomeError("FieldTypeMismatch", "notify 必須是絕對路徑字串")


def _notify_digest(home, name):
    """cpu-notify §2：SHA-256(home 絕對路徑 + \\n + name) 前 16 個十六進位字元。"""
    return hashlib.sha256(("%s\n%s" % (home, name)).encode("utf-8")).hexdigest()[:16]


def _send_notify(notify_dir, home, name):
    """放一張 `resp-<digest>.json` 通知（§3.1 放單同款）；EEXIST 當成功，其餘失敗只記 stderr 一行。"""
    path = os.path.join(notify_dir, "resp-%s.json" % _notify_digest(home, name))
    obj = {"jsonrpc": "2.0", "method": "responded", "params": {"home": home, "name": name}}
    try:
        aos_home.link_json(path, obj)
    except aos_home.RequestExists:
        pass                                   # 已經丟過同一則，當成功
    except aos_home.HomeError as exc:
        sys.stderr.write("aos-cpu: NotifyFailed: %s\n" % exc)


def _notify_backfill(home, notify_dir):
    """啟動：對 responses/ 裡每一份回音補丟一次通知（開機對帳之後、進迴圈之前）。"""
    try:
        names = sorted(os.listdir(os.path.join(home, "responses")))
    except OSError as exc:
        sys.stderr.write("aos-cpu: NotifyFailed: %s\n" % exc)
        return
    for name in names:
        if name.endswith(".json"):             # 跳過放單留下的 .tmp 半成品
            _send_notify(notify_dir, home, name)


def run(home):
    """管理一個 exec_cpu 家直到停機；主人 I/O 失敗留 current 給下一任對帳。"""
    home = os.path.abspath(home)
    control = Control()
    control.install()
    previous_cwd = os.getcwd()
    try:
        if not control.wait_go():
            return 0
        info = aos_home.load_info(home, "exec_cpu")
        _validate_notify(info)
        aos_home.ensure_queue(home)
        control.relocate()
        os.chdir(home)
        state = aos_home.read_state(home)
        aos_home.reconcile(home, state.get("current"))
        state.update(pid=os.getpid(), current=None)
        state.setdefault("runs", 0)
        aos_home.write_state(home, state)
        if "notify" in info:
            _notify_backfill(home, info["notify"])
        bell = aos_home.Doorbell(home)   # 09-24 tick-gap：放單的人按門鈴就馬上醒（cpu.md §6.5）
        try:
            return _loop(home, info, state, control, bell)
        finally:
            bell.close()
    finally:
        os.chdir(previous_cwd)
        control.close()


def _loop(home, info, state, control, bell):
    """主迴圈（cpu.md §6.3）：控制檔 → 停機？ → 撿一件做完；沒單就睡 poll_ms 或等門鈴。"""
    while True:
        aos_home.scan_controls(home, control.stop)
        control.poll()
        if control.stopping:
            # 收下工作期間到達的 stop；ack 也完成其可重做的兩步。
            aos_home.scan_controls(home, control.stop)
            state["current"] = None
            aos_home.write_state(home, state)
            return 0
        names = aos_home.list_requests(home)
        if not names:
            bell.wait(info["poll_ms"] / 1000, control.fd if control.fd is not None and not control.eof else None)
            continue
        name = names[0]
        request = os.path.join(home, "requests", name)
        envelope = aos_home.read_request(request)
        aos_hops.mark("cpu", "pick", request=name, home=home)
        state["current"] = {"name": name, "id": envelope.id, "notify": envelope.notify}
        aos_home.write_state(home, state)
        response, ran = _execute(envelope, info, control)
        if not envelope.notify:
            aos_home.write_json(os.path.join(home, "responses", name), response)
        os.unlink(request)
        if not envelope.notify and "notify" in info:
            _send_notify(info["notify"], home, name)
        state["current"] = None
        state["runs"] += int(ran)
        aos_home.write_state(home, state)
        aos_hops.mark("cpu", "done", request=name, home=home)


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        args = ["."]  # 09-24 fix-r4：DIR 可省略，省略＝目前資料夾
    if len(args) != 1 or args[0].startswith("-") or not os.path.isdir(args[0]):
        sys.stderr.write("aos-cpu: Usage: 用法是 aos-cpu [DIR]，DIR（省略＝目前資料夾）必須是資料夾\n")
        return 2
    try:
        return run(args[0])
    except aos_home.HomeError as error:
        sys.stderr.write("aos-cpu: %s: %s\n" % (error.code, error.msg))
    except (OSError, ValueError, TypeError) as error:
        sys.stderr.write("aos-cpu: IOFailed: %s\n" % error)
    return 1


if __name__ == "__main__":
    sys.exit(main())
