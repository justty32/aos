"""Kernel：用 daemon 的 aos-run 排程普通 proto5 inst；沒有 module。"""
import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
import time

import aos_daemon
import aos_inst
from aos_directives import Context, DirectiveError, Document, resolve_located

__all__ = ["KernelError", "load", "init", "boot", "add", "remove", "tick", "status", "main"]
DEFAULTS = {"interval_ms": 1000, "timeout_ms": 0, "quantum": 5,
            "done_exit": 100, "wait_exit": 101, "bad_after": 10}
CLI = str(Path(__file__).resolve().parent.parent / "cli" / "aos-kernel")
IDLE = {"argv": [sys.executable, "-c", "pass"]}
COUNTERS = ("waiting", "wait_runs", "bad_runs", "bad_exit", "aos_ticks")


class KernelError(Exception):
    def __init__(self, code, msg):
        super().__init__("%s: %s" % (code, msg))
        self.code, self.msg = code, msg


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (ValueError, UnicodeError) as e:
        raise KernelError("JsonSyntax", "%s 不是合法 UTF-8 JSON：%s" % (path, e))
    except OSError as e:
        raise KernelError("ReadFailed", "讀不到 %s：%s" % (path, e))


def _write(path, obj):
    fd, tmp = tempfile.mkstemp(prefix=".write-", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _field(obj, key, loc, default=None):
    ctx = Context(loc.ctx.doc, base_dir=loc.ctx.base_dir, env=loc.ctx.env)
    return resolve_located(obj.get(key, default), ctx, loc.position + [key])


def load(dir, env=None):
    """info 的整份、各欄與 metainfo 解指示詞；設定以 K 為中心。"""
    root = Path(dir).resolve()
    path = root / "info.json"
    if not path.is_file():
        raise KernelError("NotAHome", "%s 沒有 kernel info.json" % root)
    obj = _read(path)
    try:
        top = resolve_located(obj, Context(Document(str(path), obj), base_dir=str(root), env=env), [])
        obj = top.value
        if not isinstance(obj, dict):
            raise KernelError("FieldTypeMismatch", "info.json 必須是物件")
        mi = _field(obj, "_metainfo", top)
        if not isinstance(mi.value, dict):
            raise KernelError("NotAHome", "缺少 kernel 的 _metainfo")
        kind = _field(mi.value, "_type", mi).value
        version = _field(mi.value, "_version", mi).value
        if kind != "kernel" or type(version) is not int or version != 1:
            raise KernelError("NotAHome", "_metainfo 必須是 kernel 第 1 版")
        cfg = {key: _field(obj, key, top, value).value for key, value in DEFAULTS.items()}
        cfg["ncpu"] = _field(obj, "ncpu", top).value
    except DirectiveError as e:
        raise KernelError("FieldTypeMismatch", str(e))
    for key, value in cfg.items():
        minimum = 1 if key in ("ncpu", "quantum", "wait_exit") else 0
        if type(value) is not int or value < minimum:
            raise KernelError("FieldTypeMismatch", "%s 必須是 >= %d 的整數" % (key, minimum))
    if cfg["done_exit"] > 255 or cfg["wait_exit"] > 255 or cfg["done_exit"] == cfg["wait_exit"]:
        raise KernelError("FieldTypeMismatch", "done_exit 要是 0～255（0 關閉），wait_exit 要是不同的 1～255")
    return root, cfg


@contextmanager
def _lock(path, blocking=True):
    with open(path, "a") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _name_key(value):
    return (0, int(value)) if value.isdigit() else (1, value)


def _name(value):
    if not isinstance(value, str) or not value or value in (".", "..") or "/" in value or "\0" in value:
        raise KernelError("FieldTypeMismatch", "行程名字必須是非空檔名，不能含 / 或 NUL")
    return value


def _state(root, cfg):
    st = _read(root / "state.json")
    if (not isinstance(st, dict) or not isinstance(st.get("cpus"), dict)
            or not isinstance(st.get("queue"), list) or not isinstance(st.get("waiting"), dict)):
        raise KernelError("FieldTypeMismatch", "state 必須有 cpus 物件、queue 陣列、waiting 物件")
    seen = set()
    for n, cur in st["cpus"].items():
        if n not in {str(i) for i in range(cfg["ncpu"])}:
            raise KernelError("FieldTypeMismatch", "state cpu 編號超出 ncpu")
        if cur is None:
            continue
        if not isinstance(cur, dict):
            raise KernelError("FieldTypeMismatch", "cpu entry 必須是物件或 null")
        name = _name(cur.get("pid"))
        if name in seen:
            raise KernelError("FieldTypeMismatch", "同一行程不能在兩顆 cpu：%s" % name)
        seen.add(name)
        _counters(cur)
        for key in ("runs_at", "seen_runs"):
            if type(cur.get(key)) is not int or cur[key] < 0:
                raise KernelError("FieldTypeMismatch", "cpu.%s 必須是非負整數" % key)
    for name in st["queue"]:
        _name(name)
    if len(set(st["queue"])) != len(st["queue"]):
        raise KernelError("FieldTypeMismatch", "queue 不能重複行程")
    for name, counters in st["waiting"].items():
        _name(name)
        _counters(counters)
    for n in range(cfg["ncpu"]):
        st["cpus"].setdefault(str(n), None)
    return st


def _counters(cur):
    if not isinstance(cur, dict):
        raise KernelError("FieldTypeMismatch", "行程計數必須是物件")
    for key in ("wait_runs", "bad_runs", "bad_exit", "aos_ticks"):
        if key in cur and (type(cur[key]) is not int or cur[key] < 0):
            raise KernelError("FieldTypeMismatch", "%s 必須是非負整數" % key)
    if "waiting" in cur and type(cur["waiting"]) is not bool:
        raise KernelError("FieldTypeMismatch", "waiting 必須是布林")


def init(dir, ncpu):
    if type(ncpu) is not int or ncpu < 1:
        raise KernelError("FieldTypeMismatch", "ncpu 至少 1")
    root = Path(dir).resolve()
    if root.exists():
        raise KernelError("AlreadyRunning", "%s 已存在，不覆蓋" % root)
    root.mkdir(parents=True)
    for part in ("procs/done", "procs/bad", "cpus", "syscalls/done"):
        (root / part).mkdir(parents=True)
    _write(root / "info.json", {"_metainfo": {"_type": "kernel", "_version": 1}, "ncpu": ncpu, **DEFAULTS})
    _write(root / "inst.json", {"argv": [sys.executable, CLI, "tick"], "cwd": str(root),
                                "stderr": {"$opt": "append", "$val": "kernel.log"}})
    _write(root / "state.json", {"cpus": {str(n): None for n in range(ncpu)}, "queue": [], "waiting": {}})
    for n in range(ncpu):
        _write(root / "cpus" / ("%d.json" % n), IDLE)
        (root / "cpus" / ("%d.json.lock" % n)).touch()
    (root / "kernel.log").touch()
    return str(root)


def _args(cfg):
    return ["--interval-ms", str(cfg["interval_ms"]), "--timeout-ms", str(cfg["timeout_ms"])]


def boot(dir):
    root, cfg = load(dir)
    # Kernel tick 可能等 daemon 的 remove；timeout_ms 是工作格的限制，不砍 kernel 自己。
    return aos_daemon.request("add", target=str(root / "inst.json"),
                              args=["--interval-ms", str(cfg["interval_ms"])])


def _inst(path):
    try:
        return aos_inst.load(str(path), str(Path(path).parent))
    except aos_inst.InstError as e:
        code = e.code if e.code in ("ReadFailed", "JsonSyntax") else "FieldTypeMismatch"
        raise KernelError(code, str(e))
    except UnicodeError as e:
        raise KernelError("JsonSyntax", str(e))


def _portable(inst):
    """把解好的 inst 還原成合法 v1 JSON，搬到 slot 後路徑和選項不變。"""
    raw = {"_metainfo": inst["metainfo"], "argv": inst["argv"], "cwd": inst["cwd"], "envs": inst["envs"]}
    if inst["cwd_mkdir"]:
        raw["cwd"] = {"$opt": "mkdir", "$val": inst["cwd"]}
    if inst["envs_clear"]:
        raw["envs"] = {"$opt": "clear", "$val": inst["envs"]}
    for key in ("stdin", "stdout", "stderr", "exit"):
        stream = inst[key]
        flags = [flag for flag, value in stream.items() if flag != "path" and value]
        if flags:
            raw[key] = {"$opt": flags}
            if "inherit" not in flags and "merge" not in flags:
                raw[key]["$val"] = stream["path"]
        else:
            raw[key] = stream["path"]
    return raw


def add(dir, inst_path, name=None):
    root, cfg = load(dir)
    inst = _portable(_inst(Path(inst_path).absolute()))
    with _lock(root / ".kernel.lock"):
        st = _state(root, cfg)
        used = {p.stem for folder in ("procs", "procs/done", "procs/bad") for p in (root / folder).glob("*.json")}
        used.update(cur["pid"] for cur in st["cpus"].values() if cur)
        if name is None:
            name = str(max([int(n) for n in used if n.isdigit()] + [0]) + 1)
        _name(name)
        if name in used:
            raise KernelError("AlreadyRunning", "行程名字已存在：%s" % name)
        _write(root / "procs" / (name + ".json"), inst)
    return name


def remove(dir, name, timeout=10):
    root, _ = load(dir)
    _name(name)
    file = "%d-%d-%s.json" % (time.time_ns(), os.getpid(), secrets.token_hex(2))
    _write(root / "syscalls" / file, {"op": "rm", "pid": name})
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        done = root / "syscalls/done" / file
        if done.exists():
            result = _read(done)
            if (not isinstance(result, dict) or type(result.get("ok")) is not bool
                    or not isinstance(result.get("msg"), str)):
                raise KernelError("FieldTypeMismatch", "rm 回音必須有 ok 布林與 msg 字串")
            if not result["ok"]:
                raise KernelError(result.get("code", "NotRunning"), result["msg"])
            return result
        time.sleep(.02)
    raise KernelError("NotRunning", "kernel 10 秒內未回覆，rm 請求仍保留")


def _save(root, st):
    _write(root / "state.json", st)


def _log(root, notes):
    with open(root / "kernel.log", "a", encoding="utf-8") as f:
        f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), "; ".join(notes) or "idle"))


def _observe(cfg, cur, entry):
    runs = entry["runs"]
    if runs < cur["seen_runs"]:
        cur["runs_at"] = cur["seen_runs"] = 0
    count = runs - cur["seen_runs"]
    if not count:
        return
    cur["seen_runs"] = runs
    kind, code = entry["last_kind"], entry["last_exit"]
    cur["waiting"] = kind == "child" and code == cfg["wait_exit"]
    cur["wait_runs"] = cur.get("wait_runs", 0) + count if cur["waiting"] else 0
    bad = kind == "child" and code not in (0, cfg["done_exit"], cfg["wait_exit"])
    cur["bad_runs"] = cur.get("bad_runs", 0) + count if bad else 0
    if bad:
        cur["bad_exit"] = code
    cur["aos_ticks"] = cur.get("aos_ticks", 0) + count if kind == "aos" else 0


def _retire(cfg, cur, entry):
    if cfg["done_exit"] and cur["seen_runs"] and entry["last_kind"] == "child" and entry["last_exit"] == cfg["done_exit"]:
        return "done"
    if cur.get("aos_ticks", 0) >= 2 or (cfg["bad_after"] and cur.get("bad_runs", 0) >= cfg["bad_after"]):
        return "bad"
    return None


def _quiesce(path, entry):
    # 沒拿到成功回音就不搬檔；NotRunning 也可能是 daemon 已死，不能當作已收屍。
    return aos_daemon.request("remove", target=str(path)) if entry is not None else None


def _yield_intent(path, wanted):
    """穩定 slot 鎖檔的一個 byte；設定不中斷本格，清除者必須已持 EX 鎖。"""
    with open(str(path) + ".lock", "r+b", buffering=0) as f:
        if wanted:
            f.write(b"Y")
        else:
            f.truncate(0)


def _syscalls(root, cfg, st, runs, notes):
    pending = set()
    for path in sorted((root / "syscalls").glob("*.json")):
        done = root / "syscalls/done" / path.name
        if done.exists():
            path.unlink()
            continue
        try:
            call = _read(path)
            if not isinstance(call, dict) or call.get("op") != "rm":
                raise KernelError("FieldTypeMismatch", "syscall 只接受 rm")
            name = _name(call.get("pid"))
            n = next((n for n, cur in st["cpus"].items() if cur and cur["pid"] == name), None)
            if n is not None:
                cpu = root / "cpus" / (n + ".json")
                entry = runs.get(str(cpu))
                _yield_intent(cpu, True)
                if entry and entry["running"]:
                    pending.add(name)
                    continue
                with _lock(str(cpu) + ".lock", False) as acquired:
                    if not acquired:
                        pending.add(name)
                        continue
                    _quiesce(cpu, entry)
                    runs.pop(str(cpu), None)
                    _write(cpu, IDLE)
                    _yield_intent(cpu, False)
                    st["cpus"][n] = None
            else:
                files = [root / folder / (name + ".json") for folder in ("procs", "procs/done", "procs/bad")]
                found = [file for file in files if file.exists()]
                if not found:
                    raise KernelError("NotRunning", "找不到行程：%s" % name)
                for file in found:
                    file.unlink()
            st["queue"] = [p for p in st["queue"] if p != name]
            st["waiting"].pop(name, None)
            _save(root, st)
            out = {"ok": True, "msg": "removed " + name}
            notes.append(out["msg"])
        except KernelError as e:
            out = {"ok": False, "code": e.code, "msg": e.msg}
        _write(done, out)
        path.unlink()
    return pending


def _queue(root, st, notes):
    on_cpu = {cur["pid"] for cur in st["cpus"].values() if cur}
    present = []
    for path in sorted((root / "procs").glob("*.json"), key=lambda p: _name_key(p.stem)):
        if path.stem in on_cpu:
            raise KernelError("FieldTypeMismatch", "cpu 與 queue 同名：%s" % path.stem)
        try:
            # 手工排進來的檔同樣完整解指示詞，搬家之前固化中心路徑。
            raw = _portable(_inst(path))
        except KernelError as e:
            os.replace(path, root / "procs/bad" / path.name)
            notes.append("bad %s: %s" % (path.stem, e))
            continue
        _write(path, raw)
        present.append(path.stem)
    st["queue"] = [p for p in st["queue"] if p in present]
    st["queue"].extend(p for p in present if p not in st["queue"])
    st["waiting"] = {p: value for p, value in st["waiting"].items() if p in present}


def _schedule(root, cfg, st, runs, notes, pending_rm=()):
    for n, cur in st["cpus"].items():
        path = root / "cpus" / (n + ".json")
        entry = runs.get(str(path))
        Path(str(path) + ".lock").touch(exist_ok=True)
        if cur and entry:
            _observe(cfg, cur, entry)
        retire = _retire(cfg, cur, entry) if cur and entry else None
        switch = st["queue"] and (cur is None or cur.get("waiting")
                   or cur["seen_runs"] - cur["runs_at"] >= cfg["quantum"])
        wanted = retire or switch or (cur and cur["pid"] in pending_rm)
        if wanted:
            # 不等瞬間 false 快照碰巧被 tick 看見；請 run 完成本格後讓出下一格。
            _yield_intent(path, True)
        else:
            # 例如候選 queue 被 rm，取消等待。只能在 slot 閒置、鎖內清意圖。
            with _lock(str(path) + ".lock", False) as acquired:
                if acquired:
                    _yield_intent(path, False)
        if (retire or switch) and not (entry and entry["running"]):
            with _lock(str(path) + ".lock", False) as acquired:
                if acquired:
                    final = _quiesce(path, entry)
                    if cur and final:
                        _observe(cfg, cur, final)
                        retire = _retire(cfg, cur, final)
                    entry = None
                    if cur:
                        name = cur["pid"]
                        if retire:
                            os.replace(path, root / "procs" / retire / (name + ".json"))
                            st["waiting"].pop(name, None)
                            notes.append("%s %s" % (retire, name))
                        else:
                            os.replace(path, root / "procs" / (name + ".json"))
                            st["waiting"][name] = {k: cur[k] for k in COUNTERS if k in cur}
                            st["queue"].append(name)
                        st["cpus"][n] = None
                    if st["queue"]:
                        name = st["queue"].pop(0)
                        os.replace(root / "procs" / (name + ".json"), path)
                        st["cpus"][n] = {"pid": name, "since": time.time(), "runs_at": 0,
                                         "seen_runs": 0, **st["waiting"].pop(name, {})}
                        notes.append("cpu%s=%s" % (n, name))
                    else:
                        _write(path, IDLE)
                    # 先存指派再啟動；remove 的 ack 已經排空舊 runner 的事件。
                    _save(root, st)
                    _yield_intent(path, False)
        if entry is None:
            if not path.exists():
                if st["cpus"][n]:
                    raise KernelError("ReadFailed", "cpu 檔案不見：%s" % path)
                _write(path, IDLE)
            Path(str(path) + ".lock").touch(exist_ok=True)
            if st["cpus"][n]:
                st["cpus"][n]["runs_at"] = st["cpus"][n]["seen_runs"] = 0
                _save(root, st)
            aos_daemon.request("add", target=str(path), args=_args(cfg))


def tick(dir="."):
    root, cfg = load(dir)
    with _lock(root / ".kernel.lock", False) as acquired:
        if not acquired:
            return 0
        st = _state(root, cfg)
        daemon = aos_daemon.read_state()
        if not daemon.get("pid"):
            raise KernelError("NotRunning", "daemon 沒在跑")
        runs = daemon["runs"]
        notes = []
        pending_rm = _syscalls(root, cfg, st, runs, notes)
        _queue(root, st, notes)
        _schedule(root, cfg, st, runs, notes, pending_rm)
        _save(root, st)
        _log(root, notes)
    return 0


def status(dir):
    root, cfg = load(dir)
    st = _state(root, cfg)
    try:
        daemon = aos_daemon.read_state()
    except aos_daemon.DaemonError:
        daemon = {"pid": None, "runs": {}}
    lines = ["kernel %s ncpu=%d quantum=%d daemon=%s" % (root, cfg["ncpu"], cfg["quantum"], daemon["pid"]),
             "CPU PROC RUNNING RUNS LAST_EXIT WAIT BAD"]
    for n, cur in st["cpus"].items():
        entry = daemon["runs"].get(str(root / "cpus" / (n + ".json")), {})
        lines.append("%s %s %s %s %s %s %s" % (n, cur["pid"] if cur else "idle", entry.get("running", False),
                     entry.get("runs", 0), entry.get("last_exit"), (cur or {}).get("waiting", False),
                     (cur or {}).get("bad_runs", 0)))
    lines.append("queue: " + (" ".join(st["queue"]) or "-"))
    for folder in ("done", "bad"):
        lines.append(folder + ": " + (" ".join(sorted(p.stem for p in (root / "procs" / folder).glob("*.json"))) or "-"))
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="aos-kernel", description="排程普通 proto5 inst")
    sub = ap.add_subparsers(dest="op", required=True)
    p = sub.add_parser("init")
    p.add_argument("dir")
    p.add_argument("--ncpu", required=True, type=int)
    for op in ("boot", "ls"):
        sub.add_parser(op).add_argument("dir")
    sub.add_parser("tick")
    p = sub.add_parser("add")
    p.add_argument("dir")
    p.add_argument("inst")
    p.add_argument("--name")
    p = sub.add_parser("rm")
    p.add_argument("dir")
    p.add_argument("name")
    a = ap.parse_args(argv)
    if a.op == "init" and a.ncpu < 1:
        ap.error("--ncpu 至少 1")
    try:
        if a.op == "init":
            print(init(a.dir, a.ncpu))
        elif a.op == "boot":
            boot(a.dir)
            print("boot " + str(Path(a.dir).resolve()))
        elif a.op == "add":
            print(add(a.dir, a.inst, a.name))
        elif a.op == "rm":
            print(remove(a.dir, a.name)["msg"])
        elif a.op == "ls":
            print(status(a.dir))
        else:
            return tick()
        return 0
    except (KernelError, aos_daemon.DaemonError) as e:
        sys.stderr.write("aos-kernel: %s\n" % " ".join(str(e).split()))
        return 1
    except OSError as e:
        sys.stderr.write("aos-kernel: ReadFailed: %s\n" % " ".join(str(e).split()))
        return 1


if __name__ == "__main__":
    sys.exit(main())
