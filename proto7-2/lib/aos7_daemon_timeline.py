"""一條 tick-tock 時間線的迴圈（spec.md 2.1、2.2、2.5）：不變條件一 → pause → tick → 等（固定 interval 或提前 tock）→ tock → 等滿 interval。

迴圈本身是 daemon 裡的一個 thread；tick、tock 每次都是獨立程序（S-04）。起點是 proto7-1 lib/aos7_daemon_timeline.py。
"""
import json
import math
import os
import subprocess
import sys
import threading
import time

import aos7_task
from aos7_fs import (BIN, IO, OK, env_with_bin, holder_unverified, is_int, node_path, now, read_json, read_json3,
                     reap_stale_owner)

POLL = 0.02
DEFAULT_INTERVAL_MS = 1000
ERROR_BACKOFF = 0.5          # 時間線出錯後的等待（也是不變條件一退避的起點）
RECOVER_BACKOFF_MAX = 8.0    # 退避最多到幾秒（2.1 第 1 步）
ACTION_TIMEOUT = 30.0        # tick／tock 一次最多跑幾秒（timeline.json 的 `action_timeout_s` 可改）
STOP_GRACE = 3.0             # daemon 停機時，正在跑的 tick／tock 最多再等幾秒
TIMEOUT_RC = -9
UNKNOWN_RC = 3               # tick／tock 推定不了（round.json 讀不到…）的退出碼


def run_prog(name, root, node_id, extra_env=None, gen=None, timeout=None, abort=None):
    """跑 `bin/<name> <root> <node-id>`，回 (returncode, 最後一行 JSON 或 None, stderr)。逾時或 abort() 為真就 SIGKILL。"""
    env = env_with_bin()
    for k in ("AOS7_EARLY", "AOS7_INCOMPLETE"):
        env.pop(k, None)
    env.update(extra_env or {})
    if gen is not None:
        env["AOS7_GEN"] = str(gen)
    p = subprocess.Popen([sys.executable, os.path.join(BIN, name), root, node_id],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    t0 = time.monotonic()
    why = None
    while True:
        try:
            stdout, stderr = p.communicate(timeout=0.1)
            break
        except subprocess.TimeoutExpired:
            if timeout is not None and time.monotonic() - t0 > timeout:
                why = "timeout after %.1fs" % timeout
            elif abort is not None and abort():
                why = "aborted: daemon stopping"
            if why:
                p.kill()
                stdout, stderr = p.communicate()
                return TIMEOUT_RC, None, ("%s: %s killed (%s)" % (stderr or "", name, why)).strip()
    out = None
    lines = stdout.strip().splitlines()
    if lines:
        try:
            out = json.loads(lines[-1])
        except ValueError:
            pass
    return p.returncode, out, stderr.strip()


def read_config(node):
    """`<node>/.aos/timeline.json`（可有可無；W12）→ (interval_ms, early_tock, action_timeout_s, 錯誤或 None)。"""
    t = read_json(os.path.join(node, ".aos", "timeline.json"), {})
    t = t if isinstance(t, dict) else {}
    err = None
    ms = t.get("interval_ms", DEFAULT_INTERVAL_MS)
    if isinstance(ms, bool) or not isinstance(ms, (int, float)) or not (0 <= ms <= 86400000 * 365) \
            or not math.isfinite(ms):
        err = "interval_ms 要是有限非負數字，拿到 %r；先用 %d" % (ms, DEFAULT_INTERVAL_MS)
        ms = DEFAULT_INTERVAL_MS
    early = t.get("early_tock", False) is True
    v = t.get("action_timeout_s")
    tmo = float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and 0 < v < 1e6 else ACTION_TIMEOUT
    return int(ms), early, tmo, err


class Timeline(threading.Thread):
    """一條時間線。daemon 物件要提供 root、gen、stopping、stopping_since、kill_on_stop、is_paused(nid)、round_done(nid)、
    log(**kw)、kill_live(nid, node)。"""

    def __init__(self, daemon, node_id, ident):
        super().__init__(name="tl:" + node_id, daemon=True)
        self.d = daemon
        self.node_id = node_id
        self.node = node_path(daemon.root, node_id)
        self.node_ident = ident              # 開始時記的 (st_dev, st_ino)：換了就是被搬走或換掉（2.6）
        self.phase = "idle"
        self.round = self.disk_round()
        self.interval_ms = None
        self.early_tock = False
        self.last_error = None
        self.last_event = None
        self.round_open = None           # True／False／None＝不知道（2.2）
        self.recovery_pending = False
        self.gone = False                # node 消失：不再 tick／tock
        self.retire = False              # unregister：本回合收完就結束
        self.retire_kill = True
        self.wake = threading.Event()
        self.kick = False                # wake／resume：idle 時不等滿 interval
        self.recover_fails = 0
        self.owe_done = False
        self.unverified = None

    # ---------- 小工具 ----------

    def disk_round(self):
        r = read_json(os.path.join(self.node, ".aos", "round.json"), {})
        v = r.get("round") if isinstance(r, dict) else None
        return v if is_int(v) else getattr(self, "round", 0)

    def err(self, prog, rc, msg):
        self.last_error = {"prog": prog, "rc": rc, "round": self.round, "at": now(), "err": (msg or "")[-300:]}

    def stop_overdue(self):
        since = getattr(self.d, "stopping_since", None)
        return since is not None and time.monotonic() - since > STOP_GRACE

    def done(self):
        return self.d.stopping or self.gone

    def leaving(self):
        return self.done() or self.retire

    def sleep_until(self, t_end, kickable):
        while not self.leaving() and not (kickable and self.kick) and time.monotonic() < t_end:
            self.wake.wait(min(POLL, max(0.0, t_end - time.monotonic())))
            self.wake.clear()

    def backoff(self):
        self.recover_fails += 1
        self.phase = "error"
        t = min(ERROR_BACKOFF * 2 ** (self.recover_fails - 1), RECOVER_BACKOFF_MAX)
        end = time.monotonic() + t
        while not self.leaving() and time.monotonic() < end:
            self.wake.wait(min(POLL * 5, end - time.monotonic()))

    def prog(self, name, extra=None, timeout=None):
        rc, out, err = run_prog(name, self.d.root, self.node_id, extra, gen=self.d.gen,
                                timeout=timeout or self.cfg_timeout, abort=self.stop_overdue)
        if rc:
            self.err(name.replace("aos7-", ""), rc, err)
        if rc == TIMEOUT_RC and out is None:
            self.reap_holder()
        return rc, out, err

    def check_round(self):
        """不變條件一（2.2）：回 True／False（round.json 確知開著／確知關了或沒有）／None（讀不到＝不知道）。"""
        st, r = read_json3(os.path.join(self.node, ".aos", "round.json"))
        if st == IO:
            self.round_open = None
            return None
        self.round_open = st == OK and isinstance(r, dict) and r.get("open") is True
        return self.round_open

    # ---------- 迴圈 ----------

    def run(self):
        try:
            while True:
                try:
                    self._loop()
                    return
                except Exception as e:   # 一條時間線出事不拖垮整個 daemon：記下來、等一下再接著跑
                    self.err("timeline", None, repr(e))
                    self.phase = "error"
                    self.wake.wait(ERROR_BACKOFF)
                    if self.leaving():
                        return
        finally:
            self.phase = "stopped"

    def _loop(self):
        self.cfg_timeout = ACTION_TIMEOUT
        while not self.leaving():
            ms, early, self.cfg_timeout, cerr = read_config(self.node)
            if cerr:
                self.err("timeline", None, cerr)
            # 1. 不變條件一：舊回合確知已關才開下一回合
            ro = self.check_round()
            if ro is None:
                self.err("round", None, "round.json 讀不到（不知道回合關了沒），不 tick，退避後再看")
                self.backoff()
                continue
            if ro:
                self.recovery_pending = True
                self.phase = "tock"
                rc, out, err = self.prog("aos7-tock", {"AOS7_EARLY": "0", "AOS7_INCOMPLETE": "unclosed"})
                if (out or {}).get("stale"):
                    return
                if self.check_round() is not False:
                    self.err("tock", rc, "第 %s 回合沒關上，恢復成功前不開下一回合（已試 %d 次）；%s" % (
                        self.round, self.recover_fails + 1, (err or "")[-200:]))
                    self.backoff()
                    continue
                self.recovery_pending = False
                self.recover_fails = 0
                self.event("round-recovered", round=self.disk_round())
                if self.owe_done:
                    self.owe_done = False
                    self.d.round_done(self.node_id)
                continue   # 回到迴圈頂端重新看 pause 與 rounds 倒數
            self.recover_fails = 0
            # 2. pause
            if self.d.is_paused(self.node_id):
                self.phase = "paused"
                self.wake.wait(POLL)
                self.wake.clear()
                continue
            # 3. tick
            self.interval_ms, self.early_tock = ms, early
            t0 = time.monotonic()
            t_end = t0 + ms / 1000.0
            self.kick = False
            self.phase = "tick"
            rc, out, err = self.prog("aos7-tick")
            tick_cut = rc == TIMEOUT_RC and out is None
            if (out or {}).get("stale"):
                self.event("stale", prog="tick")
                return
            if (out or {}).get("gone"):
                self.wake.wait(POLL)
                continue
            if rc == UNKNOWN_RC:
                self.backoff()
                continue
            started = (out or {}).get("started") or []
            self.round = (out or {}).get("round") or self.disk_round()
            self.round_open = True
            # 4. 等
            self.phase = "running"
            while not self.leaving() and time.monotonic() < t_end:
                if early and all(self.run_done(r) for r in started):
                    break
                self.wake.wait(POLL)
                self.wake.clear()
            if self.gone:
                return
            self.kill_if_leaving()
            # 5. tock
            self.phase = "tock"
            is_early = time.monotonic() < t_end and not self.leaving()
            env = {"AOS7_EARLY": "1" if is_early else "0"}
            if tick_cut:
                env["AOS7_INCOMPLETE"] = "tick"
            rc, out, err = self.prog("aos7-tock", env)
            if self.check_round():
                # tock 沒把回合關上：馬上補一次（同回合已有總結就只收尾）
                if not self.gone and not self.stop_overdue():
                    self.prog("aos7-tock", {"AOS7_EARLY": "0", "AOS7_INCOMPLETE": "tock"})
            if self.check_round() is not False:
                self.owe_done = True
                self.event("round-unclosed", round=self.round, rc=rc)
                continue   # 下一圈頂端走不變條件一
            self.d.round_done(self.node_id)
            # 6. 等滿 interval（wake、resume 打斷）
            self.phase = "idle"
            self.sleep_until(t_end, kickable=True)
        if not self.gone:
            self.kill_if_leaving()
            if self.retire and self.check_round():
                self.prog("aos7-tock", {"AOS7_EARLY": "0", "AOS7_INCOMPLETE": "unregister"})

    def run_done(self, rid):
        """本回合起的 run 結束了嗎（提前 tock 用）：同 run 的 exit.json，或槽已經換人。"""
        slot, _, run = rid.rpartition("#")
        fslot = aos7_task.slot_dir(self.node, slot)
        ex = read_json(os.path.join(fslot, "exit.json"))
        if isinstance(ex, dict) and str(ex.get("run")) == run:
            return True
        b = read_json(os.path.join(fslot, "birth.json"))
        return isinstance(b, dict) and str(b.get("run")) != run

    def event(self, ev, **kw):
        self.last_event = dict(ev=ev, at=now(), **kw)
        self.d.log(ev=ev, node=self.node_id, **kw)

    def kill_if_leaving(self):
        """stop 帶 kill、或 unregister 帶 kill：收掉本 node 所有活任務。"""
        if (self.d.stopping and self.d.kill_on_stop) or (self.retire and self.retire_kill):
            self.d.kill_live(self.node_id, self.node)

    def reap_holder(self):
        """動作等 action.lock 逾時：持有者若是舊世代、仍是同一個程序就 SIGKILL；認不出身分就不殺，記人工恢復提示（2.5）。"""
        pid = reap_stale_owner(self.node, self.d.gen)
        if pid:
            self.event("stale-holder-kill", pid=pid)
            self.unverified = None
            return
        info = holder_unverified(self.node, self.d.gen)
        if not info:
            return
        self.err("action-lock", None, "stale-holder-unverified：%s。%s" % (info["why"], info["hint"]))
        if info["why"] != self.unverified:
            self.unverified = info["why"]
            self.event("stale-holder-unverified", pid=info["pid"], why=info["why"])
