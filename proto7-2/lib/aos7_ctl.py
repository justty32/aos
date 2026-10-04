"""aos7-ctl：替你寫控制檔的小工具——LLM 直接寫同樣的 JSON 檔也做得到（spec.md 第 10 節，S-01）。

    aos7-ctl daemon <root|掛載點> <op> [node] [--kill|--no-kill] [--rounds N] [--owner X] [--all] [--by WHO]
    aos7-ctl task <槽資料夾> <kill|restart> [why] [--reload] [--run N] [--by WHO]
    aos7-ctl add <node 資料夾> '<項目 JSON>'... [--by WHO]

daemon 控制檔用固定名 `<by>.<op>.<node>.json`（回條同名蓋掉，只留每個寫的人、每件事的上一次；W3）。
起點是 proto7-1 lib/aos7_ctl.py。
"""
import argparse
import json
import os
import re
import sys

from aos7_fs import edit_json, write_json

DAEMON_OPS = ("register", "unregister", "pause", "resume", "wake", "stop")
TASK_OPS = ("kill", "restart")


def default_by():
    """沒給 --by 時：在任務裡就是 `<node-id>:<tid>`，否則 `cli`。"""
    e = os.environ
    if e.get("AOS7_TID"):
        return "%s:%s" % (e.get("AOS7_NODE_ID", "?"), e["AOS7_TID"])
    return "cli"


def ctl_dir(where):
    """`where` 可以是 daemon 根、掛進來的 `.aosd`、或掛進來的 `.aosd/ctl` 本身（S-23）。"""
    where = os.path.abspath(where)
    real = os.path.realpath(where)
    if os.path.basename(real) == ".aosd":
        return os.path.join(where, "ctl")
    if os.path.basename(real) == "ctl" and os.path.basename(os.path.dirname(real)) == ".aosd":
        return where
    return os.path.join(where, ".aosd", "ctl")   # daemon 根（daemon 還沒起也行，起來才處理；2.3）


def fixed_name(by, op, node):
    """`<by>.<op>.<node>.json`：`/` 換成 `+`，其他不安全的字元換成 `_`。"""
    def safe(s):
        return re.sub(r"[^A-Za-z0-9_.:+-]", "_", s.replace("/", "+")).lstrip(".") or "_"
    parts = [safe(by), op] + ([safe(node)] if node is not None else [])
    return ".".join(parts) + ".json"


def daemon_ctl(root, op, node=None, kill=None, by=None, rounds=None, owner=None, all_=False, why=None):
    """寫 `<ctl 資料夾>/<by>.<op>.<node>.json`，回檔案路徑。"""
    by = by or default_by()
    obj = {"op": op, "by": by}
    if node is not None:
        obj["node"] = node
    if kill is not None:
        obj["kill"] = kill
    if rounds is not None:
        obj["rounds"] = rounds
    if owner is not None:
        obj["owner"] = owner
    if all_:
        obj["all"] = True
    if why:
        obj["why"] = why
    path = os.path.join(ctl_dir(root), fixed_name(by, op, node))
    write_json(path, obj)
    return path


def task_ctl(slot_dir, op, why="", by=None, reload=False, run=None):
    """寫 `<槽>/ctl.json`（已有就覆寫：只留最後一個），回檔案路徑。"""
    path = os.path.join(os.path.abspath(slot_dir), "ctl.json")
    obj = {"op": op, "by": by or default_by(), "why": why}
    if reload:
        obj["reload"] = True
    if run is not None:
        obj["run"] = run
    write_json(path, obj)
    return path


def add_items(node, items):
    """拿 tasks.json.lock 把幾項加進 `<node>/.aos/tasks.json`（一次 rename，同一回合看到）。回檔案路徑。"""
    path = os.path.join(os.path.abspath(node), ".aos", "tasks.json")

    def fn(t):
        if t is None:
            t = {"tasks": []}
        if not isinstance(t, dict) or not isinstance(t.get("tasks", []), list):
            raise ValueError("tasks.json 不是 {\"tasks\": [...]}，沒加")
        t = dict(t)
        t["tasks"] = list(t.get("tasks", [])) + list(items)
        return t
    edit_json(path, fn)
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(prog="aos7-ctl", description="寫 aos7 控制檔")
    sub = ap.add_subparsers(dest="what", required=True)
    d = sub.add_parser("daemon")
    d.add_argument("root", help="daemon 根，或掛進來的 .aosd／.aosd/ctl")
    d.add_argument("op", choices=DAEMON_OPS)
    d.add_argument("node", nargs="?")
    d.add_argument("--kill", dest="kill", action="store_true", default=None, help="stop：先 kill 所有活任務")
    d.add_argument("--no-kill", dest="kill", action="store_false", help="unregister：不殺 node 上的任務")
    d.add_argument("--rounds", type=int, help="resume：只跑這麼多回合就以同一個 owner 再 pause")
    d.add_argument("--owner", help="pause／resume 的 owner")
    d.add_argument("--all", action="store_true", help="resume：清掉所有 owner 的 pause")
    d.add_argument("--why")
    d.add_argument("--by")
    t = sub.add_parser("task")
    t.add_argument("slot_dir")
    t.add_argument("op", choices=TASK_OPS)
    t.add_argument("why", nargs="?", default="")
    t.add_argument("--reload", action="store_true", help="restart 照 node 現在 tasks.json 的同名項目")
    t.add_argument("--run", type=int, help="只在槽現在的 run 是這個時執行")
    t.add_argument("--by")
    a_ = sub.add_parser("add")
    a_.add_argument("node")
    a_.add_argument("items", nargs="+")
    a_.add_argument("--by")
    try:
        a = ap.parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit as e:
        return 0 if e.code == 0 else 1
    if a.what == "daemon":
        if a.op not in ("stop",) and not a.node:
            print("aos7-ctl: %s 要給 node" % a.op, file=sys.stderr)
            return 1
        path = daemon_ctl(a.root, a.op, a.node, a.kill, a.by, a.rounds, a.owner, a.all, a.why)
    elif a.what == "task":
        if a.reload and a.op != "restart":
            print("aos7-ctl: --reload 只給 restart", file=sys.stderr)
            return 1
        path = task_ctl(a.slot_dir, a.op, a.why, a.by, a.reload, a.run)
    else:
        try:
            items = [json.loads(x) for x in a.items]
        except ValueError as e:
            print("aos7-ctl: 項目不是 JSON：%s" % e, file=sys.stderr)
            return 1
        if not all(isinstance(i, dict) for i in items):
            print("aos7-ctl: 每個項目要是 JSON 物件", file=sys.stderr)
            return 1
        try:
            path = add_items(a.node, items)
        except ValueError as e:
            print("aos7-ctl: %s" % e, file=sys.stderr)
            return 1
    print(json.dumps({"wrote": path}, ensure_ascii=False))
    return 0
