#!/usr/bin/env python3
"""通用 kernel 的身體（N-42 第二種，基礎實作）：判斷交給「判官」——表上一格 aos-inst TARGET（規則腳本或 agent）。
一拍＝跑一次本程式，由 aos-loop 拍（loop 掛在 aos-daemon 底下）。閘門照舊用 aos_gate.py，`mailbox` 指到這裡的信箱，
信（＝那張 inst 本身）與回信的形狀同第一種（aos_mailbox）。純標準庫。說明在同資料夾 kernel2.md。

    python3 aos_kernel.py [--key 值 ...] [KERNEL.json | -]

設定：
    mailbox    信箱資料夾（同閘門的 mailbox；必填）
    state      state 窗（必填，N-19）：loop 骨架的 state／pid／runs／last_error／beat，加 kernel 的 queue、running、
               slots、budget、served、seen（每封信第一次看到的 runs）、judge_error、last_sig；判官的 stdin＝這份只留 queue／running／slots／budget
    slots      每種資源幾格 {"llm": 1, "cpu": 2, "human": 1}；純值 n＝{"llm": n}（沒寫＝1）。信的 `_metainfo.resource`
               沒寫或 "none"＝便宜的，不佔格、直接跑；寫了但這裡沒有＝回 ResourceUnknown
    judge      判官：TARGET 或內嵌 inst（沒寫＝一律用規則）。stdin＝state 窗的 queue、running、slots、budget（子集），
               stdout＝{"run": [id], "defer": [id], "reject": [{"id", "error": {code, msg}}]}（見 aos_kernel_judge）
    budget、aging_ticks、near_ms、log  同第一種（aos_gate_kernel.py）；budget 只管 llm 的信
    poll_ms    一拍之內多久看一次信箱與跑完的信（沒寫＝50）

一拍（＝一段忙碌期）：cur/ 殘信回 KernelRestarted → 反覆：收跑完的、回信、放格 → 讀 new/（過期、額度、便宜的直接跑）
→ 局面變了才決定（只有一封且有空格＝直接跑；否則問判官，判官這拍沒給合法答案＝這拍用第一種的規則——判官出錯只有這一條路，
  kernel 不數連錯、不停問：要連錯幾次就改口或停住，是判官格自己的事（C-53；10-15 使用者「都同意。」，盤點第 3 條））→ 照決定認領、起跑；判官挑完仍有空格＝補位（沒被 reject 的剩下的信照規則補滿，log reason＝backfill）
（一封一條執行緒、各自一支子程式）→ 沒有在跑的就結束這拍。格在那封的子程式結束時就放（human 格＝回信落檔或逾時）。

相依：aos_inst ← aos_mailbox（信：讀、認領、跑、回信、log）← aos_gate ← aos_gate_kernel（借 order、deadline）← aos_kernel_judge（判官：跑、讀答案、規則後援）← aos_kernel。
"""
import datetime
import json
import os
import sys
import threading
import time

import aos_cli
from aos_cli import CliError
from aos_cli import is_int as _int
from aos_ctl_state import write_json
from aos_gate_kernel import deadline
from aos_mailbox import claim, log, mailbox, read_letter, reply, run_letter
from aos_kernel_judge import ask_judge, decide_rules, resource

__all__ = ["FLAGS", "KernelError", "check", "main", "tick"]

FLAGS = ("mailbox", "state", "slots", "judge", "budget", "aging_ticks", "near_ms", "poll_ms", "log")


class KernelError(CliError):
    pass


def check(doc):
    """驗設定、補預設，回一份新的 dict。"""
    for k in ("mailbox", "state"):
        if not isinstance(doc.get(k), str):
            raise KernelError("WindowMissing" if k == "state" else "FieldType", "%s 要是路徑字串（必填），不是 %r" % (k, doc.get(k)))
    slots = doc.get("slots", 1)
    c = dict(doc, slots={"llm": slots} if _int(slots, 0) else slots, judge=doc.get("judge"),
             budget=doc.get("budget"), aging_ticks=doc.get("aging_ticks", 10), near_ms=doc.get("near_ms", 30000),
             poll_ms=doc.get("poll_ms", 50))
    if not (isinstance(c["slots"], dict) and all(isinstance(k, str) and _int(v, 0) for k, v in c["slots"].items())):
        raise KernelError("FieldType", "slots 要是 {資源: ≥0 的整數}，不是 %r" % (c["slots"],))
    for k, lo in (("aging_ticks", 1), ("near_ms", 0), ("poll_ms", 1)):
        if not _int(c[k], lo):
            raise KernelError("FieldType", "%s 要是 ≥%d 的整數，不是 %r" % (k, lo, c[k]))
    if not (c["budget"] is None or _int(c["budget"], 0)):
        raise KernelError("FieldType", "budget 要是非負整數或 null，不是 %r" % (c["budget"],))
    if not (c["judge"] is None or isinstance(c["judge"], (str, dict))):
        raise KernelError("FieldType", "judge 要是 TARGET 或一張 inst，不是 %r" % (c["judge"],))
    if not (c.get("log") is None or isinstance(c["log"], str)):
        raise KernelError("FieldType", "log 要是路徑字串，不是 %r" % (c["log"],))
    return c


def _waited_ms(doc, now):
    sent = doc.get("sent")
    return round((now - sent) * 1000) if isinstance(sent, (int, float)) and not isinstance(sent, bool) else None


def _log(cfg, rec):
    log(cfg.get("log"), dict(rec, t=round(time.time(), 3)))


# ---- 一拍 ----

def tick(cfg):
    """跑一拍（一段忙碌期），回摘要 dict。"""
    box = mailbox(cfg["mailbox"])
    st = read_letter(cfg["state"]) or {}
    n = (st.get("runs") if _int(st.get("runs"), 0) else 0) + 1
    seen = st.get("seen") if isinstance(st.get("seen"), dict) else {}
    today = datetime.date.today().isoformat()
    bud = st.get("budget") if isinstance(st.get("budget"), dict) else {}
    used = [bud.get("used", 0) if bud.get("day") == today else 0]
    last_sig, last_err = st.get("last_sig"), st.get("judge_error")
    count = {"asked": 0, "fallback": 0, "direct": 0, "skipped": 0}
    served, dropped, running, results, queue, busy, warned = [], [], {}, {}, {}, {}, []

    def window(word, now):
        """state 窗整份（loop 骨架的 state、pid、runs、last_error、beat＋kernel 的 key）；判官的 stdin 是它的子集。"""
        return {"state": word, "pid": os.getpid(), "runs": n, "last_error": None,
                "last_warning": warned[-1] if warned else None, "beat": round(now, 3),
                "served": st.get("served", 0) + len(served) if _int(st.get("served"), 0) else len(served),
                "budget": {"limit": cfg["budget"], "used": used[0], "day": today},
                "slots": {k: {"total": cfg["slots"][k], "used": busy.get(k, 0)} for k in cfg["slots"]},
                "running": {x: {"resource": resource(v[1]), "since": round(v[3], 3)} for x, v in running.items()},
                "queue": {x: {"priority": d.get("priority"), "_metainfo": d.get("_metainfo"),
                              "waited_runs": n - seen.get(x, n), "waited_ms": _waited_ms(d, now)} for x, d in queue.items()},
                "seen": seen, "judge_error": last_err, "last_sig": last_sig}

    def send(doc, rep):
        w = reply(doc, rep)                         # 回信寫不進去＝記進 state 窗的 last_warning（不寫 stderr）
        if w:
            warned.append(w)

    def drop(name, doc, code, msg, path):
        send(doc, {"error": {"code": code, "msg": msg}})
        os.remove(path)
        seen.pop(name, None)
        dropped.append({"letter": name, "error": code})
        _log(cfg, {"event": "drop", "runs": n, "letter": name, "resource": resource(doc), "error": code})

    def go(name, doc):
        t0 = time.monotonic()
        results[name] = run_letter(doc) + (round((time.monotonic() - t0) * 1000),)

    def start(name, doc, reason=None):
        path = claim(box, name)
        if path:
            th = threading.Thread(target=go, args=(name, doc), daemon=True)
            running[name] = (th, doc, path, time.time())
            th.start()
            _log(cfg, {"event": "start", "runs": n, "letter": name, "resource": resource(doc),
                       "priority": doc.get("priority"), "waited": n - seen.get(name, n), "reason": reason})
        return bool(path)

    for name in sorted(os.listdir(box["cur"])):              # 上一拍跑到一半的
        path = os.path.join(box["cur"], name)
        drop(name, read_letter(path) or {}, "KernelRestarted", "kernel 重起時這封跑到一半，不重跑（N-20）", path)

    while True:
        for name in [x for x, v in running.items() if not v[0].is_alive()]:     # 收跑完的、放格
            _, doc, path, _ = running.pop(name)
            rep, tokens, ms = results.pop(name)
            used[0] += tokens
            send(doc, rep)
            os.remove(path)
            rec = {"letter": name, "resource": resource(doc), "waited": n - seen.pop(name, n), "ms": ms,
                   "code": rep.get("code")}
            if "error" in rep:
                rec["error"] = rep["error"]["code"]
            served.append(rec)
            _log(cfg, dict(rec, event="done", runs=n))

        now, queue, started = time.time(), {}, False
        for name in sorted(os.listdir(box["new"])):          # 收信
            doc = read_letter(os.path.join(box["new"], name))
            if doc is None:
                continue
            seen.setdefault(name, n)
            k, dl = resource(doc), deadline(doc.get("priority"))
            why = None
            if dl is not None and dl <= now:
                why = ("DeadlineMissed", "deadline 已過，沒跑")
            elif k is not None and k not in cfg["slots"]:
                why = ("ResourceUnknown", "kernel 沒有 %r 這種資源的格" % k)
            elif k == "llm" and cfg["budget"] is not None and used[0] >= cfg["budget"]:
                why = ("BudgetExhausted", "今天的 token 額度用完了（%d／%d）" % (used[0], cfg["budget"]))
            if why:
                path = claim(box, name)
                if path:
                    drop(name, doc, why[0], why[1], path)
            elif k is None:
                started |= start(name, doc)                 # 便宜的：不佔格、不問判官
            else:
                queue[name] = doc

        busy = {k: 0 for k in cfg["slots"]}
        for _, doc, _, _ in running.values():
            if resource(doc) is not None:
                busy[resource(doc)] += 1
        free = {k: max(cfg["slots"][k] - busy[k], 0) for k in cfg["slots"]}
        sig = [sorted(queue), sorted(running), sorted(free.items())]
        sig = json.loads(json.dumps(sig))
        can_start = any(free[resource(d)] > 0 for d in queue.values())    # 排隊的信沒有一種資源有空格＝這拍什麼也起不了，不問判官
        if queue and can_start and sig != last_sig:
            last_sig = sig
            only = next(iter(queue)) if len(queue) == 1 else None
            snap = window("running", now)
            write_json(cfg["state"], snap)                  # 局面外顯（N-13）；判官的 stdin＝這份的子集
            if only and free[resource(queue[only])] > 0:
                how, dec = "direct", {"run": [only], "defer": [], "reject": []}
            elif cfg["judge"] is not None:
                try:
                    dec, how = ask_judge(cfg, snap, set(queue)), "judge"
                    last_err = None
                except ValueError as e:                     # 判官這拍沒給合法答案＝這拍用規則（唯一一條錯誤路徑）
                    last_err = str(e)
                    dec, how = decide_rules(queue, free, seen, n, now, cfg), "fallback"
            else:
                dec, how = decide_rules(queue, free, seen, n, now, cfg), "rules"
            count[{"judge": "asked", "rules": "fallback"}.get(how, how)] += 1
            for r in dec["reject"]:
                path = claim(box, r["id"])
                if path:
                    drop(r["id"], queue.pop(r["id"]), r["error"]["code"], r["error"]["msg"], path)
            left, run = dict(free), []
            for x in dec["run"]:                            # 超過空格的截掉
                k = resource(queue[x])
                if left[k] > 0:
                    left[k] -= 1
                    run.append(x)
            fill = []
            if how == "judge":                              # 補位：判官的 defer＝「不是我挑的」，空格仍空就照規則補（被 reject 的不補）
                rest = {x: d for x, d in queue.items() if x not in run}
                fill = decide_rules(rest, left, seen, n, now, cfg)["run"] if rest else []
            _log(cfg, {"event": "decide", "runs": n, "how": how, "run": run, "backfill": fill, "cut": len(dec["run"]) - len(run),
                       "reject": [r["id"] for r in dec["reject"]], "error": last_err if how == "fallback" else None})
            for x in run:
                started |= start(x, queue[x], "judge" if how == "judge" else how)
            for x in fill:
                started |= start(x, queue[x], "backfill")
        elif queue:
            count["skipped"] += 1
        if not running and not started:
            break
        time.sleep(cfg["poll_ms"] / 1000)

    live = set(os.listdir(box["new"]))
    seen = {k: v for k, v in seen.items() if k in live}
    queue = {k: v for k, v in queue.items() if k in live}
    busy = {}
    final = window("waiting", time.time())
    write_json(cfg["state"], final)
    return {"runs": n, "served": served, "dropped": dropped, "waiting": len(live), "budget": final["budget"],
            "judge": count}


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    try:
        doc, _, _, rest = aos_cli.config(args, FLAGS)
        if rest is not None:
            raise KernelError("Usage", "kernel 不收 `--`")
        aos_cli.emit(tick(check(doc)))
        return 0
    except CliError as e:
        aos_cli.error(e.code, e.msg)
        return 125
    except OSError as e:
        aos_cli.error("IoFailed", str(e))
        return 125


if __name__ == "__main__":
    sys.exit(main())
