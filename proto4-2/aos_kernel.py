#!/usr/bin/env python3
"""aos-kernel：做管理。它自己只是一個被第一顆 cpu 每秒跑一次的普通 proc——
一次執行做完就退出，「一直跑」那件事是它的 cpu 在做，不是它自己。

一次執行做四件事：
  1. 讀 $AOS_HOME/requests/*.json（使用者面的請求）。
  2. 翻成 daemon 請求寫進 $AOS_HOME/daemon/requests/（dir 先 realpath 過，
     symlink／`..`／尾巴 `/` 都算同一個資料夾——那就是這顆 cpu 唯一的標示）：
       {"op":"register","dir":…,"interval":…,"time_limit":…}
                                               → {"op":"spawn","dir":…,"interval":…,"time_limit":…}
       {"op":"unregister","dir":…}              → {"op":"kill","dir":…}
  3. 處理過的搬到 $AOS_HOME/requests/done/（多 ok／sent）。
  4. 讀 daemon/state.json 印一行摘要到 stdout——它會進 kernel 自己的 last.json，
     那就是 kernel 的日誌。

家目錄走 AOS_HOME（daemon 生 inst.json 時塞進 env）或第一個參數。
"""
import json
import os
import sys
import time

from aos_cpu import write_json


def req_name(seq):
    return "%013d-%d-%04d.json" % (time.time() * 1000, os.getpid(), seq)


def translate(req):
    """使用者面的請求 → daemon 請求。不認識的回 None。

    dir 先 os.path.realpath()：那是這顆 cpu 唯一的標示，symlink／`..`／尾巴 `/`
    都要正規化成同一個，daemon 的表才認得出「這資料夾已經有一顆在跑」。
    """
    op = req.get("op")
    if op == "register":
        return {"op": "spawn", "dir": os.path.realpath(req["dir"]),
                "interval": req.get("interval") or 1,
                "time_limit": req.get("time_limit") or 0}
    if op == "unregister":
        return {"op": "kill", "dir": os.path.realpath(req["dir"])}
    return None


def main():
    home = os.environ.get("AOS_HOME") or (sys.argv[1] if len(sys.argv) > 1 else None)
    if not home:
        print("沒有家：設 AOS_HOME", file=sys.stderr)
        return 2
    home = os.path.abspath(home)
    reqs = os.path.join(home, "requests")
    done = os.path.join(reqs, "done")
    dreq = os.path.join(home, "daemon", "requests")
    for p in (reqs, done, dreq):
        os.makedirs(p, exist_ok=True)

    handled = []
    names = sorted(n for n in os.listdir(reqs)
                   if n.endswith(".json") and os.path.isfile(os.path.join(reqs, n)))
    for i, n in enumerate(names):
        src = os.path.join(reqs, n)
        try:
            with open(src) as f:
                req = json.load(f)
            out = translate(req)
            if out is None:
                res = {"req": req, "ok": False, "result": "不認識的 op：%s" % req.get("op")}
            else:
                sent = req_name(i)
                write_json(os.path.join(dreq, sent), out)
                res = {"req": req, "ok": True, "sent": sent, "result": out}
                handled.append("%s→%s" % (req.get("op"), out["op"]))
        except Exception as e:
            res = {"req": n, "ok": False, "result": "%s: %s" % (type(e).__name__, e)}
        os.remove(src)
        write_json(os.path.join(done, n), res)

    try:
        with open(os.path.join(home, "daemon", "state.json")) as f:
            cpus = json.load(f).get("cpus", {})
    except (OSError, ValueError):
        cpus = {}
    print("cpu %d 顆（%s）；這次處理 %d 件請求%s" % (
        len(cpus),
        ", ".join("%s:tick=%s" % (k, v.get("tick")) for k, v in sorted(cpus.items())) or "無",
        len(names),
        ("：" + ", ".join(handled)) if handled else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
