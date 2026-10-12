#!/usr/bin/env python3
"""daemon：吃一份 config，開一個 loop（aos_loop），看控制資料夾把指令轉給它。純標準庫。

    python3 aos_daemon.py CONFIG

CONFIG 是 JSON，先用指示詞 lib 解（基準＝daemon 啟動時的 cwd）：

    control_dir      控制資料夾（必填），沒有就建
    control_poll_ms  幾毫秒看一次控制資料夾（正整數；預設 200）
    stop_poll_ms     交給 run() 的 stop_poll_ms（正整數；預設 50）

指令：往控制資料夾放一個 `名字.json`。daemon 每輪把裡面的 `*.json` 照檔名順序讀進來處理，處理完改成 `名字.json.done`，
內容換成一問一答：

    {"request": 原指令, "ok": true,  "result": 結果}
    {"request": 原指令, "ok": false, "error": {"code": "NotFound", "msg": "白話"}}

讀到不合法的 JSON 也一樣當場變成 `.done`（`request` 是讀到的原文字串，error.code＝BadCommand）。
怎麼寫不規定；`.` 開頭的檔不讀。同名的後蓋前；`.done` 由讀回覆的人自己清。兩邊都不 fsync。

指令一律 {"op", "id", ...參數}。`id` 什麼寫法都行（資料夾、inst.json、相對路徑），daemon 一律轉成 inst.json 的 realpath：

    {"op": "add",       "id": ID, "how": {...}}   新增實例                         → result＝realpath
    {"op": "set",       "id": ID, "how": {...}}   改執行方式（只改有寫的），下一次起生效
    {"op": "remove",    "id": ID, "wait": B}      移除；wait＝true 等這次跑完，false 當場收掉（預設 true）
    {"op": "pause",     "id": ID, "wait": B}      暫停；wait 同上
    {"op": "resume",    "id": ID}                 繼續
    {"op": "add_times", "id": ID, "delta": N}     剩餘次數加減 N（最少到 0）
    {"op": "state",     "id": ID}                 → result＝"waiting"／"running"／"paused"／"done"／"removing"
    {"op": "get",       "id": ID}                 → result＝狀態物件
    {"op": "list"}                                → result＝[狀態物件, ...]

沒有特別寫 result 的，result＝null。`how` 的欄位（times、interval_ms、timeout_ms、grace_ms）與狀態物件見 aos_loop。
error.code：BadCommand、UnknownOp、FieldType、NotFound、Exists、Conflict、Internal。
相對路徑（id、inst.json 裡的）基準都是 daemon 啟動時的 cwd。
實例表只在記憶體裡，daemon 結束就沒了。daemon 收到 SIGINT／SIGTERM：所有實例當場收掉，然後結束。
跑起來之後出意外不結束，只往 stderr 印一行（同一件事印一次）：控制資料夾看不了（ScanFailed）、
回覆寫不了（ReplyFailed：改把指令改名成 .done；改名也不行就放著不管）、指令處理出了沒料到的錯（回 Internal）。
命令列退出碼：0＝正常結束；1＝起不來（stderr 印一行「代號: 白話」）。
"""
import json
import os
import signal
import sys
import time

from aos_directives import DirectiveError, resolve
from aos_loop import Loop, LoopError

__all__ = ["DaemonError", "handle", "load_config", "serve"]


class DaemonError(Exception):
    """config 或指令被拒。`code`＝錯誤代號，`msg`＝白話，`str(e)`＝「代號: 白話」。"""

    def __init__(self, code, msg):
        super().__init__("%s: %s" % (code, msg))
        self.code = code
        self.msg = msg


def load_config(path):
    """讀 config，以現在的 cwd 為基準解指示詞、驗 key，回填好預設值的 dict。"""
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.loads(f.read())
    except OSError as e:
        raise DaemonError("ReadFailed", "讀不到 %s：%s" % (path, e))
    except ValueError as e:
        raise DaemonError("JsonSyntax", "%s 不是合法 JSON：%s" % (path, e))
    try:
        doc = resolve(doc, os.getcwd())
    except DirectiveError as e:
        raise DaemonError(e.code, e.msg)
    if not isinstance(doc, dict):
        raise DaemonError("FieldType", "config 要是物件")
    d = doc.get("control_dir")
    if not isinstance(d, str):
        raise DaemonError("FieldType", "control_dir 要是字串路徑，不是 %r" % (d,))
    cfg = {"control_dir": os.path.abspath(d)}
    for k, default in (("control_poll_ms", 200), ("stop_poll_ms", 50)):
        v = doc.get(k, default)
        if not (isinstance(v, int) and not isinstance(v, bool) and v > 0):
            raise DaemonError("FieldType", "%s 要是正整數，不是 %r" % (k, v))
        cfg[k] = v
    return cfg


def handle(loop, cmd):
    """一條指令 → 對 loop 的呼叫，回 {"ok", "result"} 或 {"ok", "error": {"code", "msg"}}。"""
    try:
        return {"ok": True, "result": _dispatch(loop, cmd)}
    except (DaemonError, LoopError) as e:
        return _error(e.code, e.msg)
    except Exception as e:
        return _error("Internal", "%s: %s" % (type(e).__name__, e))


def _error(code, msg):
    return {"ok": False, "error": {"code": code, "msg": msg}}


def _dispatch(loop, cmd):
    if not isinstance(cmd, dict):
        raise DaemonError("BadCommand", "指令要是物件")
    op, ident = cmd.get("op"), cmd.get("id")
    if op == "add":
        return loop.add(ident, cmd.get("how", {}))
    if op == "set":
        return loop.set(ident, cmd.get("how", {}))
    if op == "remove":
        return loop.remove(ident, cmd.get("wait", True))
    if op == "pause":
        return loop.pause(ident, cmd.get("wait", True))
    if op == "resume":
        return loop.resume(ident)
    if op == "add_times":
        return loop.add_times(ident, cmd.get("delta"))
    if op == "state":
        return loop.state(ident)
    if op == "get":
        return loop.get(ident)
    if op == "list":
        return loop.list()
    raise DaemonError("UnknownOp", "不認得的 op %r" % (op,))


def _say(said, key, msg):
    """同一件事只往 stderr 印一次；key 的訊息變了才再印。"""
    if said.get(key) != msg:
        said[key] = msg
        print(msg, file=sys.stderr)


def _scan(loop, d, said, given_up):
    """處理一輪。出意外不往上丟：印到 stderr，下一輪照常。"""
    try:
        names = sorted(os.listdir(d))
    except OSError as e:
        _say(said, "list", "ScanFailed: 看不了控制資料夾 %s：%s" % (d, e))
        return
    said.pop("list", None)
    for name in names:
        if name.startswith(".") or not name.endswith(".json") or name in given_up:
            continue
        path = os.path.join(d, name)
        raw = None
        try:
            with open(path, encoding="utf-8") as f:
                raw = f.read()
            cmd = json.loads(raw)
        except (OSError, ValueError) as e:
            reply = {"request": raw, **_error("BadCommand", "讀不了 %s：%s" % (name, e))}
        else:
            reply = {"request": cmd, **handle(loop, cmd)}
        _reply(path, reply, said, given_up)


def _reply(path, reply, said, given_up):
    """回覆寫成 名字.json.done、刪掉指令。寫不了就把指令本身改名成 .done；改名也不行就放著不管（之後也不再讀它）。"""
    d, name = os.path.split(path)
    done = os.path.join(d, name + ".done")
    tmp = os.path.join(d, "." + name + ".done.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(reply, f, ensure_ascii=False, indent=2)
        os.replace(tmp, done)
    except OSError as e:
        try:
            os.remove(tmp)
        except OSError:
            pass
        try:
            os.replace(path, done)
            _say(said, name, "ReplyFailed: 寫不了 %s 的回覆（%s），把指令改名成 .done" % (name, e))
        except OSError as e2:
            given_up.add(name)
            _say(said, name, "ReplyFailed: 寫不了 %s 的回覆（%s），改名也不行（%s），放著不管" % (name, e, e2))
        return
    try:
        os.remove(path)
    except OSError:
        pass


def serve(cfg, quit):
    """照 config 開 loop，每 control_poll_ms 看一次控制資料夾，直到 quit() 為真；然後收掉所有實例。
    控制資料夾開頭沒有就建；之後不見了只往 stderr 印一次，不建回來、不結束。"""
    d = cfg["control_dir"]
    try:
        os.makedirs(d, exist_ok=True)
    except OSError as e:
        raise DaemonError("MkdirFailed", "建不了控制資料夾：%s" % e)
    loop = Loop(cfg["stop_poll_ms"])
    said, given_up = {}, set()
    try:
        while not quit():
            _scan(loop, d, said, given_up)
            time.sleep(cfg["control_poll_ms"] / 1000)
    finally:
        loop.shutdown()


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("用法：aos_daemon.py CONFIG", file=sys.stderr)
        return 1
    got = []
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda signum, frame: got.append(signum))
    try:
        serve(load_config(args[0]), lambda: got)
        return 0
    except DaemonError as e:
        print(e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
