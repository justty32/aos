"""一條 tick-tock 時間線的迴圈：tick → 等任務或 interval → tock → 等滿 interval（spec.md 第 2 節，S-05、S-08、S-09）。

迴圈本身是 daemon 裡的一個 thread；tick、tock 每次都是獨立程序（S-04 的折衷，見 problems-core.md P-01）。
"""
import json
import math
import os
import subprocess
import sys
import threading
import time

import aos7_task
from aos7_fs import BIN, env_with_bin, node_path, now, read_json

POLL = 0.02
DEFAULT_INTERVAL_MS = 1000
ERROR_BACKOFF = 0.5    # 時間線迴圈丟例外後，等多久再接著跑


def run_prog(name, root, node_id, extra_env=None, gen=None):
    """跑 `bin/<name> <root> <node-id>`，回 (returncode, 最後一行 JSON 或 None, stderr)。"""
    env = env_with_bin()
    env.update(extra_env or {})
    if gen is not None:
        env["AOS7_GEN"] = str(gen)   # tick／tock 拿到 action.lock 後比對，舊 daemon 的動作不寫（astra-4 I-01）
    p = subprocess.run([sys.executable, os.path.join(BIN, name), root, node_id],
                       capture_output=True, text=True, env=env)
    out = None
    lines = p.stdout.strip().splitlines()
    if lines:
        try:
            out = json.loads(lines[-1])
        except ValueError:
            pass
    return p.returncode, out, p.stderr.strip()


class Timeline(threading.Thread):
    """一條時間線。daemon 物件要提供 root、is_paused(node_id)、stopping、kill_on_stop、log(**kw)。"""

    def __init__(self, daemon, node_id):
        super().__init__(name="tl:" + node_id, daemon=True)
        self.d = daemon
        self.node_id = node_id
        self.node = node_path(daemon.root, node_id)
        self.phase = "idle"
        self.round = read_json(os.path.join(self.node, ".aos", "round.json"), {}).get("round", 0)
        self.interval_ms = None      # 最近一回合實際用的 interval
        self.last_error = None       # 最近一次 tick／tock 失敗（rc≠0）
        self.gone = False            # node 消失：不再 tock（tock 會把資料夾建回來）
        self.wake = threading.Event()
        self.kick = False            # daemon ctl `wake`：不等滿 interval，馬上開下一回合（probes/event N1）

    def disk_round(self):
        """回合數以 round.json 為準（tick 寫了新回合卻沒印 stdout 時，記憶體裡的會落後）。"""
        r = read_json(os.path.join(self.node, ".aos", "round.json"), {})
        return r.get("round", self.round) if isinstance(r, dict) else self.round

    def note_error(self, prog, rc, err):
        """tick／tock 失敗時記下 last_error（status.json 會帶出來）；成功不清，留著給人看最後一次出錯。"""
        if rc:
            self.last_error = {"prog": prog, "rc": rc, "round": self.round, "at": now(),
                               "err": (err or "")[-300:]}

    def interval(self):
        """timeline.json 的 interval_ms；值不對用預設並記 last_error，時間線不死（probes/selfmod bug 3）。"""
        t = read_json(os.path.join(self.node, ".aos", "timeline.json"), {})
        ms = t.get("interval_ms", DEFAULT_INTERVAL_MS) if isinstance(t, dict) else DEFAULT_INTERVAL_MS
        if isinstance(ms, bool) or not isinstance(ms, (int, float)) or not math.isfinite(ms) or ms > 86400000 * 365:
            self.last_error = {"prog": "timeline", "rc": None, "round": self.round, "at": now(),
                               "err": "interval_ms 要是數字，拿到 %r；先用 %d" % (ms, DEFAULT_INTERVAL_MS)}
            ms = DEFAULT_INTERVAL_MS
        self.interval_ms = max(int(ms), 1)   # 這回合實際用的（status.json 帶出來；astra-4 I-08）
        return self.interval_ms / 1000.0

    def done(self):
        return self.d.stopping or self.gone

    def sleep_until(self, t_end):
        while not self.done() and not self.kick and time.monotonic() < t_end:
            self.wake.wait(min(POLL, max(0.0, t_end - time.monotonic())))

    def run(self):
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
        while not self.done():
            if self.d.is_paused(self.node_id):
                self.phase = "paused"
                self.wake.wait(POLL)
                continue
            t0 = time.monotonic()
            t_end = t0 + self.interval()
            self.kick = False
            self.phase = "tick"
            rc, out, err = run_prog("aos7-tick", self.d.root, self.node_id, gen=getattr(self.d, "gen", None))
            if (out or {}).get("stale"):
                self.d.log(ev="stale", node=self.node_id, prog="tick")   # 換了世代（不該發生在自己身上）：停這條線
                return
            if (out or {}).get("gone"):
                self.wake.wait(POLL)       # node 剛消失、daemon 還沒掃到：不開回合，等掃描收掉這條（probes/subtimeline 1）
                continue
            started = (out or {}).get("started", [])
            self.round = (out or {}).get("round") or self.disk_round()
            self.note_error("tick", rc, err)
            self.d.log(ev="tick", node=self.node_id, round=self.round, started=started, rc=rc,
                       **({"err": err[-500:]} if rc else {}))
            self.phase = "running"
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
            rc, out, err = run_prog("aos7-tock", self.d.root, self.node_id,
                                    {"AOS7_EARLY": "1" if early else "0"}, gen=getattr(self.d, "gen", None))
            self.note_error("tock", rc, err)
            self.d.log(ev="tock", node=self.node_id, round=self.round, rc=rc,
                       ended=(out or {}).get("ended"), early=early,
                       **({"err": err[-500:]} if rc else {}))
            self.d.round_done(self.node_id)   # resume 帶 rounds 的倒數（probes/sched N2）
            self.phase = "idle"
            self.sleep_until(t_end)
        if not self.gone:
            self.kill_if_stopping()

    def kill_if_stopping(self):
        """daemon stop 帶 kill：收掉本 node 所有活任務。"""
        if not (self.d.stopping and self.d.kill_on_stop):
            return
        for tid in aos7_task.live_tasks(self.node):
            ok, msg = aos7_task.kill_task(aos7_task.task_dir(self.node, tid))
            self.d.log(ev="kill", node=self.node_id, tid=tid, ok=ok, msg=msg)
