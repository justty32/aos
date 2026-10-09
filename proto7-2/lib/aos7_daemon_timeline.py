"""一條 node 的時間線（spec.md 2.1、2.2、2.5）：不變條件一 → pause → tick → 等（固定 interval 或提前 tock）→ tock → 等滿 interval。

時間線是 daemon 裡的一個 thread；tick、tock 每次都是獨立程序（S-04）。這裡只更新 daemon 記憶體裡的狀態，檔案由 tick／tock 寫。
tick／tock 的退出碼只看三種：0＝做了；3＝不知道；其他＝失敗。後兩者都退避、不算一個回合。
"""
import json
import math
import os
import subprocess
import sys
import threading
import time

import aos7_task
from aos7_fs import (BIN, N, OK, ROUND_CLOSED, ROUND_NONE, ROUND_OPEN, env_with_bin, fact, hold, is_int, node_path, now,
                     read_json, read_round, reap_stale_owner)

POLL = 0.02
DEFAULT_INTERVAL_MS = 1000
ERROR_BACKOFF = 0.5          # 出錯後的等待，也是退避的起點
RECOVER_BACKOFF_MAX = 8.0    # 退避最多到幾秒
ACTION_TIMEOUT = 30.0        # tick／tock 一次最多跑幾秒（timeline.json 的 `action_timeout_s` 可改）
STOP_GRACE = 3.0             # daemon 停機時，正在跑的 tick／tock 最多再等幾秒
TIMEOUT_RC = -9
UNKNOWN_RC = 3


def run_prog(name, root, node_id, extra_env=None, gen=None, timeout=None, abort=None):
    """跑 bin/name（tick 或 tock），回 (退出碼, stdout 最後一行 JSON 或 None, stderr)。逾時或 abort() 為真就 SIGKILL、回 -9。
    AOS7_EARLY／AOS7_INCOMPLETE 每次重給，不從 daemon 自己的環境繼承（子 daemon 的父任務可能帶著）。"""
    env = env_with_bin()
    for k in ("AOS7_EARLY", "AOS7_INCOMPLETE"):
        env.pop(k, None)
    env.update(extra_env or {})
    if gen is not None:
        env["AOS7_GEN"] = str(gen)
    p = subprocess.Popen([sys.executable, os.path.join(BIN, name), root, node_id],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    t0 = time.monotonic()
    while True:
        try:
            stdout, stderr = p.communicate(timeout=0.1)
            break
        except subprocess.TimeoutExpired:
            why = ("timeout after %.1fs" % timeout if timeout is not None and time.monotonic() - t0 > timeout else
                   "aborted: daemon stopping" if abort is not None and abort() else None)
            if why:
                p.kill()
                stdout, stderr = p.communicate()
                return TIMEOUT_RC, None, ("%s: %s killed (%s)" % (stderr or "", name, why)).strip()
    lines = stdout.strip().splitlines()
    try:
        out = json.loads(lines[-1]) if lines else None
    except ValueError:
        out = None
    return p.returncode, out, stderr.strip()


def read_config(node):
    """讀 timeline.json（可以沒有），回 (interval_ms, early_tock, timeout_s, 錯誤或 None)。這是別人寫的設定：讀不到（U）、
    讀不懂或數值不合（B）都用預設並回一句錯誤，修好下一回合生效。interval 0 合法（不等）。"""
    try:
        st, t = fact(os.path.join(node, ".aos", "timeline.json"))
        err = None
        if st not in (OK, N) or (st == OK and not isinstance(t, dict)):
            err = "timeline.json %s，先全用預設" % (t if st != OK else "不是物件")
        t = t if st == OK and isinstance(t, dict) else {}
        ms = t.get("interval_ms", DEFAULT_INTERVAL_MS)
        # 先型別、再範圍、最後 isfinite，避免巨大整數轉 float 溢位。
        if isinstance(ms, bool) or not isinstance(ms, (int, float)) or not (0 <= ms <= 86400000 * 365) \
                or not math.isfinite(ms):
            err = "interval_ms 要是不超過一年的非負數字，拿到 %.60r；先用 %d" % (ms, DEFAULT_INTERVAL_MS)
            ms = DEFAULT_INTERVAL_MS
        v = t.get("action_timeout_s", ACTION_TIMEOUT)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not (0 < v < 1e6):
            err = err or "action_timeout_s 要是 (0, 1e6) 的數字，拿到 %.60r；先用 %g" % (v, ACTION_TIMEOUT)
            v = ACTION_TIMEOUT
        early = t.get("early_tock", False)
        if not isinstance(early, bool):
            err = err or "early_tock 要是 true／false，拿到 %.60r；先用 false" % (early,)
            early = False
        return ms, early, float(v), err
    except Exception as e:   # noqa: BLE001  驗證本身永不炸（A8-11）：任何意外都全用預設並記錯
        return DEFAULT_INTERVAL_MS, False, ACTION_TIMEOUT, "timeline.json 驗證失敗（%.80r），先全用預設" % e


class Timeline(threading.Thread):
    """一條時間線。daemon 要提供 root、gen、stopping、stopping_since、kill_on_stop、is_paused、round_done、log、kill_live。"""

    def __init__(self, daemon, node_id, ident):
        super().__init__(name="tl:" + node_id, daemon=True)
        self.d = daemon
        self.node_id = node_id
        self.node = node_path(daemon.root, node_id)
        self.node_ident = ident              # 起線時的 (st_dev, st_ino)：換了就是被搬走或換掉（2.6）
        self.phase = "idle"
        self.round = self.disk_round()
        self.interval_ms = None
        self.early_tock = False
        self.last_error = None
        self.last_event = None
        self.round_open = None               # True／False／None＝不知道
        self.recovery_pending = False
        self.gone = False                    # node 消失：不再 tick／tock
        self.retire = False                  # unregister：本回合收完就結束
        self.retire_kill = True
        self.wake = threading.Event()
        self.kick = None                     # wake／resume 的 monotonic 時刻（分辨回合中、回合後送來的）
        self.round_why = None                # check_round 判不出時的原因
        self.recover_fails = 0
        self.owe_round = None                # 待結算回合號：確知關上才扣 rounds 倒數
        self.unverified = None               # 上一次認不出的鎖持有者原因（事件去重）

    # ---------- 小工具 ----------

    def disk_round(self):
        """round.json 的回合數，給 status 顯示用；讀不到沿用記憶體裡的（初始 0）。不拿來判定回合關了沒。"""
        r = read_json(os.path.join(self.node, ".aos", "round.json"), {})
        v = r.get("round") if isinstance(r, dict) else None
        return v if is_int(v) else getattr(self, "round", 0)

    def err(self, where, rc, msg, kind=None):
        """記這個 node 最近一筆錯誤（hold 格式＋rc、round）。kind 沒給時照退出碼：3＝unknown，其他＝fail。"""
        self.last_error = hold(where, kind or ("unknown" if rc == UNKNOWN_RC else "fail"), msg or "", rc=rc,
                               round=self.round)

    def stop_overdue(self):
        """daemon 停機的寬限期過了沒（過了就收掉還在跑的 tick／tock）。"""
        since = getattr(self.d, "stopping_since", None)
        return since is not None and time.monotonic() - since > STOP_GRACE

    def leaving(self):
        """時間線該結束了嗎：daemon 停機、node 消失、或已取消登記。"""
        return self.d.stopping or self.gone or self.retire

    def sleep_until(self, t_end, kick_after=None):
        """等到 monotonic 時刻 t_end；kick_after 之後送來的 wake／resume 會打斷（回合中送來的不留到這裡才生效）。"""
        def kicked():
            return kick_after is not None and self.kick is not None and self.kick >= kick_after
        while not self.leaving() and not kicked() and time.monotonic() < t_end:
            self.wake.wait(min(POLL, max(0.0, t_end - time.monotonic())))
            self.wake.clear()

    def backoff(self):
        """退避：0.5 秒起加倍、最多 8 秒；phase 記 error。停機或取消登記隨時打斷。"""
        self.recover_fails += 1
        self.phase = "error"
        end = time.monotonic() + min(ERROR_BACKOFF * 2 ** min(self.recover_fails - 1, 10), RECOVER_BACKOFF_MAX)
        while not self.leaving() and time.monotonic() < end:
            self.wake.wait(min(POLL * 5, end - time.monotonic()))
            self.wake.clear()

    def prog(self, name, extra=None, timeout=None):
        """用現在的世代跑 tick 或 tock；非零退出碼記錯，逾時被收掉時試著接管舊世代的鎖持有者。"""
        rc, out, err = run_prog(name, self.d.root, self.node_id, extra, gen=self.d.gen,
                                timeout=timeout or self.cfg_timeout, abort=self.stop_overdue)
        if rc:
            self.err(name.replace("aos7-", ""), rc, err)
        if rc == TIMEOUT_RC and out is None:
            self.reap_holder()
        return rc, out, err

    def check_round(self):
        """不變條件一（spec §2.2）：回 True＝明確開著、False＝明確關了或新空間、None＝不知道（原因放 round_why，只能退避）。"""
        st, _r, why = read_round(os.path.join(self.node, ".aos", "round.json"))
        self.round_why = why
        self.round_open = True if st == ROUND_OPEN else False if st in (ROUND_CLOSED, ROUND_NONE) else None
        return self.round_open

    # ---------- 迴圈 ----------

    def run(self):
        """thread 入口：迴圈丟例外只記下來、等一下接著跑（一條時間線出事不拖垮整個 daemon）。"""
        try:
            while True:
                try:
                    self._loop()
                    return
                except Exception as e:   # noqa: BLE001
                    self.err("timeline", None, repr(e))
                    self.phase = "error"
                    self.wake.wait(ERROR_BACKOFF)
                    if self.leaving():
                        return
        finally:
            self.phase = "stopped"

    def _loop(self):
        """spec §2.1 的六步。"""
        self.cfg_timeout = ACTION_TIMEOUT
        while not self.leaving():
            ms, early, self.cfg_timeout, cerr = read_config(self.node)
            if cerr:
                self.err("timeline", None, cerr)
            # 1. 不變條件一：舊回合確知已關才開下一回合；開著的先 tock 收掉
            ro = self.check_round()
            if ro is None:
                self.err("round", None, "不知道上一回合關了沒，不 tick，退避後再看：%s" % self.round_why,
                         kind="round-unknown")
                self.backoff()
                continue
            if ro is False and self.owe_round is not None:
                self.d.round_done(self.node_id)
                self.owe_round = None
                continue   # 補扣後回頂端重看 pause
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
                if self.owe_round is not None:   # 回合確知關上才扣 rounds 倒數
                    self.owe_round = None
                    self.d.round_done(self.node_id)
                continue   # 回到頂端重新看 pause 與倒數
            self.recover_fails = 0
            # 2. pause
            if self.d.is_paused(self.node_id):
                self.phase = "paused"
                self.wake.wait(POLL)
                self.wake.clear()
                continue
            # 3. tick（間隔照 monotonic 算，牆鐘校時不影響）
            self.interval_ms, self.early_tock = ms, early
            t0 = time.monotonic()
            t_end = t0 + ms / 1000.0
            self.kick = None
            self.phase = "tick"
            rc, out, err = self.prog("aos7-tick")
            tick_cut = rc == TIMEOUT_RC and out is None
            if (out or {}).get("stale"):
                self.event("stale", prog="tick")
                return
            if (out or {}).get("gone"):
                self.wake.wait(POLL)
                continue
            if rc and not tick_cut:
                # 不知道（3）或失敗（例外、退出碼 1）都不是一個回合：退避後回頂端（tick 若已開了回合，頂端先 tock 收掉），
                # 不扣 rounds 倒數（G2）。被逾時收掉的 tick 照常往下 tock，總結標 incomplete。
                self.backoff()
                continue
            started = (out or {}).get("started") or []
            self.round = (out or {}).get("round") or self.disk_round()
            self.round_open = True
            # 4. 等：固定 interval；early_tock 時本回合起的任務都結束就提前。固定 interval 的回合中送來 wake／resume
            #    ＝提前結束這回合（wake 是明確的請求）；early_tock 的回合中送來的不起作用
            self.phase = "running"
            woke = False
            while not self.leaving() and time.monotonic() < t_end:
                if early and all(self.run_done(r) for r in started):
                    break
                if not early and self.kick is not None and self.kick >= t0:
                    woke = True
                    break
                self.wake.wait(POLL)
                self.wake.clear()
            if self.gone:
                return
            self.kill_if_leaving()
            # 5. tock；沒關上就馬上補一次（同回合已有總結就只收尾）
            self.phase = "tock"
            env = {"AOS7_EARLY": "1" if time.monotonic() < t_end and not self.leaving() else "0"}
            if tick_cut:
                env["AOS7_INCOMPLETE"] = "tick"   # 被截斷的 tick 可能已寫了 round／birth：總結如實標出來
            rc, out, err = self.prog("aos7-tock", env)
            if self.check_round() and not self.gone and not self.stop_overdue():
                self.prog("aos7-tock", {"AOS7_EARLY": "0", "AOS7_INCOMPLETE": "tock"})
            if self.check_round() is not False:
                # 不知道也不算關上：倒數等恢復確實關上才扣，頂端走不變條件一
                self.owe_round = self.round
                self.event("round-unclosed", round=self.round, rc=rc)
                continue
            closed_at = time.monotonic()
            self.d.round_done(self.node_id)
            if woke:
                self.event("woke", round=self.round)   # 被 wake 提前結束的回合不等剩下的 interval
                continue
            # 6. 等滿 interval（只認回合關上之後送來的 wake／resume）
            self.phase = "idle"
            self.sleep_until(t_end, kick_after=closed_at)
        if not self.gone:
            self.kill_if_leaving()
            if self.retire and self.check_round():
                self.prog("aos7-tock", {"AOS7_EARLY": "0", "AOS7_INCOMPLETE": "unregister"})

    def run_done(self, rid):
        """early_tock 用：本回合起的 rid（槽#run）結束了沒——同 run 有 exit.json，或槽已換成另一個整數 run。
        讀不到、壞掉、缺 run 都當還沒結束（繼續等到 interval）。"""
        slot, _, run = rid.rpartition("#")
        fslot = aos7_task.slot_dir(self.node, slot)
        ex = read_json(os.path.join(fslot, "exit.json"))
        if isinstance(ex, dict) and str(ex.get("run")) == run:
            return True
        b = read_json(os.path.join(fslot, "birth.json"))
        return isinstance(b, dict) and is_int(b.get("run")) and str(b["run"]) != run

    def event(self, ev, **kw):
        """記這個 node 最近一件事，並交給 daemon（有 log.on 才寫流水帳）。"""
        self.last_event = dict(ev=ev, at=now(), **kw)
        self.d.log(ev=ev, node=self.node_id, **kw)

    def kill_if_leaving(self):
        """stop 或 unregister 帶 kill 時，收這個 node 的活任務。"""
        if (self.d.stopping and self.d.kill_on_stop) or (self.retire and self.retire_kill):
            self.d.kill_live(self.node_id, self.node)

    def reap_holder(self):
        """動作逾時後：舊世代的鎖持有者認得出就收掉；認不出＝不知道，不殺，記一筆（人工步驟見 modules/diag/README.md）。"""
        pid, why = reap_stale_owner(self.node, self.d.gen)
        if pid:
            self.event("stale-holder-kill", pid=pid)
            self.unverified = None
        elif why:
            self.err("action-lock", None, "stale-holder-unverified：%s；沒殺任何程序" % why, kind="stale-holder-unverified")
            if why != self.unverified:
                self.unverified = why
                self.event("stale-holder-unverified", why=why)
