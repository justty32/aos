"""daemon 的指令與控制資料夾：一條指令 → 一問一答（`handle()`），控制資料夾每圈掃一次（`_Folder`）。純標準庫。

指令格式、回覆格式、error.code 的規矩見 aos_daemon 的檔頭；這裡只放實作。
出意外不往上丟、不寫 stderr：記成這圈的 last_error（daemon 放進 state 窗）。
"""
import json
import os

from aos_daemon_table import DaemonError
from aos_loop import write_json

__all__ = ["handle"]


# ---- 指令 ----

def _error(code, msg):
    return {"ok": False, "error": {"code": code, "msg": msg}}


def handle(table, cmd):
    """一條指令 → 回 {"ok", "result"} 或 {"ok", "error"}；要等的回一個函式 ready()：還沒好回 None。"""
    try:
        r = _dispatch(table, cmd)
    except DaemonError as e:
        return _error(e.code, e.msg)
    except Exception as e:
        return _error("Internal", "%s: %s" % (type(e).__name__, e))
    if callable(r):
        def ready():
            try:
                v = r()
            except Exception as e:
                return _error("Internal", "%s: %s" % (type(e).__name__, e))
            return None if v is None else {"ok": True, "result": v}
        return ready
    return {"ok": True, "result": r}


def _dispatch(table, cmd):
    if not isinstance(cmd, dict):
        raise DaemonError("CommandBad", "指令要是物件")
    op, ident = cmd.get("op"), cmd.get("id")
    ops = {"add": lambda: table.add(ident), "set": lambda: table.set(ident, cmd.get("how", {})),
           "pause": lambda: table.pause(ident, cmd.get("wait", True)), "resume": lambda: table.resume(ident),
           "add_times": lambda: table.add_times(ident, cmd.get("delta")),
           "remove": lambda: table.remove(ident, cmd.get("wait", True)),
           "state": lambda: table.state(ident), "get": lambda: table.get(ident), "list": table.list}
    if op not in ops:
        raise DaemonError("OpUnknown", "不認得的 op %r" % (op,))
    return ops[op]()


# ---- 控制資料夾 ----

class _Folder:
    def __init__(self, d):
        self.d = d
        self.given_up, self.pending = set(), {}
        self.last_error = None      # 最近一圈出的最後一個錯（state 的 last_error）；那圈沒錯＝None
        self.errors = []

    def say(self, key, msg):
        """記成這圈的 last_error（「代號: 白話」）；不寫 stderr（N-43：預料到的意外，daemon 照樣跑）。"""
        self.errors.append(msg)

    def flush(self):
        for name, (path, cmd, ready) in list(self.pending.items()):
            r = ready()
            if r is not None:
                del self.pending[name]
                self.reply(path, {"request": cmd, **r})

    def scan(self, table):
        """處理一圈。出意外不往上丟：記成 last_error，下一圈照常。"""
        self.errors = []
        try:
            self._scan(table)
        finally:
            self.last_error = self.errors[-1] if self.errors else None

    def _scan(self, table):
        try:
            names = sorted(os.listdir(self.d))
        except OSError as e:
            self.say("list", "ScanFailed: 看不了控制資料夾 %s：%s" % (self.d, e))
            self.flush()
            return
        for name in names:
            if name.startswith(".") or not name.endswith(".json") or name in self.given_up or name in self.pending:
                continue
            path = os.path.join(self.d, name)
            raw = None
            try:
                with open(path, encoding="utf-8") as f:
                    raw = f.read()
                cmd = json.loads(raw)
            except (OSError, ValueError) as e:
                reply = {"request": raw, **_error("CommandBad", "讀不了 %s：%s" % (name, e))}
            else:
                r = handle(table, cmd)
                if callable(r):
                    self.pending[name] = (path, cmd, r)
                    continue
                reply = {"request": cmd, **r}
            self.reply(path, reply)
        self.flush()

    def reply(self, path, reply):
        """回覆寫成 名字.json.done、刪掉指令。寫不了就把指令本身改名成 .done；改名也不行就放著不管（之後也不再讀它）。"""
        name = os.path.basename(path)
        try:
            write_json(path + ".done", reply)
        except OSError as e:
            try:
                os.replace(path, path + ".done")
                self.say(name, "ReplyFailed: 寫不了 %s 的回覆（%s），把指令改名成 .done" % (name, e))
            except OSError as e2:
                self.given_up.add(name)
                self.say(name, "ReplyFailed: 寫不了 %s 的回覆（%s），改名也不行（%s），放著不管" % (name, e, e2))
            return
        try:
            os.remove(path)
        except OSError:
            pass
