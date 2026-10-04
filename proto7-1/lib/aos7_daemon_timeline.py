"""一條 tick-tock 時間線的迴圈：tick → 等任務或 interval → tock → 等滿 interval（spec.md 第 2 節，S-05、S-08、S-09）。

迴圈本身是 daemon 裡的一個 thread；tick、tock 每次都是獨立程序（S-04 的折衷，見 problems-core.md P-01）。
由 aos7_daemon.Daemon 掃到 node 後建立並啟動；讀該 node 的 .aos/timeline.json、round.json 與任務狀態，
透過 tick／tock 寫回合、任務及 rounds.jsonl，透過 daemon.log 寫 root/.aosd/log.jsonl。
本檔處理 spec §2 的逾時、恢復與停止，§3 的回合觀測，以及 §6～§7 的收任務／tock 收尾。
"""
import json
import math
import os
import subprocess
import sys
import threading
import time

import aos7_task
from aos7_fs import BIN, env_with_bin, holder_unverified, node_path, now, read_json, reap_stale_owner

POLL = 0.02
DEFAULT_INTERVAL_MS = 1000
ERROR_BACKOFF = 0.5    # 時間線迴圈丟例外後，等多久再接著跑
RECOVER_BACKOFF_MAX = 8.0   # 沒關的回合恢復一直失敗時，重試間隔（從 ERROR_BACKOFF 加倍）最多到幾秒（astra-7 H-01）
ACTION_TIMEOUT = 30.0  # tick／tock 一次最多跑幾秒（timeline.json 的 `action_timeout_s` 可改）
STOP_GRACE = 3.0       # daemon 停機時，正在跑的 tick／tock 最多再等幾秒
TIMEOUT_RC = -9


def run_prog(name, root, node_id, extra_env=None, gen=None, timeout=None, abort=None):
    """跑 `bin/<name> <root> <node-id>`，回 (returncode, 最後一行 JSON 或 None, stderr)。

    timeout 秒內沒結束、或 abort() 回真（daemon 停機等太久），SIGKILL 這個動作，rc＝TIMEOUT_RC、stderr 說明
    （一條線的 tick 卡在 I/O 不能拖住整個 daemon；eval/2026-10-03-batch-tick）。

    參數 name／root／node_id 指定動作與空間；extra_env 加環境、gen 限世代、timeout 是秒數、abort 是中止判斷。
    最後一行讀不成 JSON 回 None；能解析時原樣回傳該 JSON 值（spec §2）。
    """
    env = env_with_bin()
    env.update(extra_env or {})
    if gen is not None:
        env["AOS7_GEN"] = str(gen)   # tick／tock 拿到 action.lock 後比對，舊 daemon 的動作不寫（spec §2；astra-4 I-01）
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


class Timeline(threading.Thread):
    """一條時間線。daemon 物件要提供 root、is_paused(node_id)、stopping、kill_on_stop、log(**kw)。"""

    def __init__(self, daemon, node_id):
        """以 daemon 管理物件與 node_id 建立尚未啟動的時間線；初始化回合讀不到先用 0，回 None（spec §2、§3）。"""
        super().__init__(name="tl:" + node_id, daemon=True)
        self.d = daemon
        self.node_id = node_id
        self.node = node_path(daemon.root, node_id)
        self.phase = "idle"
        self.round = 0
        self.round = self.disk_round()   # round.json 壞掉（`[]`、字串）當 0，不讓 daemon 退出（probes/chaos B1）
        self.interval_ms = None      # 最近一回合實際用的 interval
        self.last_error = None       # 最近一次 tick／tock 失敗（rc≠0）
        self.gone = False            # node 消失：停止這條舊時間線，不再對舊 id 安排 tock（spec §2；Q4）
        self.wake = threading.Event()
        self.kick = False            # daemon ctl `wake`：不等滿 interval，馬上開下一回合（probes/event N1）
        self.check_unclosed = True   # 開回合前先看有沒有沒 tock 完的回合（第一次、或上一次 tock 沒確認關上；astra-7 H-01）
        self.recover_fails = 0       # 沒關的回合連續恢復失敗幾次（退避用）
        self.owe_done = False        # 這段自己開的回合 tock 沒關成：恢復關上後才算 round_done（resume rounds 的倒數）
        self.unverified = None       # 上次記過的「認不出持鎖者」原因（同一個只記一次；astra-6 G-10）

    def disk_round(self):
        """回合數以 round.json 為準（tick 寫了新回合卻沒印 stdout 時，記憶體裡的會落後）。

        無額外參數；回整數回合，讀不到／不是整數則沿用 self.round（初始化時為 0；spec §2、§3）。
        """
        r = read_json(os.path.join(self.node, ".aos", "round.json"), {})
        v = r.get("round") if isinstance(r, dict) else None
        return v if isinstance(v, int) and not isinstance(v, bool) else self.round

    def note_error(self, prog, rc, err):
        """tick／tock 失敗時記下 last_error（status.json 會帶出來）；成功不清，留著給人看最後一次出錯。

        參數 prog 是動作名、rc 是退出碼、err 是錯誤文字；rc 為假值就不更新，回 None（spec §2）。
        """
        if rc:
            self.last_error = {"prog": prog, "rc": rc, "round": self.round, "at": now(),
                               "err": (err or "")[-300:]}

    def interval(self):
        """timeline.json 的 interval_ms；值不對用預設並記 last_error，時間線不死（probes/selfmod bug 3）。

        無額外參數；回秒數並更新 interval_ms。檔案讀不到或非物件用預設，不另記格式錯誤（spec §2）。
        """
        t = read_json(os.path.join(self.node, ".aos", "timeline.json"), {})
        ms = t.get("interval_ms", DEFAULT_INTERVAL_MS) if isinstance(t, dict) else DEFAULT_INTERVAL_MS
        # 先看型別與範圍、最後才 isfinite：10**309 這種大整數丟進 isfinite 會 OverflowError（astra-5 F-06）
        if isinstance(ms, bool) or not isinstance(ms, (int, float)) or not (0 <= ms <= 86400000 * 365) \
                or not math.isfinite(ms):   # 負數也算壞值；0＝不等（實際 1 ms；probes/chaos B9）；NaN 比較一律 False
            self.last_error = {"prog": "timeline", "rc": None, "round": self.round, "at": now(),
                               "err": "interval_ms 要是數字，拿到 %r；先用 %d" % (ms, DEFAULT_INTERVAL_MS)}
            ms = DEFAULT_INTERVAL_MS
        self.interval_ms = max(int(ms), 1)   # 這回合實際用的（status.json 帶出來；astra-4 I-08）
        return self.interval_ms / 1000.0

    def action_timeout(self):
        """讀 timeline.json 的動作上限；無額外參數，回秒數，讀不到或值不在 (0, 1e6) 就回 30 秒（spec §2）。"""
        t = read_json(os.path.join(self.node, ".aos", "timeline.json"), {})
        v = t.get("action_timeout_s") if isinstance(t, dict) else None
        return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and 0 < v < 1e6 else ACTION_TIMEOUT

    def stop_overdue(self):
        """daemon 停機已經超過 STOP_GRACE 秒：正在跑的動作別再等了。

        無額外參數；回布林，未登記 stopping_since 就回 False，用單調時間避免牆鐘校正干擾（spec §2）。
        """
        since = getattr(self.d, "stopping_since", None)
        return since is not None and time.monotonic() - since > STOP_GRACE

    def done(self):
        """查 daemon 停機或 node 已消失的記憶體旗標；無額外參數，回布林，不另外探測磁碟（spec §2）。"""
        return self.d.stopping or self.gone

    def sleep_until(self, t_end):
        """等到單調時間 t_end，或 wake 控制／停機／消失提前打斷；回 None，供回合後 idle 等待（spec §2）。"""
        while not self.done() and not self.kick and time.monotonic() < t_end:
            self.wake.wait(min(POLL, max(0.0, t_end - time.monotonic())))

    def run(self):
        """供 Thread.start 呼叫的入口；無額外參數，捕捉時間線例外後退避重試，正常結束回 None（spec §2）。"""
        try:
            while True:
                try:
                    self._loop()
                    return
                except Exception as e:   # 一條時間線出事不拖垮整個 daemon（S-06），也不永久停掉：記下來、等一下再接著跑（astra-4 I-06）
                    self.last_error = {"prog": "timeline", "rc": None, "round": self.round, "at": now(),
                                       "err": repr(e)[-300:]}
                    try:
                        self.d.log(ev="error", node=self.node_id, msg=repr(e))
                    except Exception:
                        pass
                    self.phase = "error"
                    self.wake.wait(ERROR_BACKOFF)
                    if self.done():
                        return
        finally:
            self.phase = "stopped"

    def _loop(self):
        """執行 tick、等待、tock 與恢復狀態機；無額外參數，停機／node 消失／tick 過期時回 None（spec §2）。"""
        while not self.done():
            # spec §2：pause 擋新回合；目前此判斷也會擋住 error 回合恢復，status 的侷限見 K-02。
            if self.d.is_paused(self.node_id):
                self.phase = "paused"
                self.wake.wait(POLL)
                continue
            if self.check_unclosed:
                if not self.close_unclosed():
                    # 回合還開著（恢復也失敗：持續 I/O 錯、讀回不確定）：不開下一回合、不讓 round 往前跳過沒提交的總結，
                    # phase=error、last_error 留著，退避後再試（astra-7 H-01）
                    self.recover_fails += 1
                    self.note_unclosed(None)
                    self.phase = "error"
                    self.wake.wait(min(ERROR_BACKOFF * 2 ** (self.recover_fails - 1), RECOVER_BACKOFF_MAX))
                    continue
                self.check_unclosed = False
                self.recover_fails = 0
                if self.owe_done:
                    self.owe_done = False
                    self.d.round_done(self.node_id)
                # 已知問題 K-02：恢復倒數可能剛觸發 pause，卻未回迴圈頂端重查就接著 tick（未修，proto7-2 重做）
            t0 = time.monotonic()
            t_end = t0 + self.interval()
            self.kick = False
            self.phase = "tick"
            tmo = self.action_timeout()
            rc, out, err = run_prog("aos7-tick", self.d.root, self.node_id, gen=getattr(self.d, "gen", None),
                                    timeout=tmo, abort=self.stop_overdue)
            tick_cut = rc == TIMEOUT_RC and out is None
            if (out or {}).get("stale"):
                self.d.log(ev="stale", node=self.node_id, prog="tick")   # 換了世代（不該發生在自己身上）：停這條線
                return
            if (out or {}).get("gone"):
                self.wake.wait(POLL)       # node 剛消失、daemon 還沒掃到：不開回合，等掃描收掉這條（probes/subtimeline 1）
                continue
            started = (out or {}).get("started", [])
            self.round = (out or {}).get("round") or self.disk_round()
            self.note_error("tick", rc, err)
            if tick_cut:
                self.reap_holder()   # 在 note_error 之後：認不出持鎖者的說明留在 last_error（astra-6 G-10）
            self.d.log(ev="tick", node=self.node_id, round=self.round, started=started, rc=rc,
                       **({"err": err[-500:]} if rc else {}), **({"incomplete": True} if tick_cut else {}))
            self.phase = "running"
            # spec §2、S-09：只等這次 tick 起的任務；舊長命任務可跨回合，不應讓每圈都等滿 interval。
            while not self.done() and time.monotonic() < t_end:
                if not any(aos7_task.is_live(aos7_task.task_state(aos7_task.task_dir(self.node, t)))
                           for t in started):
                    break                      # 本回合起的都結束了：tock 提前進場
                self.wake.wait(POLL)
            if self.gone:
                return
            self.kill_if_stopping()
            self.phase = "tock"
            early = time.monotonic() < t_end
            env = {"AOS7_EARLY": "1" if early else "0"}
            if tick_cut:
                env["AOS7_INCOMPLETE"] = "tick"   # 這回合的 tick 被逾時收掉：總結標 incomplete
            rc, out, err = run_prog("aos7-tock", self.d.root, self.node_id, env, gen=getattr(self.d, "gen", None),
                                    timeout=tmo, abort=self.stop_overdue)
            self.note_error("tock", rc, err)
            tock_cut = rc == TIMEOUT_RC and out is None
            self.d.log(ev="tock", node=self.node_id, round=self.round, rc=rc,
                       ended=(out or {}).get("ended"), early=early,
                       **({"err": err[-500:]} if rc else {}),
                       **({"incomplete": True} if tock_cut else {}))
            if tock_cut:
                self.reap_holder()
            if self.round_open():
                # tock 沒把回合關上：逾時被殺、非零退出（讀回確認失敗…）、或印了不確定的結果。馬上補一次（同回合已有總結就只收尾）
                self.replay_tock()
            if self.round_open() and not self.done():
                # 補的也沒關上：下一次 tick 之前先走「沒關的回合」恢復，恢復成功前不開新回合（astra-7 H-01）
                self.check_unclosed = True
                self.owe_done = True
                self.note_unclosed(rc)
                self.d.log(ev="round-unclosed", node=self.node_id, round=self.round, rc=rc)
                self.phase = "error"
                continue
            self.d.round_done(self.node_id)   # resume 帶 rounds 的倒數（probes/sched N2）；依 round_open 判斷，未知誤判見 K-01
            self.phase = "idle"
            self.sleep_until(t_end)
        if not self.gone:
            self.kill_if_stopping()

    def note_unclosed(self, rc):
        """回合沒關上：last_error 說明（前面是原因，後面接 tock 的 stderr 末段）。

        參數 rc 是這次退出碼（None 時沿用）；保留前次錯誤末段並補回合與重試次數，回 None（spec §2）。
        """
        prev = (self.last_error or {}).get("err") or ""
        if prev.startswith("第 "):
            prev = prev.split("；", 1)[-1]
        self.last_error = {"prog": "tock", "rc": rc if rc is not None else (self.last_error or {}).get("rc"),
                           "round": self.round, "at": now(),
                           "err": "第 %s 回合沒關上（tock 失敗或讀回不確定），恢復成功前不開下一回合（已試 %d 次）；%s" % (
                               self.round, self.recover_fails, prev[-200:])}

    def round_open(self):
        """round.json 還是 open: true 嗎（node 不在、讀不到、壞掉都當沒開著：交給掃描／tick 的既有路徑）。

        無額外參數；回布林。目前把不確定也回 False，尚未落實生命週期決議的三態（spec §2、§3；K-01）。
        """
        if self.gone:
            return False
        # 已知問題 K-01：round.json 讀不到／壞掉也當已關，下一個 tick 可能跳過未提交回合（未修，proto7-2 重做）
        r = read_json(os.path.join(self.node, ".aos", "round.json"), {})
        return isinstance(r, dict) and r.get("open") is True

    def close_unclosed(self):
        """round.json 還是 open: true（node 回合中消失又出現、daemon 回合中死掉重開、上一次 tock 失敗沒關上）：先 tock 一次
        嘗試把它關掉、避免 rounds.jsonl 缺號，總結標 `incomplete: "unclosed"`（probes/chaos B8）；同回合已有總結的只收尾、不寫第二行。
        回 True＝目前判斷已關／沒開／動作過期；False＝仍讀到 open，呼叫的人不能開下一回合（astra-7 H-01）。

        無額外參數；回布林，讀不到 round.json 目前也算 True，動作回 stale 亦回 True 交下次 tick 收尾（spec §2）。
        """
        if not self.round_open():
            return True
        self.phase = "tock"
        rc, out, err = run_prog("aos7-tock", self.d.root, self.node_id, {"AOS7_EARLY": "0", "AOS7_INCOMPLETE": "unclosed"},
                                gen=getattr(self.d, "gen", None), timeout=self.action_timeout(), abort=self.stop_overdue)
        self.note_error("tock", rc, err)
        if rc == TIMEOUT_RC and out is None:
            self.reap_holder()
        self.d.log(ev="tock", node=self.node_id, round=self.round, rc=rc, ended=(out or {}).get("ended"),
                   incomplete="unclosed", **({"err": err[-500:]} if rc else {}),
                   **({"replayed": True} if (out or {}).get("replayed") else {}))
        if (out or {}).get("stale"):
            return True   # 換了世代：留給 tick 的 stale 路徑停這條線
        self.phase = "idle"
        return not self.round_open()

    def reap_holder(self):
        """動作等 action.lock 逾時：持有者若是舊世代、仍是同一個程序（pid＋啟動時間），SIGKILL 它，
        下一個動作就拿得到鎖（daemon 重開後接管舊動作；astra-5 F-04）。不 unlink 鎖檔。

        無額外參數、回 None；身分不明不殺，鎖仍有人拿時記原因；比較 gen 防新動作被舊 daemon 回收（spec §2）。
        """
        gen = getattr(self.d, "gen", None)
        # spec §2：PID 會重用，須連 /proc 的 starttime 一起驗證才回收；不能只因等鎖逾時就殺某 PID。
        # 不 unlink action.lock：舊持有者的 inode 不會因此解鎖，反讓新動作拿另一 inode 同時寫（astra-5 F-04）。
        pid = reap_stale_owner(self.node, gen)
        if pid:
            self.d.log(ev="stale-holder-kill", node=self.node_id, pid=pid)
            self.unverified = None
            return
        # 沒殺：鎖真的有人拿著卻認不出身分（缺欄位、讀不到 starttime、對不上）。照樣不殺（防誤殺），
        # 但 status 的 last_error 與 log 說清楚原因與人工恢復方法（astra-6 G-10）
        info = holder_unverified(self.node, gen)
        if not info:
            return
        self.last_error = {"prog": "action-lock", "rc": None, "round": self.round, "at": now(),
                           "err": "stale-holder-unverified：%s。%s" % (info["why"], info["hint"])}
        if info["why"] != self.unverified:   # 同一個原因只記一次 log
            self.unverified = info["why"]
            self.d.log(ev="stale-holder-unverified", node=self.node_id, pid=info["pid"], why=info["why"],
                       hint=info["hint"])

    def replay_tock(self):
        """tock 被逾時收掉、round.json 還開著：馬上補一次 tock（AOS7_INCOMPLETE=tock）。總結已經寫過的話 tock 只關回合、
        不寫第二行，round.json 標 `incomplete`／`replayed`；沒寫過就寫一行標 `incomplete: "tock"` 的總結（astra-5 F-05）。
        停機已超時、node 消失時不補，留給下一次「沒關的回合」流程。

        無額外參數、回 None；round.json 讀不到／非 open 也不補。一般非零退出而仍 open 時同樣由主迴圈呼叫（spec §2、§7）。
        """
        if self.gone or self.stop_overdue():
            return
        r = read_json(os.path.join(self.node, ".aos", "round.json"), {})
        if not (isinstance(r, dict) and r.get("open") is True):
            return
        rc, out, err = run_prog("aos7-tock", self.d.root, self.node_id, {"AOS7_EARLY": "0", "AOS7_INCOMPLETE": "tock"},
                                gen=getattr(self.d, "gen", None), timeout=self.action_timeout(), abort=self.stop_overdue)
        self.note_error("tock", rc, err)
        self.d.log(ev="tock", node=self.node_id, round=self.round, rc=rc, ended=(out or {}).get("ended"),
                   incomplete="tock", replay=True, **({"replayed": True} if (out or {}).get("replayed") else {}))

    def kill_if_stopping(self):
        """daemon stop 帶 kill：收掉本 node 所有活任務。

        無額外參數、回 None；未停機或未要求 kill 就略過，各任務收尾結果交 daemon log 留存（spec §2、§6）。
        """
        if not (self.d.stopping and self.d.kill_on_stop):
            return
        for tid in aos7_task.live_tasks(self.node):
            ok, msg = aos7_task.kill_task(aos7_task.task_dir(self.node, tid))
            self.d.log(ev="kill", node=self.node_id, tid=tid, ok=ok, msg=msg)
