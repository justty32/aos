#!/usr/bin/env python3
"""請求檔那一層——daemon 與外面之間只有檔案，從 `aos_daemon.py` 拆出來的。

寫一個 JSON 到 `H/requests/`（先 `.tmp` 再 rename），daemon 每一圈掃一次（`.tmp` 忽略），
處理完搬到 `H/requests/done/` 同名、內容＝**原請求 ＋ `ok` ＋ `result`**。這一版沒有
kernel，daemon 自己讀請求。

    {"op":"add",     "target":"/path/to/inst.json", "args":["--interval-ms","2000"]}
    {"op":"remove",  "target":"/path/to/inst.json", "force":false}
    {"op":"restart", "target":"/path/to/inst.json", "args":["--interval-ms","5000"]}
    {"op":"get",     "target":"/path/to/inst.json"}
    {"op":"ls"}
    {"op":"pause",   "target":"/path/to/inst.json"}
    {"op":"resume",  "target":"/path/to/inst.json"}
    {"op":"stop"}

七個動作的目標欄位一律叫 **`target`**，值是那份 inst.json 的路徑（§15：key＝它的
realpath；`add`／`restart` 只收 `.json`，`rm`／`get`／`pause`／`resume` 存不存在都查表）。

不認得的 op、缺欄位、壞掉的 JSON ＝ `ok:false`（不是炸掉），一樣有回音。
"""
import json
import os

from aos_home import write_json


def dispatch(dmn, req):
    """一個請求 → `(ok, result)`。七個動作都是**立刻回**的，這裡不會卡住主迴圈。"""
    if not isinstance(req, dict):
        return False, "請求不是一個 JSON 物件"
    op = req.get("op")
    try:
        if op == "add":
            return dmn.add(req["target"], req.get("args") or [])
        if op == "remove":
            return dmn.remove(req["target"], bool(req.get("force")))
        if op == "restart":
            return dmn.restart(req["target"], req.get("args") or [])
        if op == "get":
            return dmn.get(req["target"])
        if op == "ls":
            return dmn.ls()
        if op == "pause":
            return dmn.pause(req["target"])
        if op == "resume":
            return dmn.resume(req["target"])
        if op == "stop":
            dmn.stopping = True
            return True, "收工中"
    except KeyError as e:
        return False, "缺欄位 %s" % e
    return False, "不認得的 op：%r" % (op,)


def handle_requests(dmn):
    """掃 requests/*.json（`.tmp` 忽略）、處理、搬到 done/ 同名＋ok／result。"""
    try:
        names = sorted(n for n in os.listdir(dmn.home.requests) if n.endswith(".json"))
    except OSError:
        return
    for n in names:
        src = os.path.join(dmn.home.requests, n)
        if not os.path.isfile(src):
            continue
        req = None
        try:
            with open(src, encoding="utf-8") as f:
                req = json.load(f)
            ok, res = dispatch(dmn, req)
        except Exception as e:                          # 壞掉的請求檔也要有回音
            ok, res = False, "%s: %s" % (type(e).__name__, e)
        if not ok:
            dmn.say("請求 %s 被拒：%s" % (n, res))
        try:
            os.remove(src)
        except OSError:
            pass
        if ok:
            dmn.save()          # 先落地再回音：CLI 收到 done 時 state.json 已經是新的
        out = dict(req) if isinstance(req, dict) else {"req": n}
        out["ok"], out["result"] = ok, res
        write_json(os.path.join(dmn.home.done, n), out)
