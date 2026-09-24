"""daemon 替 kernel 開 tick（spec/daemon/ticks.md；2026-09-24 one-boot）。

daemon 除了當 cpu 的爸爸，也替登記過的 kernel 家「開一格 `aos-kernel tick`」：時間到（上一格開始後 every_ms）、
或 `K/requests/` 出現上一格開始時還沒有的檔，就開一格當孩子、不等它。同一個 kernel 家同時只開一格
（kernel 自己還有 `K/.tick.lock` 兜底）。daemon 只 stat／列 `K/requests/` 的檔名，**不讀 kernel 家任何檔的內容**。

登記：`D/requests/` 的 `tick` 單（params `home`、`cli`、`every_ms`、`timeout_ms`；`off: true`＝撤登記），
記在 `D/kernels/<id>.json`（id＝K 絕對路徑的 SHA-256 前 16 字元），daemon 重開照這些檔接著開。
一格退出：0＝好；75＝鎖被佔（別的 tick 在跑），不算失敗；其他（含逾時被 KILL）＝失敗，stderr 記一行、
退避 min(max(every_ms, 100)×2^(連敗−1), restart_max_ms) 再試，**不自己停**。
"""
import hashlib
import os
from pathlib import Path
import subprocess
import time

import aos_daemon_pools as pools
import aos_home

KERNELS = "kernels"
BUSY_EXIT = 75
MIN_BACKOFF_MS = 100
STOP_KILL = "停機時還沒跑完"


def kernel_id(khome):
    return hashlib.sha256(os.path.abspath(khome).encode()).hexdigest()[:16]


def reg_path(dhome, khome):
    return Path(dhome) / KERNELS / (kernel_id(khome) + ".json")


def peek(dhome, khome):
    """給 kernel（ls、health、halt）偷看：這個 K 在這個 daemon 登記了沒、最近怎樣；沒登記回 None。"""
    return pools.peek(reg_path(dhome, khome))


def registered(dhome):
    """這個 daemon 家登記了哪些 kernel 家（`aos down` 看還有沒有別人）。"""
    out = []
    folder = Path(dhome) / KERNELS
    if folder.is_dir():
        for leaf in sorted(folder.glob("*.json")):
            record = pools.peek(leaf)
            if record is not None and isinstance(record.get("home"), str):
                out.append(record)
    return out


def _abs(value):
    return isinstance(value, str) and value != "" and "\0" not in value and os.path.isabs(value)


def check_tick(params):
    """tick 單的形狀：不合＝-32602（DaemonError 由呼叫端丟）。回整理過的 params。"""
    from aos_daemon_rpc import DaemonError
    def bad(key, msg):
        raise DaemonError("FieldTypeMismatch", msg, -32602, ["params", key])
    if not isinstance(params, dict):
        raise DaemonError("FieldTypeMismatch", "params 必須是物件", -32602, ["params"])
    if not _abs(params.get("home")):
        bad("home", "home 必須是 kernel 家的絕對路徑")
    off = params.get("off", False)
    if type(off) is not bool:
        bad("off", "off 必須是布林")
    out = {"home": os.path.normpath(params["home"]), "off": off}
    if off:
        return out
    if not _abs(params.get("cli")):
        bad("cli", "cli 必須是 aos-kernel 的絕對路徑")
    out["cli"] = params["cli"]
    for key, default in (("every_ms", 1000), ("timeout_ms", 60000)):
        value = params.get(key, default)
        if type(value) is not int or value < 0:
            bad(key, "%s 必須是非負整數" % key)
        out[key] = value
    return out


class Ticker:
    """一個登記的 kernel 家在 daemon 記憶體裡的樣子。"""

    def __init__(self, reg):
        self.home = Path(reg["home"])
        self.id = kernel_id(self.home)
        self.cli, self.every_ms, self.timeout_ms = reg["cli"], reg["every_ms"], reg["timeout_ms"]
        self.proc = None            # 正在跑的那格（Popen）
        self.started = None         # 那格開始的 monotonic
        self.killed = None          # 那格被 daemon KILL 的原因（逾時／停機）
        self.stop_at = None         # 停機時：到這個時間還沒退就 KILL
        self.next_at = time.monotonic()   # 時間到就開一格（登記當下馬上開第一格）
        self.hold = 0.0             # 連敗退避中：這之前新檔也不開
        self.seen, self.mtime, self.poked = set(), None, False
        self.fails, self.last_exit, self.last_error_at = int(reg.get("fails") or 0), reg.get("last_exit"), reg.get("last_error_at")
        self.removed = False
        self.runs = 0

    def record(self):
        return {"home": str(self.home), "cli": self.cli, "every_ms": self.every_ms, "timeout_ms": self.timeout_ms,
                "fails": self.fails, "last_exit": self.last_exit, "last_error_at": self.last_error_at}


def _listing(folder):
    try:
        return {n for n in os.listdir(folder) if n.endswith(".json") and not n.startswith(".")}
    except OSError:
        return set()


class TicksMixin:
    """混進 aos_daemon_loop.Daemon：登記、何時開、收屍、逾時、停機。"""

    def init_ticks(self):
        self.tickers = {}            # id -> Ticker（登記中的）
        self.tick_pids = {}          # pid -> Ticker（正在跑的那格；撤登記後還在跑的也在這）

    def load_tickers(self):
        """開機：照 D/kernels/*.json 接著開（壞的檔記一行、略過）。"""
        folder = self.home / KERNELS
        folder.mkdir(exist_ok=True)
        for leaf in sorted(folder.glob("*.json")):
            record = pools.peek(leaf)
            try:
                reg = check_tick(record)
            except aos_home.HomeError as exc:
                pools.log("ReadFailed", "kernel 登記檔壞了、略過：%s（%s）" % (leaf, exc.msg))
                continue
            ticker = Ticker(dict(record, **reg))
            if ticker.id != leaf.name[:-5]:
                pools.log("ReadFailed", "kernel 登記檔名字跟內容對不上、略過：%s" % leaf)
                continue
            self.tickers[ticker.id] = ticker

    def publish_ticker(self, ticker):
        try:
            aos_home.write_json(self.home / KERNELS / (ticker.id + ".json"), ticker.record())
        except aos_home.HomeError as exc:
            pools.log(exc.code, exc.msg)

    # ---- tick 單（D/requests/） ----

    def tick(self, params):
        from aos_daemon_rpc import DaemonError
        p = check_tick(params)
        ident = kernel_id(p["home"])
        if p["off"]:
            ticker = self.tickers.pop(ident, None)
            if ticker is not None:
                ticker.removed = True          # 正在跑的那格照樣收屍，只是不再開下一格
            (self.home / KERNELS / (ident + ".json")).unlink(missing_ok=True)
            return {"home": p["home"], "off": True}
        if self.state["stopping"]:
            raise DaemonError("Stopping", "daemon 正在停機")
        ticker = self.tickers.get(ident)
        if ticker is None:
            ticker = self.tickers[ident] = Ticker(p)
        else:
            ticker.cli, ticker.every_ms, ticker.timeout_ms = p["cli"], p["every_ms"], p["timeout_ms"]
            ticker.next_at, ticker.hold, ticker.fails = time.monotonic(), 0.0, 0   # 重登記＝人來處理過了，連敗歸零
        (self.home / KERNELS).mkdir(exist_ok=True)
        try:
            aos_home.write_json(self.home / KERNELS / (ident + ".json"), ticker.record())
        except aos_home.HomeError as exc:
            self.tickers.pop(ident, None)
            raise DaemonError(exc.code, exc.msg) from exc
        return {"home": p["home"], "id": ident}

    # ---- 每圈 ----

    def ticks_step(self):
        now = time.monotonic()
        running = {id(t): t for t in self.tick_pids.values()}
        for ticker in running.values():
            limit = ticker.timeout_ms / 1000 if ticker.timeout_ms else None
            if ticker.killed is None and limit is not None and now - ticker.started >= limit:
                ticker.killed = "逾時（跑超過 %d ms）" % ticker.timeout_ms
                pools.signal_pid(ticker.proc.pid, pools.KILL, group=True)
            elif ticker.killed is None and ticker.stop_at is not None and now >= ticker.stop_at:
                ticker.killed = STOP_KILL
                pools.signal_pid(ticker.proc.pid, pools.KILL, group=True)
        if self.state["stopping"]:
            return
        for ticker in self.tickers.values():
            if ticker.proc is not None:
                continue
            self.watch(ticker)
            if now >= ticker.next_at or (ticker.poked and now >= ticker.hold):
                self.start_tick(ticker, now)

    def watch(self, ticker):
        """只 stat 資料夾的修改時間；變了才列一次目錄、比檔名（不讀內容）。"""
        try:
            mtime = os.stat(ticker.home / "requests").st_mtime_ns
        except OSError:
            return
        if mtime != ticker.mtime:
            ticker.mtime = mtime
            if _listing(ticker.home / "requests") - ticker.seen:
                ticker.poked = True

    def start_tick(self, ticker, now):
        folder = ticker.home / "requests"
        try:
            ticker.mtime = os.stat(folder).st_mtime_ns
        except OSError:
            ticker.mtime = None
        ticker.seen, ticker.poked = _listing(folder), False
        ticker.next_at = now + ticker.every_ms / 1000
        try:
            proc = subprocess.Popen([ticker.cli, "tick", "--target", str(ticker.home)], stdin=subprocess.DEVNULL,
                                    stdout=subprocess.DEVNULL, start_new_session=True, close_fds=True)
        except OSError as exc:
            self.tick_failed(ticker, None, "開不起來：%s" % exc)
            return
        ticker.proc, ticker.started, ticker.killed = proc, now, None
        ticker.stop_at = None
        self.tick_pids[proc.pid] = ticker

    def tick_exited(self, pid, code):
        """收屍時呼叫（aos_daemon_loop.reap）：回 True＝這個 pid 是 tick。"""
        ticker = self.tick_pids.pop(pid, None)
        if ticker is None:
            return False
        ticker.proc.returncode = code          # 免得 Popen 之後自己去 waitpid
        ticker.proc, killed, ticker.killed = None, ticker.killed, None
        ticker.runs += 1
        if ticker.removed or killed == STOP_KILL:
            return True                         # 撤登記了，或 daemon 停機時砍的（不算這個 kernel 的失敗）
        if killed is None and code == 0:
            if ticker.fails:
                ticker.fails, ticker.hold = 0, 0.0
                ticker.last_exit = 0
                self.publish_ticker(ticker)
        elif killed is None and code == BUSY_EXIT:
            ticker.next_at = max(ticker.next_at, time.monotonic() + ticker.every_ms / 1000)
        else:
            self.tick_failed(ticker, code, killed)
        return True

    def tick_failed(self, ticker, code, why):
        ticker.fails += 1
        wait = min(max(ticker.every_ms, MIN_BACKOFF_MS) * 2 ** (ticker.fails - 1), self.info["restart_max_ms"])
        ticker.next_at = ticker.hold = time.monotonic() + wait / 1000
        ticker.last_exit, ticker.last_error_at = code, time.time()
        pools.log("TickFailed", "K=%s 這格%s（連敗 %d，%d ms 後再試）" % (
            ticker.home, why or "退出 %s" % code, ticker.fails, wait))
        self.publish_ticker(ticker)

    # ---- 停機 ----

    def stop_ticks(self):
        """daemon 收到 stop：不再開新的；正在跑的給 stop_wait_ms＋kill_wait_ms 自己跑完，再不退就 KILL 整組。"""
        deadline = time.monotonic() + (self.info["stop_wait_ms"] + self.info["kill_wait_ms"]) / 1000
        for ticker in self.tick_pids.values():
            if ticker.stop_at is None:
                ticker.stop_at = deadline

    def ticks_sleep(self, delay):
        now = time.monotonic()
        for ticker in self.tickers.values():
            if ticker.proc is None and not self.state["stopping"]:
                delay = min(delay, max(ticker.next_at - now, 0))
        return delay

    def ticks_view(self):
        return {t.id: dict(t.record(), running=t.proc is not None) for t in self.tickers.values()}
