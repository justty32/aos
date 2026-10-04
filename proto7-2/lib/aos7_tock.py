"""aos7-tock：關一個回合——執行任務控制、判定每個槽（疑似 lost 先身分掃描）、對活任務寫 tock.json、覆寫 last-round.json、
補 seen_round、刪該刪的槽、關 round.json（spec.md 第 7 節）。

    aos7-tock <root> <node-id>

退出碼：0＝做了（或 gone／stale／skipped，stdout 說明）；1＝last-round.json 讀回確認不了（回合沒關，下次重來）；
3＝round.json／last-round.json 讀不到、或列不出槽（不知道，什麼都沒寫）。
起點是 proto7-1 lib/aos7_tock.py；rounds.jsonl、tasks-old、ended.json 拿掉，改成只留上一次（last-round.json＋exit.json 的 seen_round）。
"""
import json
import os
import shutil
import signal
import sys

import aos7_task
from aos7_fs import IO, MISSING, OK, action_lock, is_int, now, read_json, read_json3, test_point, write_json
from aos7_task import ENDED, EMPTY, LIVE, UNKNOWN
from aos7_tick import Unknown, held_node, table_slots


def tock(root, node_id, early=None):
    """做一次 tock，回本回合總結（即 last-round.json 的內容）。early＝這次是不是提前進場（daemon 給）。"""
    root = os.path.abspath(root)

    def act(fnode, node):
        with action_lock(root, fnode) as ok:
            if not ok:
                return {"round": None, "stale": True}
            return _tock(root, node_id, node, fnode, early)
    return held_node(act, root, node_id, {"round": None, "gone": True})


class ReadBack(Exception):
    """last-round.json 讀回確認不了。"""


def _tock(root, node_id, node, fnode, early):
    rpath = os.path.join(fnode, ".aos", "round.json")
    lpath = os.path.join(fnode, ".aos", "last-round.json")
    st, state = read_json3(rpath)
    if st == IO:
        raise Unknown("round.json 讀不到：%s" % state)
    if st == MISSING:
        return {"round": None, "skipped": "no round.json"}
    bad_round = None
    if not isinstance(state, dict):
        state = {}
    if state.get("open") is False:
        return {"round": state.get("round"), "skipped": "round already closed"}
    lst, lr = read_json3(lpath)
    if lst == IO:
        raise Unknown("last-round.json 讀不到：%s，判斷不了這回合總結寫過沒" % lr)
    lr = lr if lst == OK and isinstance(lr, dict) else None
    rnd = state.get("round")
    if not is_int(rnd):
        # round.json 被寫壞（tick 之後才壞的）：從 last-round.json 接著數
        if lr is None or not is_int(lr.get("round")):
            raise Unknown("round.json 壞了，last-round.json 也不能用；請人寫回 round.json")
        bad_round, rnd = rnd, lr["round"] + 1
        state["round"] = rnd
    if lr is not None and lr.get("round") == rnd:
        return _replayed(root, node_id, node, fnode, rpath, state, rnd, lr)
    slots, lerr = aos7_task.list_slots(fnode)
    if lerr:
        raise Unknown("列不出 .aos/tasks/：%s" % lerr)
    at = now()
    ctx = aos7_task.Ctx(root, node_id, node, fnode, rnd)
    ctl = list(state.get("ctl") or []) + aos7_task.run_all_ctl(ctx)

    alive, ended, errors, marks, views = [], [], [], [], {}
    for slot in slots:
        fslot = aos7_task.slot_dir(fnode, slot)
        try:
            v = aos7_task.judge_resolved(fslot, node, slot, rnd)
        except Exception as e:   # noqa: BLE001  一個槽壞掉只記它，其他照做
            errors.append({"slot": slot, "phase": "judge", "err": repr(e)[:200]})
            continue
        views[slot] = v
        if v.state == ENDED:
            if aos7_task.unreported(v):
                ended.append(aos7_task.ended_record(v, fslot))
                marks.append((slot, v))
        elif v.state == LIVE:
            alive.append(aos7_task.run_id(slot, v.run if v.run is not None else "?"))
        elif v.state == UNKNOWN:
            errors.append({"slot": slot, "phase": "judge", "err": v.get("why")})
    seen = {e["run"] for e in ended}
    reaped = [e for e in state.get("reaped") or [] if isinstance(e, dict) and e.get("run") not in seen]
    ended = reaped + ended

    for slot, v in views.items():
        if v.state == LIVE and v.run is not None:
            try:
                write_json(os.path.join(aos7_task.slot_dir(fnode, slot), "tock.json"),
                           {"run": v.run, "round": rnd, "at": at, "early": early})
            except OSError as e:
                errors.append({"slot": slot, "phase": "tock.json", "err": repr(e)[:200]})

    summary = {"round": rnd, "tick_at": state.get("tick_at"), "tock_at": at, "early": early,
               "started": state.get("started") or [], "alive": alive, "ended": ended,
               "skipped": state.get("skipped") or [], "ctl": ctl, "mounts": state.get("mounts") or [],
               "tasks_error": list(state.get("tasks_error") or []), "errors": errors,
               "tasks_rev": state.get("tasks_rev")}
    if bad_round is not None:
        summary["tasks_error"].append("round.json 的 round 壞了（%r），從 last-round.json 接成 %d" % (bad_round, rnd))
    if os.environ.get("AOS7_INCOMPLETE"):
        summary["incomplete"] = os.environ["AOS7_INCOMPLETE"]
    write_json(lpath, summary)
    test_point("tock-summary")
    st2, back = read_json3(lpath)
    if not (st2 == OK and isinstance(back, dict) and back.get("round") == rnd and back.get("tock_at") == at):
        raise ReadBack("last-round.json 讀回確認不了第 %d 回合（%s），回合沒關，下次 tock 重來" % (rnd, st2))
    _finish(fnode, rnd, marks, views)
    state.update({"open": False, "tock_at": at})
    write_json(rpath, state)
    return summary


def _mark_seen(fslot, run, rnd):
    """exit.json 補 seen_round（這一次結束已經在第 rnd 回合的 last-round.json 報過）。"""
    path = os.path.join(fslot, "exit.json")
    ex = read_json(path)
    if isinstance(ex, dict) and ex.get("run") == run and not is_int(ex.get("seen_round")):
        ex["seen_round"] = rnd
        write_json(path, ex)


def _finish(fnode, rnd, marks, views):
    """總結提交之後才做：補 seen_round、刪掉該刪的槽（spec 5.1：名字不在表上、run 已結束、結束在更早的回合報過）。"""
    for slot, v in marks:
        try:
            _mark_seen(aos7_task.slot_dir(fnode, slot), v.run, rnd)
        except OSError:
            pass   # 補不上下次會再報一次（重複），不會漏
    st, t = read_json3(os.path.join(fnode, ".aos", "tasks.json"))
    if st == MISSING:
        table = set()
    elif st == OK and isinstance(t, dict) and isinstance(t.get("tasks"), list):
        table = table_slots([i for i in t["tasks"] if isinstance(i, dict)])
    else:
        return   # 表讀不到或讀不懂＝不知道哪些名字還在，不刪
    for slot, v in views.items():
        if slot in table:
            continue
        ex = v.get("exit") or {}
        done = v.state == ENDED and is_int(ex.get("seen_round")) and ex["seen_round"] < rnd
        if done or (v.state == EMPTY and not v.get("broken")):
            try:
                shutil.rmtree(aos7_task.slot_dir(fnode, slot))
            except OSError:
                pass


def _replayed(root, node_id, node, fnode, rpath, state, rnd, prior):
    """這回合的總結已經寫過（上一次 tock 寫完 last-round.json 就被殺）：不重寫，只把收尾做完——
    ended 裡的補 seen_round、alive 裡沒收到這回合 tock.json 的補寫、關 round.json 並標 `replayed: true`（spec 第 7 節）。"""
    marks, views = [], {}
    slots, _ = aos7_task.list_slots(fnode)
    reported = {e.get("run") for e in prior.get("ended") or [] if isinstance(e, dict)}
    alive = set(x for x in prior.get("alive") or [] if isinstance(x, str))
    for slot in slots:
        fslot = aos7_task.slot_dir(fnode, slot)
        try:
            v = aos7_task.judge(fslot, node, slot, rnd)
        except Exception:   # noqa: BLE001
            continue
        views[slot] = v
        rid = aos7_task.run_id(slot, v.run)
        if v.state == ENDED and rid in reported:
            marks.append((slot, v))
        if rid in alive and v.run is not None:
            tp = os.path.join(fslot, "tock.json")
            old = read_json(tp)
            if not (isinstance(old, dict) and old.get("round") == rnd and old.get("run") == v.run):
                try:
                    write_json(tp, {"run": v.run, "round": rnd, "at": prior.get("tock_at") or now(),
                                    "early": prior.get("early")})
                except OSError:
                    pass
    _finish(fnode, rnd, marks, {s: v for s, v in views.items() if v.state != ENDED or
                                is_int((v.get("exit") or {}).get("seen_round"))})
    state.update({"open": False, "tock_at": prior.get("tock_at") or now(), "replayed": True,
                  "incomplete": os.environ.get("AOS7_INCOMPLETE") or "tock"})
    write_json(rpath, state)
    return dict(prior, replayed=True)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("用法: aos7-tock <root> <node-id>", file=sys.stderr)
        return 1
    signal.signal(signal.SIGTERM, lambda *_: None)   # 同 tick：做完這回合再走
    e = os.environ.get("AOS7_EARLY")
    try:
        r = tock(argv[0], argv[1], early=None if e is None else e == "1")
    except Unknown as ex:
        print(json.dumps({"unknown": str(ex)}, ensure_ascii=False))
        print("aos7-tock: %s" % ex, file=sys.stderr)
        return 3
    except ReadBack as ex:
        print("aos7-tock: %s" % ex, file=sys.stderr)
        return 1
    print(json.dumps(r, ensure_ascii=False))
    return 0
