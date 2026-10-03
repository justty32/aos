"""aos7-tock：關一個回合——執行任務控制、補 lost、記結束、對活任務寫 tock.json、寫回合總結（spec.md 第 7 節）。

    aos7-tock <root> <node-id>
"""
import json
import os
import sys

import aos7_task
from aos7_fs import append_jsonl, node_path, now, read_json, write_json


def tock(root, node_id):
    """做一次 tock，回本回合總結（即 rounds.jsonl 加的那一行）。"""
    node = node_path(root, node_id)
    rpath = os.path.join(node, ".aos", "round.json")
    state = read_json(rpath, {})
    rnd = state.get("round", 0)
    at = now()

    ctl = list(state.get("ctl", [])) + aos7_task.run_all_ctl(node)

    alive, ended = [], []
    for tid in aos7_task.list_tasks(node):
        tdir = aos7_task.task_dir(node, tid)
        st = aos7_task.task_state(tdir)
        if st == "lost":
            write_json(os.path.join(tdir, "exit.json"), {"code": None, "lost": True, "at": at, "round": rnd})
            st = "ended"
        if st == "ended":
            if not os.path.exists(os.path.join(tdir, "ended.json")):
                ex = read_json(os.path.join(tdir, "exit.json"), {})
                write_json(os.path.join(tdir, "ended.json"), {"round": rnd})
                rec = {"tid": tid, "code": ex.get("code")}
                if ex.get("lost"):
                    rec["lost"] = True
                ended.append(rec)
        else:
            write_json(os.path.join(tdir, "tock.json"), {"round": rnd, "at": at})
            alive.append(tid)

    summary = {"round": rnd, "tick_at": state.get("tick_at"), "tock_at": at,
               "started": state.get("started", []), "alive": alive, "ended": ended, "ctl": ctl,
               "mounts": state.get("mounts", [])}
    append_jsonl(os.path.join(node, ".aos", "rounds.jsonl"), summary)  # 一回合一行，不再一回合一檔（P-12、R-10）
    state.update({"open": False, "tock_at": at})
    write_json(rpath, state)
    return summary


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("用法: aos7-tock <root> <node-id>", file=sys.stderr)
        return 1
    print(json.dumps(tock(argv[0], argv[1]), ensure_ascii=False))
    return 0
