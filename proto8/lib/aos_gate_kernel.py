#!/usr/bin/env python3
"""LLM kernel 的身體（N-42 第一種，基礎實作）：一拍＝跑一次本程式，由 aos-loop 拍（loop 掛在 aos-daemon 底下）。
每拍看閘門（aos_gate.py）丟進信箱的信，挑下一封、真跑、寫回信。純標準庫。說明在同資料夾 kernel.md。

    python3 aos_gate_kernel.py [--key 值 ...] [KERNEL.json | -]

設定：
    mailbox      信箱資料夾（同閘門的 mailbox；必填）
    state        kernel 的 state 窗（必填，N-19）：loop 骨架的 state／pid／runs／last_error／beat，
                 加 seen（每封信第一次看到的 runs）、budget {limit, used, day}、served
    slots        一拍最多跑幾封（沒寫＝1；>1 時同一拍的幾封一起跑，等最慢的跑完這拍才結束）
    budget       一天的 token 額度（全局；沒寫或 null＝不限）。用量＝回信 stdout 最後一份的 usage.total_tokens，沒有＝0
    aging_ticks  每等幾拍升一級（沒寫＝10）
    near_ms      deadline 剩不到這麼久＝插隊（沒寫＝30000）
    log          選填：每處理一封往這個檔追加一行 JSON（給人看順序）

一拍：
1. cur/ 裡還有信＝上一拍跑到一半被收掉（kernel 重起）→ 回錯 KernelRestarted、刪信，不重跑（N-20）。
2. 讀 new/ 的信；deadline 已過＝回 DeadlineMissed、丟掉；額度見底＝全部回 BudgetExhausted。
3. 排序挑 slots 封：deadline 剩不到 near_ms 的插隊（越近越前）→ 有效級數高的先（low／normal／high＝-1／0／1，
   數字取正負號；有效級數＝級數＋等了幾拍 // aging_ticks）→ deadline 近的先 → `_metainfo.cost` 小的先（沒寫＝0）→ 先來後到。
4. 認領（new/ → cur/；被閘門撤走的跳過）、信本身就是 inst：填 stdout／stderr 旁檔、aos_inst.run() 跑、
   回信＝結果（N-30）、刪信（aos_mailbox.run_letter）。
stdout 一份 {"runs", "served", "dropped", "waiting", "budget"}。設定不對＝stderr 錯誤、退出 125。

相依：aos_inst ← aos_mailbox ← aos_gate ← aos_gate_kernel（也借 aos_ctl_state 的 write_json）。
"""
import datetime
import math
import os
import sys
import threading
import time

import aos_cli
import aos_gate
from aos_cli import CliError
from aos_cli import is_int as _int
from aos_ctl_state import write_json
from aos_mailbox import claim, log, mailbox, read_letter, reply, run_letter

__all__ = ["FLAGS", "KernelError", "check", "level", "main", "order", "tick"]

FLAGS = ("mailbox", "state", "slots", "budget", "aging_ticks", "near_ms", "log")


class KernelError(CliError):
    pass


def check(doc):
    """驗設定、補預設，回一份新的 dict。"""
    for k in ("mailbox", "state"):
        if not isinstance(doc.get(k), str):
            raise KernelError("WindowMissing" if k == "state" else "FieldType", "%s 要是路徑字串（必填），不是 %r" % (k, doc.get(k)))
    c = dict(doc, slots=doc.get("slots", 1), budget=doc.get("budget"),
             aging_ticks=doc.get("aging_ticks", 10), near_ms=doc.get("near_ms", 30000))
    for k, lo in (("slots", 1), ("aging_ticks", 1), ("near_ms", 0)):
        if not _int(c[k], lo):
            raise KernelError("FieldType", "%s 要是 ≥%d 的整數，不是 %r" % (k, lo, c[k]))
    if not (c["budget"] is None or _int(c["budget"], 0)):
        raise KernelError("FieldType", "budget 要是非負整數或 null，不是 %r" % (c["budget"],))
    if not (c.get("log") is None or isinstance(c["log"], str)):
        raise KernelError("FieldType", "log 要是路徑字串，不是 %r" % (c["log"],))
    return c


def level(pri):
    """priority 物件 → 級數：low／normal／high＝-1／0／1；數字取正負號；沒寫、不認得＝0。"""
    v = (pri or {}).get("level")
    if isinstance(v, str):
        return aos_gate.LEVELS.get(v.lower(), 0)
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return (v > 0) - (v < 0)
    return 0


def deadline(pri):
    """priority.deadline → epoch 秒或 None。字串＝ISO 8601（沒時區＝本機時間）；數字＝epoch 秒；壞的＝None。"""
    v = (pri or {}).get("deadline")
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    if isinstance(v, str):
        try:
            return datetime.datetime.fromisoformat(v.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
    return None


def _cost(meta):
    v = meta.get("cost") if isinstance(meta, dict) else None
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else 0


def order(letters, seen, now_tick, now, cfg):
    """[(名, 信)] → 照規則排好的 list（不含過期的；呼叫前先剔掉）。"""
    near = cfg["near_ms"] / 1000

    def key(item):
        name, doc = item
        pri = doc.get("priority")
        dl = deadline(pri)
        eff = level(pri) + (now_tick - seen.get(name, now_tick)) // cfg["aging_ticks"]
        jump = dl is not None and dl - now <= near
        return (0 if jump else 1, dl if jump else 0, -eff, dl if dl is not None else math.inf,
                _cost(doc.get("_metainfo")), name)
    return sorted(letters, key=key)


def tick(cfg):
    """跑一拍，回這拍的摘要 dict。"""
    box = mailbox(cfg["mailbox"])
    st = read_letter(cfg["state"]) or {}
    n = (st.get("runs") if _int(st.get("runs"), 0) else 0) + 1
    seen = st.get("seen", {}) if isinstance(st.get("seen"), dict) else {}
    today = datetime.date.today().isoformat()
    bud = st.get("budget") if isinstance(st.get("budget"), dict) else {}
    used = bud.get("used", 0) if bud.get("day") == today else 0
    now = time.time()
    served, dropped = [], []

    def drop(name, doc, code, msg, path):
        reply(doc, {"error": {"code": code, "msg": msg}})
        os.remove(path)
        seen.pop(name, None)
        dropped.append({"letter": name, "error": code})
        log(cfg.get("log"), {"runs": n, "letter": name, "priority": doc.get("priority"), "error": code,
                   "sent": doc.get("sent")})

    for name in sorted(os.listdir(box["cur"])):              # 1. 上一拍跑到一半的
        path = os.path.join(box["cur"], name)
        drop(name, read_letter(path) or {}, "KernelRestarted", "kernel 重起時這封跑到一半，不重跑（N-20）", path)

    letters = []
    for name in sorted(os.listdir(box["new"])):              # 2. 收信、過期、額度
        doc = read_letter(os.path.join(box["new"], name))
        if doc is None:
            continue
        seen.setdefault(name, n)
        dl = deadline(doc.get("priority"))
        if dl is not None and dl <= now:
            path = claim(box, name)
            if path:
                drop(name, doc, "DeadlineMissed", "deadline 已過，沒跑", path)
        elif cfg["budget"] is not None and used >= cfg["budget"]:
            path = claim(box, name)
            if path:
                drop(name, doc, "BudgetExhausted", "今天的 token 額度用完了（%d／%d）" % (used, cfg["budget"]), path)
        else:
            letters.append((name, doc))

    picked = []
    for name, doc in order(letters, seen, n, now, cfg):     # 3. 挑
        if len(picked) >= cfg["slots"]:
            break
        path = claim(box, name)
        if path:
            picked.append((name, doc, path))

    results = {}

    def go(name, doc):
        t0 = time.monotonic()
        results[name] = run_letter(doc) + (round((time.monotonic() - t0) * 1000),)

    if len(picked) == 1:                                     # 4. 跑（一封就在主執行緒，訊號照 aos_inst 轉）
        go(picked[0][0], picked[0][1])
    else:
        ths = [threading.Thread(target=go, args=(nm, d)) for nm, d, _ in picked]
        for t in ths:
            t.start()
        for t in ths:
            t.join()
    for name, doc, path in picked:
        rep, tokens, ms = results[name]
        used += tokens
        reply(doc, rep)
        os.remove(path)
        rec = {"letter": name, "priority": doc.get("priority"), "waited": n - seen.pop(name, n), "ms": ms,
               "code": rep.get("code")}
        if "error" in rep:
            rec["error"] = rep["error"]["code"]
        served.append(rec)
        log(cfg.get("log"), dict(rec, runs=n, sent=doc.get("sent")))

    live = set(os.listdir(box["new"]))
    seen = {k: v for k, v in seen.items() if k in live}
    budget = {"limit": cfg["budget"], "used": used, "day": today}
    served_all = (st.get("served") if _int(st.get("served"), 0) else 0) + len(served)
    write_json(cfg["state"], {"state": "waiting", "pid": os.getpid(), "runs": n, "last_error": None,
                              "beat": round(time.time(), 3), "seen": seen, "budget": budget, "served": served_all})
    return {"runs": n, "served": served, "dropped": dropped, "waiting": len(live), "budget": budget}


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
