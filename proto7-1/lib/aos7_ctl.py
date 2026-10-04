"""aos7-ctl：替你寫控制檔的小工具——LLM 直接寫同樣的 JSON 檔也做得到（spec.md 第 8 節，S-01）。

人或任務從 bin/aos7-ctl 呼叫；只寫 `.aosd/ctl/<名字>.json` 或任務的 `ctl.json`，
不讀執行回條。daemon 在第 2 節處理前者，tick／tock 在第 6 節處理後者；寫成功不等於已執行。

    aos7-ctl daemon <root|掛載點> <pause|resume|stop|rescan|wake> [node] [--kill] [--rounds N] [--by WHO]
    aos7-ctl task <taskdir> <kill|restart> [why] [--reload] [--by WHO]
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
    """無參數；由任務環境回傳預設署名字串。缺 tid 回 `cli`，有 tid 但缺 node id 用 `?`。"""
    e = os.environ
    if e.get("AOS7_TID"):
        return "%s:%s" % (e.get("AOS7_NODE_ID", "?"), e["AOS7_TID"])
    return "cli"


def ctl_dir(where):
    """將 where（daemon 根、掛進來的 `.aosd` 或 ctl）轉成控制資料夾絕對路徑（第 8 節、S-23）。

    找不到內層 `.aosd`、實際位置也不叫 `.aosd` 時，原路徑就當 ctl；不驗證 daemon 是否存在。
    """
    where = os.path.abspath(where)
    if os.path.isdir(os.path.join(where, ".aosd")):
        return os.path.join(where, ".aosd", "ctl")
    if os.path.basename(os.path.realpath(where)) == ".aosd":
        return os.path.join(where, "ctl")
    return where


def daemon_ctl(root, op, node=None, kill=False, by=None, rounds=None):
    """向 root（根或掛載點）寫 op，回傳控制檔路徑；I/O 失敗向外拋出。

    node 指定時間線，kill 要求停機收任務，rounds 限制 resume 回合數；by 省略時由環境署名。
    這裡只組 JSON，欄位語意交給 daemon 判定（第 2、8 節）。
    """
    obj = {"op": op, "by": by or default_by()}
    if node is not None:
        obj["node"] = node
    if kill:
        obj["kill"] = True
    if rounds is not None:
        obj["rounds"] = rounds
    # 第 2、8 節：每件獨立命名，供 daemon 依檔名順序收取；不能覆寫成單一 ctl.json。
    name = "%d-%d.json" % (time.time_ns(), os.getpid())
    path = os.path.join(ctl_dir(root), name)
    write_json(path, obj)
    return path


def task_ctl(tdir, op, why="", by=None, reload=False):
    """在 tdir 寫 op／why 與 by（省略時由環境署名），回傳 ctl.json 路徑；I/O 失敗向外拋出。

    已有就覆寫、只留最後一個；reload 要求 restart 照 tasks.json 現在的同名項目（第 6 節、Q6）。
    不直接 kill，讓 tick／tock 在回合邊界執行（S-17）。
    """
    path = os.path.join(os.path.abspath(tdir), "ctl.json")
    obj = {"op": op, "by": by or default_by(), "why": why}
    if reload:
        obj["reload"] = True
    write_json(path, obj)
    return path


def main(argv=None):
    """解析 argv（None 用命令列），寫控制檔並印路徑；成功／help 回 0，參數錯回 1，I/O 例外外拋。"""
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
    t.add_argument("--reload", action="store_true", help="restart 照 node 現在 tasks.json 的同名項目（不是出生時的定義）")
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
        if a.reload and a.op != "restart":
            print("aos7-ctl: --reload 只給 restart", file=sys.stderr)
            return 1
        path = task_ctl(a.taskdir, a.op, a.why, a.by, a.reload)
    print(json.dumps({"wrote": path}, ensure_ascii=False))
    return 0
