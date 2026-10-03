"""proto7-1 共用的小工具：JSON 檔讀寫（原子）、時間字串、路徑、任務環境（spec.md 第 0、5 節）。"""
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
    tmp = "%s.tmp.%d" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, path)


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
