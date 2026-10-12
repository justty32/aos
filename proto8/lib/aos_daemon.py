#!/usr/bin/env python3
"""daemon：吃一份 config，開一個 loop（aos_loop），看控制資料夾把指令轉給它。純標準庫。

    python3 aos_daemon.py CONFIG

CONFIG 是 JSON，先用指示詞 lib 解（基準＝daemon 啟動時的 cwd）：

    control_dir      控制資料夾（必填）；底下 in/ 收指令、out/ 放回覆，沒有就建
    control_poll_ms  幾毫秒看一次 in/（正整數；預設 200）
    stop_poll_ms     交給 run() 的 stop_poll_ms（正整數；預設 50）

指令：往 in/ 放一個 `名字.json`（先寫成 `.名字.tmp` 再改名，免得被讀到一半；`.` 開頭的不讀）。
daemon 依檔名順序處理、刪掉，回覆寫到 out/名字.json：成功 {"ok": true, ...}，失敗 {"ok": false, "error": "代號: 白話"}。

    {"op": "add", "target": T, ...執行方式}   新增實例 → {"id": ID}；T 是 inst.json 或資料夾
    {"op": "set", "id": ID, ...執行方式}      改執行方式，下一次起生效
    {"op": "remove", "id": ID, "wait": B}     移除；wait＝true 等這次跑完，false 當場收掉（預設 true）
    {"op": "pause", "id": ID, "wait": B}      暫停；wait 同上
    {"op": "resume", "id": ID}                繼續
    {"op": "times", "id": ID, "delta": N}     剩餘次數加減 N
    {"op": "get", "id": ID}                   查一個 → {"inst": 狀態}
    {"op": "list"}                            查全部 → {"insts": [狀態, ...]}

執行方式、狀態的意思見 aos_loop。相對路徑（target、inst.json 裡的）基準都是 daemon 啟動時的 cwd。
實例表只在記憶體裡，daemon 結束就沒了。daemon 收到 SIGINT／SIGTERM：所有實例當場收掉，然後結束。
命令列退出碼：0＝正常結束；1＝起不來（stderr 印一行「代號: 白話」）。
"""
import json
import os
import signal
import sys
import time

from aos_directives import DirectiveError, resolve
from aos_loop import HOW, Loop, LoopError

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
    """一條指令 → 對 loop 的呼叫，回覆的 dict。"""
    try:
        if not isinstance(cmd, dict):
            raise DaemonError("BadCommand", "指令要是物件")
        op = cmd.get("op")
        how = {k: cmd[k] for k in HOW if k in cmd}
        if op == "add":
            return {"ok": True, "id": loop.add(cmd.get("target"), **how)}
        if op == "list":
            return {"ok": True, "insts": loop.list()}
        ident = cmd.get("id")
        if op == "set":
            loop.set(ident, **how)
        elif op == "remove":
            loop.remove(ident, cmd.get("wait", True))
        elif op == "pause":
            loop.pause(ident, cmd.get("wait", True))
        elif op == "resume":
            loop.resume(ident)
        elif op == "times":
            loop.times(ident, cmd.get("delta"))
        elif op == "get":
            return {"ok": True, "inst": loop.get(ident)}
        else:
            raise DaemonError("UnknownOp", "不認得的 op %r" % (op,))
        return {"ok": True}
    except (DaemonError, LoopError) as e:
        return {"ok": False, "error": str(e)}


def _scan(loop, in_dir, out_dir):
    for name in sorted(os.listdir(in_dir)):
        if name.startswith(".") or not name.endswith(".json"):
            continue
        path = os.path.join(in_dir, name)
        try:
            with open(path, encoding="utf-8") as f:
                cmd = json.loads(f.read())
        except (OSError, ValueError) as e:
            reply = {"ok": False, "error": "BadCommand: 讀不了 %s：%s" % (name, e)}
        else:
            reply = handle(loop, cmd)
        try:
            os.remove(path)
        except OSError:
            pass
        tmp = os.path.join(out_dir, "." + name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(reply, f, ensure_ascii=False, indent=2)
        os.replace(tmp, os.path.join(out_dir, name))


def serve(cfg, quit):
    """照 config 開 loop，每 control_poll_ms 看一次 in/，直到 quit() 為真；然後收掉所有實例。"""
    in_dir = os.path.join(cfg["control_dir"], "in")
    out_dir = os.path.join(cfg["control_dir"], "out")
    try:
        os.makedirs(in_dir, exist_ok=True)
        os.makedirs(out_dir, exist_ok=True)
    except OSError as e:
        raise DaemonError("MkdirFailed", "建不了控制資料夾：%s" % e)
    loop = Loop(cfg["stop_poll_ms"])
    try:
        while not quit():
            _scan(loop, in_dir, out_dir)
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
