"""寫入紀錄（spec.md 第 5 節「只碰給的資料夾」）：環境有 AOS7_AUDIT 且在任務裡時，Python 啟動就裝一個 audit hook，
把每個「寫」的動作記到 `$AOS7_TASK/writes.jsonl`：{"op", "path"（實際位置）, "ok", "pid", "via"（經過連結時寫的路徑）}。

- 只記空間根（AOS7_ROOT）底下的寫入；空間外（/dev/null、__pycache__ 等）不管。
- ok＝寫入的實際位置落在自己的 node（不含裡面巢狀的別的 node／daemon 根）或某個掛載點的目標底下。
- 只看得到 Python 程序（含 Python 起的 Python）；sh、C 程式的寫入看不到（problems.md M-3）。
- 只記不擋。tick 只在 AOS7_AUDIT 有值時把這個資料夾放進任務的 PYTHONPATH。
"""
import json
import os
import sys


def _install():
    e = os.environ
    task, node, root = e.get("AOS7_TASK"), e.get("AOS7_NODE"), e.get("AOS7_ROOT")
    if not (e.get("AOS7_AUDIT") and task and node and root):
        return
    rp = os.path.realpath
    root_r, node_r = rp(root), rp(node)

    def load_targets():
        """birth.json 的掛載點目標；執行中加掛（M-6）後 tick 會改 birth.json，所以判不過時重讀一次。"""
        try:
            with open(os.path.join(task, "birth.json"), encoding="utf-8") as f:
                mounts = json.load(f).get("mounts") or {}
        except (OSError, ValueError):
            mounts = {}
        return [rp(v["at"]) for v in mounts.values() if isinstance(v, dict) and "at" in v]
    targets = load_targets()
    log = os.path.join(task, "writes.jsonl")
    busy = []
    wflags = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC

    def under(p, base):
        return p == base or p.startswith(base + os.sep)

    def nested(real):
        """real 與 node 之間有沒有別的 node（.aos/timeline.json）或 daemon 根（.aosd/）。"""
        d = os.path.dirname(real)
        while d != node_r and under(d, node_r):
            if os.path.exists(os.path.join(d, ".aos", "timeline.json")) or os.path.isdir(os.path.join(d, ".aosd")):
                return True
            d = os.path.dirname(d)
        return False

    def record(op, path):
        if not isinstance(path, (str, bytes)):
            return
        real = rp(os.path.join(os.getcwd(), os.fsdecode(path)))
        if not under(real, root_r) or real == rp(log):
            return
        ok = any(under(real, t) for t in targets) or (under(real, node_r) and not nested(real))
        if not ok:
            targets[:] = load_targets()
            ok = any(under(real, t) for t in targets)
        rec = {"op": op, "path": real, "ok": ok, "pid": os.getpid()}
        given = os.path.abspath(os.fsdecode(path))
        if given != real:
            rec["via"] = given   # 經過掛載點（或別的連結）寫的：寫的時候用的路徑
        line = json.dumps(rec, ensure_ascii=False) + "\n"
        fd = os.open(log, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.write(fd, line.encode())
        finally:
            os.close(fd)

    def hook(event, args):
        if busy:
            return
        try:
            busy.append(1)
            if event == "open":
                path, mode, flags = (tuple(args) + (None, None))[:3]
                w = (isinstance(flags, int) and flags & wflags) or (isinstance(mode, str) and any(c in mode for c in "wax+"))
                if w:
                    record("open", path)
            elif event in ("os.rename", "os.replace"):
                record(event, args[0])
                record(event, args[1])
            elif event in ("os.remove", "os.rmdir", "os.mkdir", "os.truncate", "shutil.rmtree"):
                record(event, args[0])
            elif event in ("os.symlink", "os.link"):
                record(event, args[1])
        except Exception:
            pass
        finally:
            busy.clear()

    sys.addaudithook(hook)


_install()
