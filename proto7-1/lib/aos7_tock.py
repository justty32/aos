"""aos7-tock：關一個回合——執行任務控制、補 lost、記結束、對活任務寫 tock.json、寫回合總結（spec.md 第 7 節）。

    aos7-tock <root> <node-id>
"""
import json
import os
import signal
import sys

import aos7_task
from aos7_fs import action_lock, append_jsonl, now, read_json, tail_jsonl, write_json
from aos7_tick import held_node


DEFAULT_KEEP_ENDED = 20


def keep_ended_rounds(node):
    """timeline.json 的 `keep_ended_rounds`（非負整數）；沒寫或不對用 20。"""
    t = read_json(os.path.join(node, ".aos", "timeline.json"), {})
    k = t.get("keep_ended_rounds") if isinstance(t, dict) else None
    return k if isinstance(k, int) and not isinstance(k, bool) and k >= 0 else DEFAULT_KEEP_ENDED


def tock(root, node_id, early=None):
    """做一次 tock，回本回合總結（即 rounds.jsonl 加的那一行）。early＝這次是不是提前進場（daemon 給；不知道是 None）。

    整個動作抓著 node 目錄的 fd 寫（astra-5 F-09）：中途被搬走寫到新位置，被刪掉就收手印 gone。"""
    def act(fnode, node):
        with action_lock(root, fnode) as ok:
            if not ok:
                return {"round": None, "stale": True}   # 舊 daemon 的動作：不倒寫新 daemon 的回合（astra-4 I-01）
            return _tock(fnode, early)
    return held_node(act, root, node_id, {"round": None, "gone": True})


def logged_summary(node, rnd, k=5):
    """rounds.jsonl 最後幾行裡第 rnd 回合的總結（同回合重做的 tock 用來去重；astra-5 F-05）；沒有回 None。"""
    for row in reversed(tail_jsonl(os.path.join(node, ".aos", "rounds.jsonl"), k)):
        if isinstance(row, dict) and row.get("round") == rnd and not isinstance(row.get("round"), bool):
            return row
    return None


def torn_tail(path):
    """rounds.jsonl 檔尾沒有換行結尾時，回那段半行的位元組數；正常回 0。"""
    try:
        with open(path, "rb") as f:
            end = f.seek(0, os.SEEK_END)
            if not end:
                return 0
            back = min(end, 1 << 20)
            f.seek(end - back)
            tail = f.read(back)
    except OSError:
        return 0
    return 0 if tail.endswith(b"\n") else len(tail) - (tail.rfind(b"\n") + 1)


def _tock(node, early):
    rpath = os.path.join(node, ".aos", "round.json")
    state = read_json(rpath, {})
    if not isinstance(state, dict):
        state = {}
    rnd = state.get("round", 0)
    bad_round = None
    if not isinstance(rnd, int) or isinstance(rnd, bool):
        # round.json 被寫壞（tick 之後才壞的）：從 rounds.jsonl 接著數，總結不寫非整數的 round（probes/chaos B6）
        bad_round, rnd = rnd, (aos7_task.last_logged_round(node) or 0) + 1
        state["round"] = rnd
    if state.get("open") is False:
        # 這回合已經 tock 過（tick 被打斷沒開新回合、daemon 收尾又 tock 一次）：不再寫第二行總結（probes/nest3 N1）
        return {"round": rnd, "skipped": "round already closed"}
    prior = logged_summary(node, rnd)
    if prior is not None:
        return _replayed(node, rpath, state, rnd, prior)
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
    if bad_round is not None:
        summary["tasks_error"] = list(summary.get("tasks_error") or []) + [
            "round.json 的 round 壞了（%r），從 rounds.jsonl 接成 %d" % (bad_round, rnd)]
    if os.environ.get("AOS7_INCOMPLETE"):
        summary["incomplete"] = os.environ["AOS7_INCOMPLETE"]   # daemon 給：tick 被逾時收掉＝"tick"；上一段沒關的回合＝"unclosed"
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
    rpath_l = os.path.join(node, ".aos", "rounds.jsonl")
    torn = torn_tail(rpath_l)
    if torn:
        # 上次 append 中途被殺留下的半行：append_jsonl 先補換行（半行留著當證據，讀的人跳過），總結記一筆（astra-6 G-08）
        summary["errors"] = list(summary.get("errors") or []) + [
            {"tid": None, "phase": "rounds.jsonl", "err": "檔尾有沒寫完的一行（%d bytes），已補換行、保留原樣" % torn}]
    append_jsonl(rpath_l, summary)  # 一回合一行，不再一回合一檔（P-12、R-10）
    if logged_summary(node, rnd) is None:
        # 總結沒有完整提交（讀不回這回合的一行）：不寫 ended.json、不關回合，下次 tock 重來（astra-6 G-08）
        raise OSError("rounds.jsonl 讀不回第 %d 回合的總結，沒寫 ended.json、回合沒關" % rnd)
    # 先寫總結，再在任務資料夾寫 ended.json：中途被殺時下次 tock 會再報一次（重複），不會永久漏掉（astra-4 I-03）
    for tdir in marks:
        try:
            write_json(os.path.join(tdir, "ended.json"), {"round": rnd})
        except OSError:
            pass
    state.update({"open": False, "tock_at": at})
    write_json(rpath, state)
    return summary


def _replayed(node, rpath, state, rnd, prior):
    """這回合的總結已經在 rounds.jsonl（上一次 tock 寫完總結後被殺：逾時、kill -9）：不寫第二行，只把沒做完的收尾做完——
    總結裡報過 ended 的任務補 ended.json（沒報過的留給下一回合報，不會漏）、總結裡 alive 的補這回合的 tock.json、round.json 關上並標
    `incomplete`（daemon 給的原因，沒給是 "tock"）與 `replayed: true`（astra-5 F-05）。回 prior 加 `replayed: true`。"""
    for rec in prior.get("ended") or []:
        tid = rec.get("tid") if isinstance(rec, dict) else None
        if not isinstance(tid, str) or "/" in tid or tid.startswith("."):
            continue
        tdir = aos7_task.task_dir(node, tid)
        try:
            if os.path.isdir(tdir) and not os.path.exists(os.path.join(tdir, "ended.json")):
                write_json(os.path.join(tdir, "ended.json"), {"round": rnd})
        except OSError:
            pass
    for tid in prior.get("alive") or []:
        # 被殺前可能還沒寫到它：補這回合的 tock.json（已經是這回合的就不動）
        if not isinstance(tid, str) or "/" in tid or tid.startswith("."):
            continue
        tp = os.path.join(aos7_task.task_dir(node, tid), "tock.json")
        old = read_json(tp)
        if os.path.isdir(os.path.dirname(tp)) and not (isinstance(old, dict) and old.get("round") == rnd):
            try:
                write_json(tp, {"round": rnd, "at": prior.get("tock_at") or now(), "early": prior.get("early")})
            except OSError:
                pass
    state.update({"open": False, "tock_at": prior.get("tock_at") or now(), "replayed": True,
                  "incomplete": os.environ.get("AOS7_INCOMPLETE") or "tock"})
    write_json(rpath, state)
    return dict(prior, replayed=True)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("用法: aos7-tock <root> <node-id>", file=sys.stderr)
        return 1
    signal.signal(signal.SIGTERM, lambda *_: None)   # 同 tick：做完這回合再走（probes/nest3 N1）
    e = os.environ.get("AOS7_EARLY")
    print(json.dumps(tock(argv[0], argv[1], early=None if e is None else e == "1"), ensure_ascii=False))
    return 0
