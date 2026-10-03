"""aos7-tock：關一個回合——執行任務控制、補 lost、記結束、對活任務寫 tock.json、寫回合總結（spec.md 第 7 節）。

    aos7-tock <root> <node-id>
"""
import json
import os
import signal
import sys

import aos7_task
from aos7_fs import action_lock, append_jsonl, node_path, now, read_json, write_json


DEFAULT_KEEP_ENDED = 20


def keep_ended_rounds(node):
    """timeline.json 的 `keep_ended_rounds`（非負整數）；沒寫或不對用 20。"""
    t = read_json(os.path.join(node, ".aos", "timeline.json"), {})
    k = t.get("keep_ended_rounds") if isinstance(t, dict) else None
    return k if isinstance(k, int) and not isinstance(k, bool) and k >= 0 else DEFAULT_KEEP_ENDED


def tock(root, node_id, early=None):
    """做一次 tock，回本回合總結（即 rounds.jsonl 加的那一行）。early＝這次是不是提前進場（daemon 給；不知道是 None）。"""
    node = node_path(root, node_id)
    if not os.path.isfile(os.path.join(node, ".aos", "timeline.json")):
        # node 已經不在：什麼都不寫，免得把資料夾建回來（probes/subtimeline 1、rename N9）
        return {"round": None, "gone": True}
    with action_lock(root, node) as ok:
        if not ok:
            return {"round": None, "stale": True}   # 舊 daemon 的動作：不倒寫新 daemon 的回合（astra-4 I-01）
        return _tock(node, early)


def _tock(node, early):
    rpath = os.path.join(node, ".aos", "round.json")
    state = read_json(rpath, {})
    if not isinstance(state, dict):
        state = {}
    rnd = state.get("round", 0)
    if state.get("open") is False:
        # 這回合已經 tock 過（tick 被打斷沒開新回合、daemon 收尾又 tock 一次）：不再寫第二行總結（probes/nest3 N1）
        return {"round": rnd, "skipped": "round already closed"}
    at = now()

    ctl = list(state.get("ctl", [])) + aos7_task.run_all_ctl(node)

    keep = keep_ended_rounds(node)
    alive, ended, errors, marks, archived = [], [], [], [], []
    for tid in aos7_task.list_tasks(node):
        tdir = aos7_task.task_dir(node, tid)
        try:
            er = read_json(os.path.join(tdir, "ended.json"))
            if isinstance(er, dict) and isinstance(er.get("round"), int) and rnd - er["round"] > keep:
                # 結束超過 keep 回合：搬到 tasks-old/，之後 tick／tock／status 不再掃它（Q3）
                os.makedirs(aos7_task.old_dir(node), exist_ok=True)
                os.rename(tdir, os.path.join(aos7_task.old_dir(node), tid))
                archived.append(tid)
                continue
            st = aos7_task.task_state(tdir)
            if st == "lost":
                write_json(os.path.join(tdir, "exit.json"), {"code": None, "lost": True, "at": at, "round": rnd})
                st = "ended"
            if st == "ended":
                if not os.path.exists(os.path.join(tdir, "ended.json")):
                    ex = read_json(os.path.join(tdir, "exit.json"), {})
                    ex = ex if isinstance(ex, dict) else {}
                    rec = {"tid": tid, "name": aos7_task.name_of(tdir), "code": ex.get("code")}
                    if ex.get("lost"):
                        rec["lost"] = True
                    cd = read_json(os.path.join(tdir, "ctl-done.json"))
                    if isinstance(cd, dict) and cd.get("op") in ("kill", "restart"):
                        rec["by_ctl"] = {"op": cd.get("op"), "by": cd.get("by")}   # 被控制收掉的，不是自己結束（probes/lifecycle N-4）
                    ended.append(rec)
                    marks.append(tdir)
            else:
                alive.append(tid)
        except (OSError, ValueError, TypeError, AttributeError) as e:
            # 一個任務的資料夾壞掉，不拖垮同一條線的其他任務（astra-4 I-05）
            errors.append({"tid": tid, "phase": "scan", "err": repr(e)[:200]})

    summary = {"round": rnd, "tick_at": state.get("tick_at"), "tock_at": at,
               "started": state.get("started", []), "alive": alive, "ended": ended, "ctl": ctl,
               "mounts": state.get("mounts", []), "early": early}
    if state.get("tasks_error"):
        summary["tasks_error"] = state["tasks_error"]
    if os.environ.get("AOS7_INCOMPLETE"):
        summary["incomplete"] = os.environ["AOS7_INCOMPLETE"]   # 這回合的 tick 被逾時收掉（daemon 給）
    # tock.json 寫失敗只記錯，其他任務照收（astra-4 I-05 tockdirpeer）
    for tid in alive:
        try:
            write_json(os.path.join(aos7_task.task_dir(node, tid), "tock.json"), {"round": rnd, "at": at, "early": early})
        except OSError as e:
            errors.append({"tid": tid, "phase": "tock.json", "err": repr(e)[:200]})
    if errors:
        summary["errors"] = errors
    if archived:
        summary["archived"] = archived
    append_jsonl(os.path.join(node, ".aos", "rounds.jsonl"), summary)  # 一回合一行，不再一回合一檔（P-12、R-10）
    # 先寫總結，再在任務資料夾寫 ended.json：中途被殺時下次 tock 會再報一次（重複），不會永久漏掉（astra-4 I-03）
    for tdir in marks:
        try:
            write_json(os.path.join(tdir, "ended.json"), {"round": rnd})
        except OSError:
            pass
    state.update({"open": False, "tock_at": at})
    write_json(rpath, state)
    return summary


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("用法: aos7-tock <root> <node-id>", file=sys.stderr)
        return 1
    signal.signal(signal.SIGTERM, lambda *_: None)   # 同 tick：做完這回合再走（probes/nest3 N1）
    e = os.environ.get("AOS7_EARLY")
    print(json.dumps(tock(argv[0], argv[1], early=None if e is None else e == "1"), ensure_ascii=False))
    return 0
