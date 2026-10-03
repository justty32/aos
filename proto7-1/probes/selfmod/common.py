"""selfmod 任務腳本共用：找 lib、讀寫自己 node 的 tasks.json。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))
import aos7_fs as fs  # noqa: E402,F401

NODE = os.environ.get("AOS7_NODE", "")
TASK = os.environ.get("AOS7_TASK", "")
TID = os.environ.get("AOS7_TID", "")
TASKS = os.path.join(NODE, ".aos", "tasks.json")


def bump(name):
    """<node>/<name> 計數 +1，回新值（看任務被起了幾次）。"""
    p = os.path.join(NODE, name)
    n = (fs.read_json(p, 0) or 0) + 1
    fs.write_json(p, n)
    return n


def edit_tasks(fn):
    """讀改寫自己 node 的 tasks.json（沒有鎖：這就是要量的 lost update）。"""
    t = fs.read_json(TASKS, {}) or {}
    t["tasks"] = fn(t.get("tasks") or [])
    fs.write_json(TASKS, t)
