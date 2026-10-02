"""aos-daemon 的控制模組：伺服器端（plan m3n-control-module.md 步驟 2、3、6）。

設定檔寫了 `"modules": {"control": {"socket": "<路徑>"}}` 時，`aos_daemon.main()` 叫 `serve()`：
在那個路徑開一個 unix socket，一條執行緒收連線；一連線一請求——讀一行 JSON、回一行 JSON、關掉。
四個指令 wake／pause／resume／status，每個都只對一項（`insts` 的鍵，逐字比對）。
指令只改那一項的狀態、喚醒它的執行緒，不自己開程序（同一項不疊著開照 m3）。

〔使用者方向 2026-10-01〕POC 默認一切正常；唯一的例外是單一連線出的錯（壞 JSON、對面先關、逾時、
過深的 JSON）只影響那一條連線，收連線的執行緒繼續跑。回應一律 ASCII 跳脫（非 ASCII 寫成反斜線 u 加四個 hex）。

待問 1 照建議先做（使用者可改）：暫停中 wake 跑一次、跑完照樣暫停；被 stop_on_nonzero 停掉的項
wake 回 `stopped`、不跑；resume 一律馬上跑一次。

〔使用者 2026-10-01 第十九批〕`kill`、`restart`：
- kill：那一項正在跑就先送 SIGTERM，`modules.control.kill_grace_ms`（預設 5000）內還沒結束就 SIGKILL，掛了 cgroup
  再 `cgroup.kill` 整個框（`aos_daemon.kill_run()`，另開執行緒、送出 SIGTERM 就回）。沒在跑：回 ok、什麼都不做。
  被殺的那次照常印 `exit=`（128+N）、照週期排下一次；`stop_on_nonzero` 照算。
- restart：被 stop_on_nonzero 停掉的回 `stopped`（同 wake）；有在跑就照 kill、記一次待補（結束後立刻再跑，
  被殺的那次不算 stop_on_nonzero）；沒在跑＝不帶選項的 wake。
"""
import json
import os
import socket
import threading
import time

from aos_daemon import clock, say, state_changed

COMMANDS = ("wake", "pause", "resume", "status", "kill", "restart")
KILL_GRACE = 5.0        # 秒；modules.control.kill_grace_ms（第十九批）
WAKE_OPTIONS = ("skip_while_running", "keep_schedule")
TIMEOUT = 1.0           # 每條連線最多等這麼久（連上不送的客戶端不能卡住後面的人）


class BadRequest(Exception):
    pass


def grace_of(conf):
    """`modules.control.kill_grace_ms` 換成秒：非負數，沒寫＝5000。不合丟 ValueError（讀設定時就檢查，算設定錯）。"""
    ms = conf.get("kill_grace_ms", 5000)
    if isinstance(ms, bool) or not isinstance(ms, (int, float)) or ms < 0:
        raise ValueError("modules.control.kill_grace_ms 要是非負數")
    return ms / 1000.0


def set_grace(conf):
    global KILL_GRACE
    KILL_GRACE = grace_of(conf)


def serve(path, items, answer=None):
    """開 socket（路徑上有舊檔先刪）、起收連線的執行緒。items＝{inst 字面值: Item}。
    answer(一行 bytes, items) → 回應 dict，格式不對丟 BadRequest；沒給＝控制指令。
    訊息模組（m3m 模組四，`aos_daemon_mq`）也用這一套開它自己的 socket。"""
    answer = answer or (lambda line, its: handle(parse(line), its))
    if os.path.lexists(path):
        os.unlink(path)
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.bind(path)
    s.listen()
    threading.Thread(target=_accept_loop, args=(s, items, answer), daemon=True).start()


def _accept_loop(s, items, answer):
    while True:
        conn, _ = s.accept()
        with conn:
            try:
                _one(conn, items, answer)
            except Exception:
                pass                    # 對面先關、逾時、怪輸入（過深的 JSON……）：只丟掉這一條連線


def _one(conn, items, answer):
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
        reply = answer(data.split(b"\n", 1)[0], items)
    except BadRequest as e:
        reply = {"ok": False, "error": "bad_request", "detail": str(e)}
    # ASCII 跳脫：字串裡的落單代理字元（\ud800）照樣送得出去，不會在 encode 時丟錯
    conn.sendall((json.dumps(reply, separators=(",", ":")) + "\n").encode("ascii"))


def parse(line):
    """一行 → (指令名, inst, wake 選項 dict)。格式不對丟 BadRequest。"""
    try:
        req = json.loads(line.decode("utf-8"))
    except (ValueError, RecursionError):    # UnicodeDecodeError 也是 ValueError；RecursionError＝太深
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
    """改狀態、回應答（不等那一項跑完）。items＝daemon 的 {inst: Item}（重讀設定會原地改它）。
    pause／resume 改完通知記住狀態模組（m3m 模組三；沒掛時什麼都不做），鎖放開後才寫檔。"""
    reply = _handle(request, items)
    if reply.get("ok") and request[0] in ("pause", "resume"):
        state_changed()
    return reply


def _handle(request, items):
    cmd, inst, opts = request
    item = items.get(inst)
    if item is None:
        return {"ok": False, "error": "unknown_inst", "detail": inst}
    with item.cond:
        if cmd == "status":
            return status(item)
        if cmd in ("kill", "restart"):
            return _kill(item, inst, cmd == "restart")
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


def _kill(item, inst, restart):
    """在 item.cond 底下：kill／restart（第十九批）。"""
    import aos_daemon
    if restart:
        if item.stopped:
            return {"ok": False, "error": "stopped", "detail": inst}
        _want(item, False)
        if item.running:
            item.restart_seq = item.run_seq
        item.cond.notify_all()
    if item.running:
        threading.Thread(target=aos_daemon.kill_run, args=(item, item.run_seq, KILL_GRACE), daemon=True).start()
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
