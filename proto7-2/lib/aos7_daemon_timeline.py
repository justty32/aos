"""一條 tick-tock 時間線的迴圈（spec.md 2.1、2.2、2.5）：不變條件一 → pause → tick → 等（固定 interval 或提前 tock）→ tock → 等滿 interval。

迴圈本身是 daemon 裡的一個 thread；tick、tock 每次都是獨立程序（S-04）。起點是 proto7-1 lib/aos7_daemon_timeline.py。

由 daemon.check_nodes 建立，每條服務一個已登記 node（S-05、S-13）。讀 .aos/timeline.json、round.json
與任務槽的 birth.json／exit.json，tick/tock 子程序負責寫回合與任務檔；本模組只更新 daemon 記憶體狀態，
事件經 daemon 寫 status.json（及有 log.on 時的 log.jsonl），鎖接管另讀 action.owner.json（spec §2.5、§2.8、§9）。
"""
import json
import math
import os
import subprocess
import sys
import threading
import time

import aos7_task
from aos7_fs import (BIN, ROUND_CLOSED, ROUND_NONE, ROUND_OPEN, env_with_bin, holder_unverified, is_int, node_path, now,
                     read_json, read_round, reap_stale_owner)

POLL = 0.02
DEFAULT_INTERVAL_MS = 1000
ERROR_BACKOFF = 0.5          # 時間線出錯後的等待（也是不變條件一退避的起點）
RECOVER_BACKOFF_MAX = 8.0    # 退避最多到幾秒（2.1 第 1 步）
ACTION_TIMEOUT = 30.0        # tick／tock 一次最多跑幾秒（timeline.json 的 `action_timeout_s` 可改）
STOP_GRACE = 3.0             # daemon 停機時，正在跑的 tick／tock 最多再等幾秒
TIMEOUT_RC = -9
UNKNOWN_RC = 3               # tick／tock 推定不了（round.json 讀不到…）的退出碼


def clip(msg, limit=300):
    """把 msg 縮到約 limit 字：保留開頭（錯誤類型、根因）與結尾（路徑、提示），中間換成「…」（A2-08）。"""
    if len(msg) <= limit:
        return msg
    head = limit * 2 // 5
    return msg[:head] + " … " + msg[-(limit - head - 3):]


def run_prog(name, root, node_id, extra_env=None, gen=None, timeout=None, abort=None):
    """以獨立程序跑 bin/name，root／node_id 指定空間與時間線（spec §2.1、§2.5；S-04）。
    extra_env 加動作變數、gen 給世代、timeout 限秒數、abort 為無參數停止判定回呼。
    回 (退出碼, stdout 最後一行 JSON 或 None, stderr)；輸出不明回 None，逾時或 abort 為真則 kill 並回 -9。"""
    env = env_with_bin()
    # spec §2.1、§2.5：每次動作各自決定 early/incomplete，避免子 daemon 繼承父動作的回合標記。
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
    """讀 node/.aos/timeline.json，回 (interval_ms, early_tock, timeout_s, 錯誤或 None)（spec §1）。
    檔案可無（W12）；讀不懂用預設，interval 不合檢查時另回錯誤，timeout 不合則用預設。"""
    t = read_json(os.path.join(node, ".aos", "timeline.json"), {})
    t = t if isinstance(t, dict) else {}
    err = None
    ms = t.get("interval_ms", DEFAULT_INTERVAL_MS)
    # spec §1：有限非負數字就照用（註解疑點 timeline:76／83：不再另設 365 天上限、也不截掉小數）。
    if isinstance(ms, bool) or not isinstance(ms, (int, float)) or not math.isfinite(ms) or ms < 0:
        err = "interval_ms 要是有限非負數字，拿到 %r；先用 %d" % (ms, DEFAULT_INTERVAL_MS)
        ms = DEFAULT_INTERVAL_MS
    early = t.get("early_tock", False) is True
    v = t.get("action_timeout_s")
    tmo = float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and 0 < v < 1e6 else ACTION_TIMEOUT
    return ms, early, tmo, err


class Timeline(threading.Thread):
    """一條時間線。daemon 物件要提供 root、gen、stopping、stopping_since、kill_on_stop、is_paused(nid)、round_done(nid)、
    log(**kw)、kill_live(nid, node)。"""

    def __init__(self, daemon, node_id, ident):
        """建立 daemon 管理的 node_id 時間線；ident 是起線時 (st_dev, st_ino)（spec §2.1、§2.6）。
        回 None；僅初始化未啟動 thread，回合數讀不懂先顯示 0，開回合前仍會檢查磁碟。"""
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
        self.kick = None                 # wake／resume 的 monotonic 時刻；只有回合關上「之後」的才打斷第 6 步（A2-11）
        self.round_why = None            # check_round 判不出時的原因（寫進 last_error）
        self.recover_fails = 0
        self.owe_done = False
        self.unverified = None

    # ---------- 小工具 ----------

    def disk_round(self):
        """讀 round.json 供顯示回合數（spec §2.8），無額外參數，回整數。
        檔案讀不到或 round 不合型別時保留記憶體回合（初始 0），不據此推定回合已關。"""
        r = read_json(os.path.join(self.node, ".aos", "round.json"), {})
        v = r.get("round") if isinstance(r, dict) else None
        return v if is_int(v) else getattr(self, "round", 0)

    def err(self, prog, rc, msg, kind=None):
        """把 prog、rc 與 msg 記成此 node 最近錯誤，帶目前回合與時間（spec §2.8）。回 None。

        A2-08：`kind` 是錯誤類型（例 `stale-holder-unverified`、`round-unknown`），分欄放、不會被截掉；
        msg 太長時保留開頭與結尾、中間換成「…」（以前只留最後 300 字，深路徑會把開頭的錯誤類型與根因截掉）。"""
        self.last_error = {"prog": prog, "rc": rc, "round": self.round, "at": now(), "err": clip(msg or "")}
        if kind:
            self.last_error["kind"] = kind

    def stop_overdue(self):
        """判定 daemon 的停止寬限期是否已過，供動作程序 abort 使用（spec §2.5、§2.7）。
        無額外參數，回 bool；沒有停止起點回 False，時間用 monotonic 避免牆鐘跳動。"""
        since = getattr(self.d, "stopping_since", None)
        return since is not None and time.monotonic() - since > STOP_GRACE

    def done(self):
        """讀記憶體旗標判定 daemon 停止或 node 消失，無額外參數，回 bool（spec §2.6、§2.7）。
        不讀磁碟；不知道 node 是否消失時，須由 daemon 保留 gone 原值。"""
        return self.d.stopping or self.gone

    def leaving(self):
        """判定時間線應否結束，包含 done 與 unregister 的 retire（spec §2.3、§2.7）。
        無額外參數，回 bool；只讀既有旗標，不另推定檔案或程序是否存在。"""
        return self.done() or self.retire

    def sleep_until(self, t_end, kick_after=None):
        """等到 monotonic 時刻 t_end；kick_after 不是 None 時，在那個時刻之後送來的 wake／resume 會打斷等待（spec §2.1）。
        A2-11：回合中送來的 wake 照「回合中照舊」不起作用，也不留到回合後的 idle 才生效。
        回 None；停止或 retire 隨時可打斷，喚醒 Event 後仍重查條件。"""
        def kicked():
            """有沒有在 kick_after 之後收到 wake／resume。"""
            return kick_after is not None and self.kick is not None and self.kick >= kick_after
        while not self.leaving() and not kicked() and time.monotonic() < t_end:
            self.wake.wait(min(POLL, max(0.0, t_end - time.monotonic())))
            self.wake.clear()

    def backoff(self):
        """不變條件一無法確認／恢復時指數退避，0.5 秒起至 8 秒（spec §2.1、§2.2）。
        無額外參數，回 None；phase 記 error，停止或 retire 可提前離開等待。"""
        self.recover_fails += 1
        self.phase = "error"
        t = min(ERROR_BACKOFF * 2 ** (self.recover_fails - 1), RECOVER_BACKOFF_MAX)
        end = time.monotonic() + t
        while not self.leaving() and time.monotonic() < end:
            self.wake.wait(min(POLL * 5, end - time.monotonic()))

    def prog(self, name, extra=None, timeout=None):
        """以當前世代跑 name 動作，extra 給環境，timeout 覆蓋設定秒數（spec §2.5）。
        回 (退出碼, JSON 或 None, stderr)；非零記錯，逾時後嘗試辨識舊鎖持有者，不明則不殺。"""
        rc, out, err = run_prog(name, self.d.root, self.node_id, extra, gen=self.d.gen,
                                timeout=timeout or self.cfg_timeout, abort=self.stop_overdue)
        if rc:
            self.err(name.replace("aos7-", ""), rc, err)
        if rc == TIMEOUT_RC and out is None:
            self.reap_holder()
        return rc, out, err

    def check_round(self):
        """讀 round.json 更新 round_open，供不變條件一檢查（spec §2.2）。判定只用 aos7_fs.read_round（A2-02）：
        回 True＝明確 `open: true`；False＝明確 `open: false` 或確定沒有 round.json（新空間）；
        None＝不知道（讀不到、半寫、缺 open、型別不對），原因放 round_why，呼叫端只能退避、不 tick。"""
        st, _r, why = read_round(os.path.join(self.node, ".aos", "round.json"))
        self.round_why = why
        if st == ROUND_OPEN:
            self.round_open = True
        elif st in (ROUND_CLOSED, ROUND_NONE):
            self.round_open = False
        else:
            # spec §0、§2.2 三態：不明留 None，呼叫端只能退避，不能把它當成已關回合（以前缺 open／半寫當已關）。
            self.round_open = None
        return self.round_open

    # ---------- 迴圈 ----------

    def run(self):
        """thread 入口，重試 _loop 並隔離單條時間線例外（spec §2.1；S-05、S-06）。
        無額外參數，回 None；例外記錯等 0.5 秒再試，離開時一律標 stopped。"""
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
        """推進不變條件一、pause、tick、等待、tock、剩餘等待六步（spec §2.1、§2.2）。
        無額外參數，回 None；舊世代或 node 消失離開，讀不到回合則保留狀態並退避（P2-09）。"""
        self.cfg_timeout = ACTION_TIMEOUT
        while not self.leaving():
            ms, early, self.cfg_timeout, cerr = read_config(self.node)
            if cerr:
                self.err("timeline", None, cerr)
            # 1. spec §2.2 不變條件一：先檢查舊回合；內容損壞的回合數另由 tick 的 §3 fallback 處理。
            ro = self.check_round()
            if ro is None:
                self.err("round", None, "不知道上一回合關了沒，不 tick，退避後再看：%s" % self.round_why,
                         kind="round-unknown")
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
                    # spec §2.4：關回合才消耗 rounds；延後恢復成功時補扣，不能在失敗 tock 時先扣。
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
            # spec §0、§2.1：間隔靠 monotonic，ISO at 只供人看；牆鐘校時不會改變等待長度。
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
            if rc == UNKNOWN_RC:
                # P2-09：退出碼 3 表示無法推定，不是空回合；退避後重新檢查，不接著正常 tock。
                self.backoff()
                continue
            started = (out or {}).get("started") or []
            self.round = (out or {}).get("round") or self.disk_round()
            self.round_open = True
            # 4. 等
            self.phase = "running"
            while not self.leaving() and time.monotonic() < t_end:
                # P2-01：固定 interval 的這段仍在回合中，因此 wake 不縮短它；只在第 6 步看 kick。
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
                # spec §2.5：被截斷的 tick 可能已寫 round/birth，讓 tock 如實標 incomplete 而非宣稱完整。
                env["AOS7_INCOMPLETE"] = "tick"
            rc, out, err = self.prog("aos7-tock", env)
            if self.check_round():
                # tock 沒把回合關上：馬上補一次（同回合已有總結就只收尾）
                if not self.gone and not self.stop_overdue():
                    self.prog("aos7-tock", {"AOS7_EARLY": "0", "AOS7_INCOMPLETE": "tock"})
            if self.check_round() is not False:
                # spec §2.2、§2.4：含「不知道」都不算完成，欠下的 rounds 扣除等恢復確實關上才做。
                self.owe_done = True
                self.event("round-unclosed", round=self.round, rc=rc)
                continue   # 下一圈頂端走不變條件一
            closed_at = time.monotonic()
            self.d.round_done(self.node_id)
            # 6. 等滿 interval（wake、resume 打斷；只認回合關上之後送來的，A2-11）
            self.phase = "idle"
            self.sleep_until(t_end, kick_after=closed_at)
        if not self.gone:
            self.kill_if_leaving()
            if self.retire and self.check_round():
                self.prog("aos7-tock", {"AOS7_EARLY": "0", "AOS7_INCOMPLETE": "unregister"})

    def run_done(self, rid):
        """判定本回合 rid（槽#run）是否已結束，供提前 tock（spec §2.1 第 4 步）。
        同 run 有 exit，或 birth 的 run 是**另一個整數**（槽已換人）回 True；讀不到、壞掉、缺 run 都回 False，
        繼續等到 interval（註解疑點 timeline:311：缺 run 的 birth 以前會當已換人、准許提前 tock）。"""
        slot, _, run = rid.rpartition("#")
        fslot = aos7_task.slot_dir(self.node, slot)
        ex = read_json(os.path.join(fslot, "exit.json"))
        if isinstance(ex, dict) and str(ex.get("run")) == run:
            return True
        b = read_json(os.path.join(fslot, "birth.json"))
        return isinstance(b, dict) and is_int(b.get("run")) and str(b["run"]) != run

    def event(self, ev, **kw):
        """將事件名 ev 與欄位 kw 記為 node 最近事件，再轉給 daemon（spec §2.8、§9）。
        回 None；daemon 決定是否依 log.on 追加事件檔。"""
        self.last_event = dict(ev=ev, at=now(), **kw)
        self.d.log(ev=ev, node=self.node_id, **kw)

    def kill_if_leaving(self):
        """stop 或 unregister 帶 kill 時，請 daemon 收此 node 活任務（spec §2.7；P2-10）。
        無額外參數，回 None；未要求 kill 就不動，程序身分判定交給 kill_live。"""
        if (self.d.stopping and self.d.kill_on_stop) or (self.retire and self.retire_kill):
            self.d.kill_live(self.node_id, self.node)

    def reap_holder(self):
        """動作逾時後嘗試接管舊世代鎖持有者（spec §2.5），無額外參數，回 None。
        只有 gen 較舊且 pid/starttime 確認同一程序才殺；不知道則保留、記人工恢復提示，重複提示去重。"""
        pid = reap_stale_owner(self.node, self.d.gen)
        if pid:
            self.event("stale-holder-kill", pid=pid)
            self.unverified = None
            return
        info = holder_unverified(self.node, self.d.gen)
        if not info:
            return
        self.err("action-lock", None, "stale-holder-unverified：%s。%s" % (info["why"], info["hint"]),
                 kind="stale-holder-unverified")
        if info["why"] != self.unverified:
            self.unverified = info["why"]
            self.event("stale-holder-unverified", pid=info["pid"], why=info["why"])
