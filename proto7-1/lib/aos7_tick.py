"""aos7-tick：開一個回合——round +1、執行任務控制、起任務，印一行 JSON 就結束，不等任務（spec.md 第 4 節）。

    aos7-tick <root> <node-id>
"""
import json
import os
import sys

import aos7_task
from aos7_fs import node_path, now, read_json, write_json


def load_items(node):
    """讀 tasks.json 的項目；壞掉當空表。"""
    t = read_json(os.path.join(node, ".aos", "tasks.json"), {})
    items = t.get("tasks") if isinstance(t, dict) else None
    return [i for i in (items or []) if isinstance(i, dict)]


def live_names(node):
    """活任務的 name 集合（keep 判斷用）。"""
    names = set()
    for tid in aos7_task.live_tasks(node):
        b = read_json(os.path.join(aos7_task.task_dir(node, tid), "birth.json"), {})
        names.add(b.get("name"))
    return names


def tick(root, node_id):
    """做一次 tick，回 {"round", "started", "ctl"}。"""
    node = node_path(root, node_id)
    rpath = os.path.join(node, ".aos", "round.json")
    rnd = read_json(rpath, {}).get("round", 0) + 1
    state = {"round": rnd, "open": True, "tick_at": now(), "tock_at": None, "started": [], "ctl": []}
    write_json(rpath, state)

    state["ctl"] = aos7_task.run_all_ctl(node)

    started = []
    sdir = os.path.join(node, ".aos", "spawn")
    for fn in sorted(os.listdir(sdir)) if os.path.isdir(sdir) else []:
        if not fn.endswith(".json"):
            continue
        item = read_json(os.path.join(sdir, fn))
        os.remove(os.path.join(sdir, fn))
        if isinstance(item, dict):
            started.append(aos7_task.start_task(root, node_id, item, rnd))

    names = live_names(node)
    for item in load_items(node):
        if rnd < item.get("from_round", 1):
            continue
        if item.get("mode", "each") == "keep" and item.get("name") in names:
            continue
        started.append(aos7_task.start_task(root, node_id, item, rnd))
        names.add(item.get("name"))

    state["started"] = started
    write_json(rpath, state)
    return {"round": rnd, "started": started, "ctl": state["ctl"]}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("用法: aos7-tick <root> <node-id>", file=sys.stderr)
        return 1
    r = tick(argv[0], argv[1])
    print(json.dumps({"round": r["round"], "started": r["started"]}, ensure_ascii=False))
    return 0
