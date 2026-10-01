"""aos-daemon 的控制模組：伺服器端（plan m3n-control-module.md 步驟 2、3、6）。

設定檔寫了 `"modules": {"control": {"socket": "<路徑>"}}` 時，`aos_daemon.main()` 叫 `serve()`：
在那個路徑開一個 unix socket，一條執行緒收連線；一連線一請求——讀一行 JSON、回一行 JSON、關掉。
四個指令 wake／pause／resume／status，每個都只對一項（`insts` 的鍵，逐字比對）。
指令只改那一項的狀態、喚醒它的執行緒，不自己開程序（同一項不疊著開照 m3）。

〔使用者方向 2026-10-01〕POC 默認一切正常；唯一的例外是單一連線出的錯（壞 JSON、對面先關、逾時）
只影響那一條連線，收連線的執行緒繼續跑。

待問 1 照建議先做（使用者可改）：暫停中 wake 跑一次、跑完照樣暫停；被 stop_on_nonzero 停掉的項
wake 回 `stopped`、不跑；resume 一律馬上跑一次。
"""
import json
import os
import socket
import threading
import time

from aos_daemon import clock, say

COMMANDS = ("wake", "pause", "resume", "status")
WAKE_OPTIONS = ("skip_while_running", "keep_schedule")
TIMEOUT = 1.0           # 每條連線最多等這麼久（連上不送的客戶端不能卡住後面的人）


class BadRequest(Exception):
    pass


def serve(path, items):
    """開 socket（路徑上有舊檔先刪）、起收連線的執行緒。items＝{inst 字面值: Item}。"""
    if os.path.lexists(path):
        os.unlink(path)
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.bind(path)
    s.listen()
    threading.Thread(target=_accept_loop, args=(s, items), daemon=True).start()


def _accept_loop(s, items):
    while True:
        conn, _ = s.accept()
        with conn:
            try:
                _one(conn, items)
            except OSError:
                pass                    # 對面先關、逾時：只丟掉這一條連線


def _one(conn, items):
    deadline = time.monotonic() + TIMEOUT
    data = b""
    while b"\n" not in data:
        left = deadline - time.monotonic()
        if left <= 0:
            return                      # 逾時：關掉、不回
        conn.settimeout(left)
        chunk = conn.recv(4096)
        if not chunk:
            break                       # 對面關了寫的那一邊、沒送完一行
        data += chunk
    try:
        if b"\n" not in data:
            raise BadRequest("沒有讀到一行")
        reply = handle(parse(data.split(b"\n", 1)[0]), items)
    except BadRequest as e:
        reply = {"ok": False, "error": "bad_request", "detail": str(e)}
    conn.sendall((json.dumps(reply, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))


def parse(line):
    """一行 → (指令名, inst, wake 選項 dict)。格式不對丟 BadRequest。"""
    try:
        req = json.loads(line.decode("utf-8"))
    except ValueError:                  # UnicodeDecodeError 也是 ValueError
        raise BadRequest("不是 JSON")
    if not isinstance(req, dict):
        raise BadRequest("不是 JSON 物件")
    names = [c for c in COMMANDS if c in req]
    if len(names) != 1:
        raise BadRequest("指令名要剛好一個（%s 之一）" % "／".join(COMMANDS))
    cmd = names[0]
    inst = req[cmd]
    if not isinstance(inst, str):
        raise BadRequest("%s 的值要是字串（inst 字面值）" % cmd)
    opts = {}
    if cmd == "wake":                   # 其他指令帶這兩個欄位一律忽略
        for k in WAKE_OPTIONS:
            v = req.get(k, False)
            if not isinstance(v, bool):
                raise BadRequest("%s 要是布林" % k)
            opts[k] = v
    return cmd, inst, opts


def handle(request, items):
    """改狀態、回應答（不等那一項跑完）。"""
    cmd, inst, opts = request
    item = items.get(inst)
    if item is None:
        return {"ok": False, "error": "unknown_inst", "detail": inst}
    with item.cond:
        if cmd == "status":
            return status(item)
        if cmd == "wake":
            if item.stopped:
                return {"ok": False, "error": "stopped", "detail": inst}
            if not (item.running and opts["skip_while_running"]):
                _want(item, opts["keep_schedule"])
        elif cmd == "pause":
            item.paused = True
            item.pending = False        # 待補的那次一併取消；正在跑的不殺
            say("inst=%s paused" % inst)
        else:                           # resume：清掉暫停與已停，當成一次不帶選項的 wake
            item.paused = item.stopped = False
            say("inst=%s resumed" % inst)
            _want(item, False)
        item.cond.notify_all()
    return {"ok": True}


def _want(item, keep):
    """記「跑一次」（叫幾次都只補一次；keep_schedule 照最後一次）。"""
    item.pending = True
    item.pending_keep = keep


def status(item):
    idle = not (item.running or item.paused or item.stopped)
    return {"ok": True, "inst": item.inst, "running": item.running, "pending": item.pending,
            "paused": item.paused, "stopped": item.stopped, "last_exit": item.last_exit,
            "last_end": item.last_end, "next": clock(item.due) if idle else None}
