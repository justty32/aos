"""proto7-1 共用的小工具：JSON 檔讀寫（原子）、時間字串、路徑、任務環境（spec.md 第 0、5 節）。"""
import contextlib
import datetime
import json
import os
import time

BIN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin")


def now():
    """給人看的時間字串（spec 第 0 節：邏輯不依賴它）。"""
    return datetime.datetime.now().isoformat(timespec="milliseconds")


def read_json(path, default=None):
    """讀 JSON 檔；不存在或壞掉回 default。"""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json(path, obj):
    """原子寫：先寫暫存檔再 rename；需要的話建資料夾。"""
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    # 暫存檔以 `.` 開頭：別人列資料夾（`*.json`、sh 的 `ls`）時不會讀到寫一半的檔（probes/polyglot N11）
    tmp = os.path.join(d, ".%s.tmp.%d" % (os.path.basename(path), os.getpid()))
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, path)


def edit_json(path, fn, default=None):
    """讀—改—寫一個 JSON 檔，期間對 `<path>.lock` 拿 flock（多個寫的人約定都用它，就不會互相蓋掉；probes/selfmod、lifecycle）。

    fn(舊內容) 回新內容；回 None＝不寫。回寫進去的內容。tick 只讀不拿鎖（寫是原子的，讀到的一定是完整的一版）。"""
    import fcntl
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path + ".lock", "a") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        new = fn(read_json(path, default))
        if new is not None:
            write_json(path, new)
        return new


@contextlib.contextmanager
def action_lock(root, node):
    """tick／tock 整個動作期間對 `<node>/.aos/action.lock` 拿 flock，拿到後比對 daemon 世代（astra-4 I-01）。

    yield True＝可以寫；False＝自己是舊 daemon 起的動作（環境 AOS7_GEN 跟 `<root>/.aosd/gen.json` 不同），什麼都不要寫。
    新 daemon 先換世代才起時間線；舊動作要嘛在新動作之前做完（拿著鎖時新的進不來），要嘛拿到鎖時看到世代變了。
    沒有 AOS7_GEN（人手跑、測試）不比對。"""
    import fcntl
    with open(os.path.join(node, ".aos", "action.lock"), "a") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        mine = os.environ.get("AOS7_GEN")
        cur = read_json(os.path.join(root, ".aosd", "gen.json"), {}) or {}
        yield mine is None or not isinstance(cur, dict) or str(cur.get("gen")) == mine


def append_jsonl(path, obj):
    """流水帳加一行。"""
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def read_jsonl(path):
    """讀流水帳，壞行跳過。"""
    out = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    except OSError:
        pass
    return out


def tail_jsonl(path, k, block=65536):
    """流水帳最後 k 行（壞行跳過）：從檔尾往回一塊一塊讀，不讀整個檔（astra-3 三-3）。"""
    if k <= 0:
        return []
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            pos, buf = f.tell(), b""
            while pos > 0 and buf.count(b"\n") <= k:
                step = min(block, pos)
                pos -= step
                f.seek(pos)
                buf = f.read(step) + buf
    except OSError:
        return []
    lines = buf.split(b"\n")
    if pos > 0:
        lines = lines[1:]  # 第一段可能是半行
    out = []
    for line in lines[-(k + 1):]:
        try:
            out.append(json.loads(line))
        except ValueError:
            pass
    return out[-k:]


def node_path(root, node_id):
    """node id → 絕對路徑（根是 "."）。"""
    root = os.path.abspath(root)
    return root if node_id in (".", "") else os.path.join(root, node_id)


def node_id_of(root, path):
    """絕對路徑 → node id。"""
    rel = os.path.relpath(os.path.abspath(path), os.path.abspath(root))
    return "." if rel == "." else rel.replace(os.sep, "/")


def join_id(base, rel):
    """node id 接相對路徑（kernel 算成員 id 用）。"""
    if base in (".", ""):
        return os.path.normpath(rel).replace(os.sep, "/")
    return os.path.normpath(os.path.join(base, rel)).replace(os.sep, "/")


def aos_dir(node):
    return os.path.join(node, ".aos")


TASK_DIRS = ("tasks", "tasks-old")   # 任務資料夾在 `.aos/tasks/`；tock 把結束很久的搬到 `.aos/tasks-old/`（Q3）


def task_dirs_of(aos):
    """`<aos>/tasks/` 與 `<aos>/tasks-old/` 底下所有任務資料夾：[(tid, 路徑)]，依 tid 排序（tasks 的在前）。"""
    out = []
    for sub in TASK_DIRS:
        base = os.path.join(aos, sub)
        try:
            names = sorted(os.listdir(base))
        except OSError:
            continue
        out += [(t, os.path.join(base, t)) for t in names if not t.startswith(".")]
    return out


def task_env():
    """任務從環境變數讀自己是誰（spec 第 5 節）。缺了丟 KeyError。"""
    e = os.environ
    return {"root": e["AOS7_ROOT"], "node": e["AOS7_NODE"], "node_id": e["AOS7_NODE_ID"],
            "task": e["AOS7_TASK"], "tid": e["AOS7_TID"]}


def wait_tock(task_dir, last_round, poll=0.02, timeout=None):
    """等 tock.json 的 round 比 last_round 大，回新的 round；逾時回 None（S-11）。"""
    path = os.path.join(task_dir, "tock.json")
    end = None if timeout is None else time.monotonic() + timeout
    while True:
        t = read_json(path)
        if t and isinstance(t.get("round"), int) and t["round"] > last_round:
            return t["round"]
        if end is not None and time.monotonic() >= end:
            return None
        time.sleep(poll)


def env_with_bin(env=None):
    """複製一份環境，PATH 前面加上 proto7-1 的 bin/。"""
    env = dict(os.environ if env is None else env)
    env["PATH"] = BIN + os.pathsep + env.get("PATH", "")
    return env
