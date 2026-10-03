"""aos7-ctl：替你寫控制檔的小工具——LLM 直接寫同樣的 JSON 檔也做得到（spec.md 第 8 節，S-01）。

    aos7-ctl daemon <root|掛載點> <pause|resume|stop|rescan|wake> [node] [--kill] [--rounds N] [--by WHO]
    aos7-ctl task <taskdir> <kill|restart> [why] [--by WHO]
"""
import argparse
import json
import os
import sys
import time

from aos7_fs import write_json

DAEMON_OPS = ("pause", "resume", "stop", "rescan", "wake")
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
    if os.path.isdir(os.path.join(where, ".aosd")):
        return os.path.join(where, ".aosd", "ctl")
    if os.path.basename(os.path.realpath(where)) == ".aosd":
        return os.path.join(where, "ctl")
    return where


def daemon_ctl(root, op, node=None, kill=False, by=None, rounds=None):
    """寫 `<ctl 資料夾>/<時間>-<pid>.json`（見 ctl_dir），回檔案路徑。"""
    obj = {"op": op, "by": by or default_by()}
    if node is not None:
        obj["node"] = node
    if kill:
        obj["kill"] = True
    if rounds is not None:
        obj["rounds"] = rounds
    name = "%d-%d.json" % (time.time_ns(), os.getpid())
    path = os.path.join(ctl_dir(root), name)
    write_json(path, obj)
    return path


def task_ctl(tdir, op, why="", by=None):
    """寫 `<taskdir>/ctl.json`（已有就覆寫：只留最後一個），回檔案路徑。"""
    path = os.path.join(os.path.abspath(tdir), "ctl.json")
    write_json(path, {"op": op, "by": by or default_by(), "why": why})
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(prog="aos7-ctl", description="寫 aos7 控制檔")
    sub = ap.add_subparsers(dest="what", required=True)
    d = sub.add_parser("daemon")
    d.add_argument("root", help="daemon 根，或掛進來的 .aosd／.aosd/ctl")
    d.add_argument("op", choices=DAEMON_OPS)
    d.add_argument("node", nargs="?")
    d.add_argument("--kill", action="store_true", help="stop 時先 kill 所有活任務")
    d.add_argument("--rounds", type=int, help="resume 時只跑這麼多回合就自動 pause")
    d.add_argument("--by")
    t = sub.add_parser("task")
    t.add_argument("taskdir")
    t.add_argument("op", choices=TASK_OPS)
    t.add_argument("why", nargs="?", default="")
    t.add_argument("--by")
    try:
        a = ap.parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit as e:
        return 0 if e.code == 0 else 1
    if a.what == "daemon":
        if a.op in ("pause", "resume", "wake") and not a.node:
            print("aos7-ctl: %s 要給 node" % a.op, file=sys.stderr)
            return 1
        path = daemon_ctl(a.root, a.op, a.node, a.kill, a.by, a.rounds)
    else:
        path = task_ctl(a.taskdir, a.op, a.why, a.by)
    print(json.dumps({"wrote": path}, ensure_ascii=False))
    return 0
