"""aos7-tock <root> <node-id>：關一個回合（spec.md 第 7 節）——任務控制、判定每個槽、寫總結 last-round.json、通知活任務
（tock.json）、補 seen_round、刪該刪的槽、關 round.json。先留下可恢復的總結、再清理：總結寫完並整份讀回確認，才通知任務
（任務收到 tock 時總結一定已經是這回合的）；中途被殺，下一次照 round.json＋last-round.json 重播收尾。
退出碼：0＝做了（或 gone／stale／skipped）；3＝不知道（回合判不出、總結讀不到或讀回確認不了、列不出槽、看不到 node…；回合沒關）。
"""
import json
import os
import shutil
import signal
import sys

import aos7_task
from aos7_fs import (N, OK, U, ROUND_OPEN, ROUND_CLOSED, ROUND_NONE, Unknown, action_lock, errname, fact, hold, is_int, now,
                     read_json, read_round, summary_ok, sweep_tmp, test_point, write_json)
from aos7_task import ENDED, EMPTY, LIVE, UNKNOWN
from aos7_tick import held_node, table_slots


def tock(root, node_id, early=None):
    """收一個回合，回總結（或 gone／stale／skipped）；推定不了丟 Unknown。early＝daemon 說這回合是不是提前收的。
    tock 不收掉任務：任務可以跨回合。"""
    root = os.path.realpath(root)

    def act(fnode, node):
        with action_lock(root, fnode) as ok:
            return _tock(root, node_id, node, fnode, early) if ok else {"round": None, "stale": True}
    return held_node(act, root, node_id, {"round": None, "gone": True})


def _kind(e):
    return getattr(e, "kind", type(e).__name__)


def _tell(fslot, rec, who):
    """寫一份 tock.json；寫不進去回一筆紀錄（hold 格式，帶 slot／run／round），寫成回 None。"""
    try:
        write_json(os.path.join(fslot, "tock.json"), rec)
    except OSError as e:
        return hold("tock.json", errname(e), repr(e), **who)


def _tock(root, node_id, node, fnode, early):
    """動作鎖內收回合。"""
    rpath = os.path.join(fnode, ".aos", "round.json")
    lpath = os.path.join(fnode, ".aos", "last-round.json")
    sweep_tmp(os.path.join(fnode, ".aos"))
    st, state, why = read_round(rpath)
    if st == ROUND_NONE:
        return {"round": None, "skipped": "no round.json"}
    if st == ROUND_CLOSED:
        return {"round": state["round"], "skipped": "round already closed"}
    if st != ROUND_OPEN:
        raise Unknown(why, kind="round-unknown")
    lst, lr = fact(lpath)
    if lst == U:
        raise Unknown("%s，判斷不了這回合總結寫過沒" % lr)
    rnd = state["round"]
    # 上次寫完總結就被殺：照那份完整的總結重播收尾（不重算，免得已補過 seen_round 的結束就此不見）。
    # 壞掉或不完整的總結（tock 是它唯一的寫者）照常重新產生，不丟任何東西
    if lst == OK and summary_ok(lr) and lr["round"] == rnd:
        return _replayed(root, node_id, node, fnode, rpath, state, rnd, lr)
    slots, lerr = aos7_task.list_slots(fnode)
    if lerr:
        raise Unknown("列不出 .aos/tasks/：%s" % lerr, kind="listdir")
    at = now()
    ctl = list(state.get("ctl") or []) + aos7_task.run_all_ctl(aos7_task.Ctx(root, node_id, node, fnode, rnd))
    alive, ended, errors, marks, views = [], [], [], [], {}
    for slot in slots:
        fslot = aos7_task.slot_dir(fnode, slot)
        for d in (fslot, os.path.join(fslot, "mount-req"), os.path.join(fslot, "mount-done")):
            sweep_tmp(d)   # 基礎設施資料夾裡寫者已死的暫存檔（不遞迴清任務自己的資料夾）
        try:
            v = aos7_task.judge_resolved(fslot, node, slot, rnd)
        except Exception as e:   # noqa: BLE001  一個槽出事只記它，其他照做
            errors.append(hold("judge", _kind(e), repr(e), slot=slot))
            continue
        views[slot] = v
        if v.state == ENDED and aos7_task.unreported(v):
            ended.append(aos7_task.ended_record(v, fslot))
            marks.append((slot, v))
        elif v.state == LIVE:
            alive.append(aos7_task.run_id(slot, v.run if v.run is not None else "?"))
            if v.get("unsure"):   # 保守當活的也進 errors，不要「停著卻看似正常」
                errors.append(hold("judge", "unsure", v["unsure"], slot=slot))
        elif v.state == UNKNOWN:
            errors.append(hold("judge", "unknown", v.get("why"), slot=slot))
    # tick 重用槽前先記下的結束（tock 之後才結束的 run）也要報；照 run id 去重
    seen = {e["run"] for e in ended}
    ended = [e for e in state.get("reaped") or [] if isinstance(e, dict) and e.get("run") not in seen] + ended
    summary = {"round": rnd, "tick_at": state.get("tick_at"), "tock_at": at, "early": early,
               "started": state.get("started") or [], "alive": alive, "ended": ended,
               "skipped": state.get("skipped") or [], "ctl": ctl, "mounts": state.get("mounts") or [],
               "tasks_error": list(state.get("tasks_error") or []), "errors": errors, "tasks_rev": state.get("tasks_rev")}
    if os.environ.get("AOS7_INCOMPLETE"):
        summary["incomplete"] = os.environ["AOS7_INCOMPLETE"]
    write_json(lpath, summary)
    test_point("tock-summary")
    st2, back = fact(lpath)
    if not (st2 == OK and back == json.loads(json.dumps(summary, ensure_ascii=False))):   # 整份比對
        raise Unknown("last-round.json 讀回確認不了第 %d 回合（%s），回合沒關，下次 tock 重來" % (rnd, st2), kind="readback")
    # 總結提交之後才通知；寫不進去的記在 round.json 的 notify_errors（總結已提交，不改它），不跨回合補送（spec §7）
    notify_err = [e for e in (_tell(aos7_task.slot_dir(fnode, s), {"run": v.run, "round": rnd, "at": at, "early": early},
                                    {"slot": s, "run": v.run, "round": rnd})
                              for s, v in views.items() if v.state == LIVE and v.run is not None) if e]
    _finish(fnode, rnd, marks, views)
    test_point("tock-after-finish")
    state.update({"open": False, "tock_at": at})   # 這一步之後 daemon 才准下一次 tick
    if notify_err:
        state["notify_errors"] = notify_err
    write_json(rpath, state)
    return summary


def _finish(fnode, rnd, marks, views):
    """總結提交後收尾：已報的結束補 seen_round；刪「名字不在表上、已結束而且結束早一回合就報過（once 的結果至少留完整一回合）」
    與空的槽。表讀不到或讀不懂＝不知道哪些名字還在，不刪。補不上、刪不掉的下次再來（重複報不會漏）。"""
    for slot, v in marks:
        path = os.path.join(aos7_task.slot_dir(fnode, slot), "exit.json")
        ex = read_json(path)
        if isinstance(ex, dict) and ex.get("run") == v.run and not is_int(ex.get("seen_round")):
            ex["seen_round"] = rnd
            try:
                write_json(path, ex)
                test_point("tock-seen-round")
            except OSError:
                pass
    st, t = fact(os.path.join(fnode, ".aos", "tasks.json"))
    if st == N:
        table = set()
    elif st == OK and isinstance(t, dict) and isinstance(t.get("tasks"), list):
        table = table_slots([i for i in t["tasks"] if isinstance(i, dict)])
    else:
        return
    for slot, v in views.items():
        seen_round = (v.get("exit") or {}).get("seen_round")
        if slot not in table and (v.state == EMPTY or (v.state == ENDED and is_int(seen_round) and seen_round < rnd)):
            shutil.rmtree(aos7_task.slot_dir(fnode, slot), ignore_errors=True)


def _replayed(root, node_id, node, fnode, rpath, state, rnd, prior):
    """同回合已有完整總結：不重寫，只把收尾做完——ended 裡的補 seen_round、alive 裡沒收到這回合 tock.json 的補寫、關回合
    並標 replayed。列不出槽＝收尾做不了，回合先不關；補不上的通知記進 notify_errors，不吞掉。回總結加 replayed。"""
    slots, lerr = aos7_task.list_slots(fnode)
    if lerr:
        raise Unknown("列不出 .aos/tasks/：%s（重播收尾做不了，回合先不關）" % lerr)
    reported = {e.get("run") for e in prior.get("ended") or [] if isinstance(e, dict)}
    alive = set(x for x in prior.get("alive") or [] if isinstance(x, str))
    owed = {sl: int(r) for sl, _, r in (x.rpartition("#") for x in alive) if r.isdigit()}
    marks, views, notify_err = [], {}, []
    for slot in slots:
        fslot = aos7_task.slot_dir(fnode, slot)
        try:
            v = aos7_task.judge(fslot, node, slot, rnd)
        except Exception as e:   # noqa: BLE001
            if slot in owed:
                notify_err.append(hold("judge", _kind(e), repr(e), slot=slot, run=owed[slot], round=rnd))
            continue
        views[slot] = v
        rid = aos7_task.run_id(slot, v.run)
        if v.state == ENDED and rid in reported:
            marks.append((slot, v))
        if slot in owed and v.state == UNKNOWN:
            notify_err.append(hold("judge", "unknown", "槽判不出，tock.json 沒補：%s" % v.get("why"), slot=slot,
                                   run=owed[slot], round=rnd))
        old = read_json(os.path.join(fslot, "tock.json"))
        if rid in alive and v.run is not None and not (isinstance(old, dict) and old.get("round") == rnd
                                                       and old.get("run") == v.run):
            err = _tell(fslot, {"run": v.run, "round": rnd, "at": prior.get("tock_at") or now(), "early": prior.get("early")},
                        {"slot": slot, "run": v.run, "round": rnd})
            if err:
                notify_err.append(err)
    # 這次才補 seen_round 的結束，還不算「早一回合報過」，不拿來刪槽
    _finish(fnode, rnd, marks, {s: v for s, v in views.items()
                                if v.state != ENDED or is_int((v.get("exit") or {}).get("seen_round"))})
    state.update({"open": False, "tock_at": prior.get("tock_at") or now(), "replayed": True,
                  "incomplete": os.environ.get("AOS7_INCOMPLETE") or "tock"})
    if notify_err:
        state["notify_errors"] = notify_err
    write_json(rpath, state)
    return dict(prior, replayed=True, **({"notify_errors": notify_err} if notify_err else {}))


def main(argv=None):
    """命令列入口；退出碼見檔頭。"""
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
    print(json.dumps(r, ensure_ascii=False))
    return 0
