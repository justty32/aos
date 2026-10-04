"""aos7-tock：關一個回合——執行任務控制、判定每個槽（疑似 lost 先身分掃描）、對活任務寫 tock.json、覆寫 last-round.json、
補 seen_round、刪該刪的槽、關 round.json（spec.md 第 7 節）。

    aos7-tock <root> <node-id>

由 daemon 在 interval 到時、提前收回合或恢復未關回合時呼叫（spec §2.1～2.2；S-08、S-11）。
讀 .aos/round.json、last-round.json、tasks.json 與槽的 birth／pid／exit／ctl；
寫 last-round.json、round.json、exit.json 的 seen_round、活槽的 tock.json，任務控制另寫回條／表。
共用 action.lock 並讀 .aosd/gen.json、寫 .aos/action.owner.json（spec §2.5）。
這裡是「先留下可恢復的總結、再清理」的提交點，核心只保留上一次（spec §0、§7～8）。

退出碼：0＝做了（或 gone／stale／skipped，stdout 說明）；1＝last-round.json 讀回確認不了（回合沒關，下次重來）；
3＝不知道（round.json 讀不到或內容不完整、last-round.json 讀不到、列不出槽、gen.json 不能用、看不到 node；什麼都沒寫，A2-02）。
順序：總結提交（寫＋整份讀回）→ 通知活任務（tock.json，A2-12）→ 補 seen_round／刪槽 → 關 round.json。
起點是 proto7-1 lib/aos7_tock.py；rounds.jsonl、tasks-old、ended.json 拿掉，改成只留上一次（last-round.json＋exit.json 的 seen_round）。
"""
import json
import os
import shutil
import signal
import sys

import aos7_task
from aos7_fs import (MISSING, OK, ROUND_OPEN, ROUND_CLOSED, ROUND_NONE, action_lock, is_int, now, read_json, read_json3,
                     read_round, summary_ok, sweep_tmp, test_point, write_json)
from aos7_task import ENDED, EMPTY, LIVE, UNKNOWN
from aos7_tick import Unknown, held_node, table_slots
from aos7_fs import IO


def tock(root, node_id, early=None):
    """替 root 空間的 node_id 收一回合，early 是 daemon 給的提前進場值（可為 None）。
    回本回合總結，或 gone／stale／skipped 結果；不確定丟 Unknown，確認總結失敗丟 ReadBack。
    此入口持有 node fd 並拿動作鎖；任務可以跨回合，不因 tock 而結束（spec §2.5、§7；S-11）。"""
    root = os.path.realpath(root)   # 同 tick（A2-04）

    def act(fnode, node):
        """以持有的 fnode 及原路徑 node 執行鎖內 tock，回總結或 stale 結果。
        拿鎖後確認世代，舊世代不寫回合，避免覆蓋新 daemon 的動作（spec §2.5）。"""
        with action_lock(root, fnode) as ok:
            if not ok:
                return {"round": None, "stale": True}
            return _tock(root, node_id, node, fnode, early)
    return held_node(act, root, node_id, {"round": None, "gone": True})


class ReadBack(Exception):
    """last-round.json 讀回確認不了。"""


def _tock(root, node_id, node, fnode, early):
    """在動作鎖內收回合，回總結或 skipped；root／node_id／node／fnode 定位空間與原目錄。
    early 寫入通知和總結；回合／總結讀不到或列槽失敗丟 Unknown，總結讀回不符丟 ReadBack。
    先提交總結才通知任務（tock.json）、標已報／刪槽、關回合，保留重做所需的證據（spec §7、§8 不變條件三；A2-12）。"""
    rpath = os.path.join(fnode, ".aos", "round.json")
    lpath = os.path.join(fnode, ".aos", "last-round.json")
    sweep_tmp(os.path.join(fnode, ".aos"))   # A2-07：拿著 action.lock 時清掉寫者已死的原子寫暫存檔
    # spec §2.2、§3；A2-02：只有 read_round 說 open 才收；壞掉／缺 open／讀不到＝不知道，不猜回合數（以前會用 last-round 接）。
    st, state, why = read_round(rpath)
    if st == ROUND_NONE:
        return {"round": None, "skipped": "no round.json"}     # P2-06：沒有回合可關
    if st == ROUND_CLOSED:
        out = {"round": state["round"], "skipped": "round already closed"}
        if state.get("notify_errors"):
            # A3-08：回合關上時有沒寫進去的 tock.json，再 tock 一次就補（權限恢復後人手跑 aos7-tock 也有用）
            left = retry_notify(fnode, node, state)
            state["notify_errors"] = left
            if not left:
                state.pop("notify_errors")
            write_json(rpath, state)
            out["notify_retried"] = True
            out["notify_errors"] = left
        return out
    if st != ROUND_OPEN:
        raise Unknown(why)
    lst, lr = read_json3(lpath, strict=True)   # A3-03：不是一般檔＝不知道，不當沒有總結去重新產生
    if lst == IO:
        raise Unknown("last-round.json 讀不到：%s，判斷不了這回合總結寫過沒" % lr)
    lr = lr if lst == OK else None
    rnd = state["round"]
    # spec §7：上次可能在總結落盤後被殺；依既有總結重播，避免重算 ended 使證據消失。
    # 只拿「完整的同回合總結」重播（summary_ok）；缺欄、型別錯的照常重新產生（註解疑點 aos7_tock.py:77）。
    if summary_ok(lr) and lr["round"] == rnd:
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
        sweep_tmp(fslot)
        # A3-07：mount-req／mount-done 也是基礎設施子目錄（任務與 tick 原子寫回條／請求），寫者死了留下的暫存檔一起清；
        # 不遞迴清任務自己的資料夾
        for sub in ("mount-req", "mount-done"):
            sweep_tmp(os.path.join(fslot, sub))
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
            # spec §5.4、P2-08：starttime／pid 讀不到以 LIVE＋unsure 保留；A2-08：原因也進總結 errors，不再「保守停著但看似正常」。
            alive.append(aos7_task.run_id(slot, v.run if v.run is not None else "?"))
            if v.get("unsure") or v.get("broken"):
                errors.append({"slot": slot, "phase": "unsure", "err": v.get("unsure") or v.get("why")})
        elif v.state == UNKNOWN:
            errors.append({"slot": slot, "phase": "judge", "err": v.get("why")})
    # spec §4.2、P2-03：tick 重用槽前先保存的舊結束也要報，以 run id 去重避免同次結束報兩份。
    seen = {e["run"] for e in ended}
    reaped = [e for e in state.get("reaped") or [] if isinstance(e, dict) and e.get("run") not in seen]
    ended = reaped + ended

    summary = {"round": rnd, "tick_at": state.get("tick_at"), "tock_at": at, "early": early,
               "started": state.get("started") or [], "alive": alive, "ended": ended,
               "skipped": state.get("skipped") or [], "ctl": ctl, "mounts": state.get("mounts") or [],
               "tasks_error": list(state.get("tasks_error") or []), "errors": errors,
               "tasks_rev": state.get("tasks_rev")}
    if os.environ.get("AOS7_INCOMPLETE"):
        summary["incomplete"] = os.environ["AOS7_INCOMPLETE"]
    # spec §7、§8 不變條件三：先存總結並讀回確認，才允許通知任務、標已報、清槽與關回合。
    write_json(lpath, summary)
    test_point("tock-summary")   # P2-15：在提交與收尾之間卡住／被殺，驗證下次只靠「上一次」就能恢復。
    st2, back = read_json3(lpath)
    if not (st2 == OK and back == json.loads(json.dumps(summary, ensure_ascii=False))):
        # 註解疑點 aos7_tock.py:130：整份比對，不只比 round／tock_at。
        raise ReadBack("last-round.json 讀回確認不了第 %d 回合（%s），回合沒關，下次 tock 重來" % (rnd, st2))
    # A2-12：tock.json 在總結提交之後才寫——任務（例如歷史 module）收到這回合的 tock 時，last-round.json 一定已經是這回合的。
    # 在這之前被殺：下次 tock 走重播，照總結的 alive 補寫沒收到的 tock.json。
    notify_err = _notify(fnode, rnd, at, early, views)
    _finish(fnode, rnd, marks, views)
    test_point("tock-after-finish")
    # spec §2.2 不變條件一：這一步關上後，daemon 才有依據准許下一次 tick。
    state.update({"open": False, "tock_at": at})
    if notify_err:
        state["notify_errors"] = notify_err
    write_json(rpath, state)
    return summary


def _notify(fnode, rnd, at, early, views):
    """對活任務寫 tock.json（S-11），回寫不進去的清單（記進 round.json 的 notify_errors；總結已經提交，不改它）。"""
    errs = []
    for slot, v in views.items():
        if v.state == LIVE and v.run is not None:
            try:
                write_json(os.path.join(aos7_task.slot_dir(fnode, slot), "tock.json"),
                           {"run": v.run, "round": rnd, "at": at, "early": early})
            except OSError as e:
                errs.append({"slot": slot, "run": v.run, "round": rnd, "phase": "tock.json", "err": repr(e)[:200]})
    return errs


def retry_notify(fnode, node, state):
    """A3-08：補寫 round.json `notify_errors` 記著、還欠的 tock.json。回還補不上的清單（每筆 {"slot","run","round","err"}）。

    每筆照槽現在的判定：同一個 run 還活著 → 補寫（那個槽的 tock.json 已經是這回合或更新的就不寫）；槽換了 run、已結束、
    或槽不在了 → 那份通知已經沒有對象，丟掉；判不出（UNKNOWN）或寫不進去 → 留著，下次再補。
    tick 開下一回合前、tock 遇到已關的回合時呼叫（拿著 action.lock）。state 不是物件或沒有 notify_errors 回 []。"""
    owed = state.get("notify_errors") if isinstance(state, dict) else None
    if not isinstance(owed, list):
        return []
    left = []
    for e in owed:
        if not (isinstance(e, dict) and isinstance(e.get("slot"), str) and is_int(e.get("run")) and is_int(e.get("round"))):
            continue   # 舊格式（沒有 run／round）補不了，也不留
        fslot = aos7_task.slot_dir(fnode, e["slot"])
        try:
            v = aos7_task.judge(fslot, node, e["slot"], e["round"])
        except Exception as ex:   # noqa: BLE001
            left.append(dict(e, err="判定失敗：%r" % (ex,)))
            continue
        if v.state == UNKNOWN:
            left.append(dict(e, err="槽判不出：%s" % v.get("why")))
            continue
        if v.state != LIVE or v.run != e["run"]:
            continue
        tp = os.path.join(fslot, "tock.json")
        old = read_json(tp)
        if isinstance(old, dict) and old.get("run") == e["run"] and is_int(old.get("round")) and old["round"] >= e["round"]:
            continue
        try:
            write_json(tp, {"run": e["run"], "round": e["round"], "at": state.get("tock_at") or now(),
                            "early": None, "late": True})
        except OSError as ex:
            left.append(dict(e, err=repr(ex)[:200]))
    return left


def _mark_seen(fslot, run, rnd):
    """替 fslot 的 exit.json 標記 run 已在 rnd 回合報過，無回傳值（None）。
    讀不到、不是物件、run 不符或已有整數 seen_round 都不寫，寫入 I/O 錯誤外拋。
    比對 run 避免重播舊回合時把新 run 誤標為已報（spec §5.1、§7）。"""
    path = os.path.join(fslot, "exit.json")
    ex = read_json(path)
    if isinstance(ex, dict) and ex.get("run") == run and not is_int(ex.get("seen_round")):
        ex["seen_round"] = rnd
        write_json(path, ex)


def _finish(fnode, rnd, marks, views):
    """提交總結後收尾：fnode 定位 node，rnd 是本回合，marks 是待標記配對，views 是槽判定。
    回 None；先補 seen_round，再刪不在表上且早一回合已報結束的槽，也清掉無損的空槽（spec §5.1、§7）。
    表讀不到／格式不合時不刪；標記或刪除 I/O 失敗容後重試，未知槽不當已結束。"""
    for slot, v in marks:
        try:
            _mark_seen(aos7_task.slot_dir(fnode, slot), v.run, rnd)
        except OSError:
            pass   # 補不上下次會再報一次（重複），不會漏
    st, t = read_json3(os.path.join(fnode, ".aos", "tasks.json"), strict=True)   # 被換成 FIFO＝不知道表上有誰，不刪
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
        # spec §5.1：嚴格小於本回合，讓 once 的結束至少留下完整一回合供任務讀取。
        done = v.state == ENDED and is_int(ex.get("seen_round")) and ex["seen_round"] < rnd
        if done or (v.state == EMPTY and not v.get("broken")):
            try:
                shutil.rmtree(aos7_task.slot_dir(fnode, slot))
                aos7_task.write_seen(fnode, slot, None)   # A3-01：槽刪了，它的控制完成證據也拿掉（ctl.json 跟著槽沒了）
            except OSError:
                pass


def _replayed(root, node_id, node, fnode, rpath, state, rnd, prior):
    """回 prior 總結加 replayed=True，只補收尾，不覆寫這回合的總結（spec §7）。
    root／node_id／node／fnode 是空間與路徑；rpath、state 是待關回合檔及內容，rnd 是回合數。
    prior 的 ended 用來補 seen_round，alive 用來補 tock；槽判定例外跳過，通知 I/O 失敗略過。
    恢復只依 round／last-round 兩份上次記錄，無須歷史檔（§8 不變條件三）。"""
    marks, views = [], {}
    slots, lerr = aos7_task.list_slots(fnode)
    if lerr:
        # 註解疑點 aos7_tock.py:185：列不出槽就補不了 seen_round／tock.json，不能照樣關回合。
        raise Unknown("列不出 .aos/tasks/：%s（重播收尾做不了，回合先不關）" % lerr)
    reported = {e.get("run") for e in prior.get("ended") or [] if isinstance(e, dict)}
    alive = set(x for x in prior.get("alive") or [] if isinstance(x, str))
    owed = {}   # 總結 alive 裡的 run：slot → run（A3-08：補不上的要留紀錄，不能吞掉）
    for x in alive:
        sl, _, r = x.rpartition("#")
        if r.isdigit():
            owed[sl] = int(r)
    notify_err = []
    for slot in slots:
        fslot = aos7_task.slot_dir(fnode, slot)
        try:
            v = aos7_task.judge(fslot, node, slot, rnd)
        except Exception as e:   # noqa: BLE001
            if slot in owed:
                notify_err.append({"slot": slot, "run": owed[slot], "round": rnd, "phase": "judge", "err": repr(e)[:200]})
            continue
        views[slot] = v
        rid = aos7_task.run_id(slot, v.run)
        if v.state == ENDED and rid in reported:
            marks.append((slot, v))
        if slot in owed and v.state == UNKNOWN:
            notify_err.append({"slot": slot, "run": owed[slot], "round": rnd, "phase": "judge",
                               "err": "槽判不出，tock.json 沒補：%s" % v.get("why")})
        if rid in alive and v.run is not None:
            tp = os.path.join(fslot, "tock.json")
            old = read_json(tp)
            if not (isinstance(old, dict) and old.get("round") == rnd and old.get("run") == v.run):
                try:
                    write_json(tp, {"run": v.run, "round": rnd, "at": prior.get("tock_at") or now(),
                                    "early": prior.get("early")})
                except OSError as e:
                    notify_err.append({"slot": slot, "run": v.run, "round": rnd, "phase": "tock.json",
                                       "err": repr(e)[:200]})
    # spec §7：本次才補 seen_round 的 View 還沒有舊標記，不拿它當作可刪的既報結束。
    _finish(fnode, rnd, marks, {s: v for s, v in views.items() if v.state != ENDED or
                                is_int((v.get("exit") or {}).get("seen_round"))})
    state.update({"open": False, "tock_at": prior.get("tock_at") or now(), "replayed": True,
                  "incomplete": os.environ.get("AOS7_INCOMPLETE") or "tock"})
    if notify_err:
        # A3-08：跟正常收尾一樣記在 round.json 的 notify_errors（總結已提交、不改它）；下一個 tick／再一次 tock 會補（retry_notify）
        state["notify_errors"] = notify_err
    write_json(rpath, state)
    out = dict(prior, replayed=True)
    if notify_err:
        out["notify_errors"] = notify_err
    return out


def main(argv=None):
    """解析 argv（None 用命令列）的 root／node-id，讀 AOS7_EARLY 後跑 tock、印總結 JSON。
    回 0 表示完成或略過，1 表示用法或讀回失敗，3 表示 Unknown（spec §7、P2-09）。"""
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
