#!/usr/bin/env python3
"""表上的一筆（entry）＋兩條讀取執行緒＋狀態機——從 `aos_daemon.py` 拆出來的。

一筆 entry ＝ 一個 aos-run 子進程 ＋ 它的近況 ＋ 它現在處在哪個**狀態**。近況不是解
stderr 來的（那條照舊原樣進 daemon.log），而是讀 aos-run 的 `--status-fd`：

    ready                                 裝好訊號處理器了、還沒開跑  → ready=True
    start #3                              第 3 次開跑                 → running=True
    done #3 exit=0 kind=child 0.2s        第 3 次跑完                 → running=False、
                                          runs=3、last_exit=0、last_kind=child
    stop max_runs                         它要退了（last_line 留著）

五個狀態，daemon 主迴圈每圈叫一次 `advance()` 推：

    running        正常跑著
    pause_pending  收到 pause 了，等它睡著（ready 且 running=False）才送 SIGSTOP
    paused         已經 SIGSTOP 住了
    stopping       送過 SIGTERM 了，等它自己退（過了 deadline 還活著＝SIGKILL 整群）
    restarting     跟 stopping 一樣，只是收屍之後要用 new_args 同 key 再開一顆

**這裡的每個方法都不等人**：送個訊號、標個狀態、回一句要 log 的話就結束。
"""
import os
import signal
import time

RUNNING = "running"
PAUSE_PENDING = "pause_pending"
PAUSED = "paused"
STOPPING = "stopping"
RESTARTING = "restarting"

TERM_WAIT = 5.0         # SIGTERM 之後給它多久，還活著就 SIGKILL 整個 group
FORCE_GAP = 0.2         # force：兩發 SIGTERM 之間要隔一下，不然會被併成一次


def base_dir(target):
    """key＝目標**基準資料夾**的 realpath：資料夾→它自己；`.json`／普通檔案→它所在的
    資料夾。symlink、`..`、尾巴的 `/` 算同一個。不拿 inst.json 的 `cwd` 當 key（§13.1）。
    """
    p = os.path.abspath(target)
    if not os.path.isdir(p):
        p = os.path.dirname(p)
    return os.path.realpath(p)


class Entry:
    """表上的一筆：一個 aos-run 子進程 ＋ 從它 status-fd 讀來的近況 ＋ 狀態。"""

    def __init__(self, key, proc, target, args, status_fd):
        self.key = key
        self.proc = proc
        self.target = target
        self.args = list(args)
        self.started_at = time.time()
        self.state = RUNNING
        self.ready = False              # 收到 `ready` 了＝訊號處理器裝好了
        self.running = False            # start→True、done→False（False＝在睡覺）
        self.runs = 0                   # 最後一個 done 的 `#n`
        self.last_exit = None           # 最後一個 `exit=`
        self.last_kind = None           # 最後一個 `kind=`（child／aos／usage）
        self.last_line = None           # 最後一行 status 原文
        self.status_fd = status_fd      # 管子的讀端，讀完那條執行緒自己關
        self.thread = None              # 讀 stderr → daemon.log
        self.sthread = None             # 讀 status → 上面那些欄位
        self.stop_deadline = None       # stopping／restarting：過了還活著就 SIGKILL
        self.force_at = None            # rm --force：到了再補一發 SIGTERM
        self.new_args = None            # restarting：收屍之後用這組旗標重開

    def entry(self):
        return {"pid": self.proc.pid, "target": self.target, "args": self.args,
                "started_at": self.started_at, "state": self.state,
                "ready": self.ready, "running": self.running, "runs": self.runs,
                "last_exit": self.last_exit, "last_kind": self.last_kind,
                "last_line": self.last_line, "alive": self.alive()}

    def feed(self, line):
        """一行 status 事件 → 更新欄位。看不懂的行只留 last_line，不炸。"""
        self.last_line = line
        w = line.split()
        if not w:
            return
        if w[0] == "ready":
            self.ready = True
        elif w[0] == "start":
            self.running = True
        elif w[0] == "done":
            self.running = False
            for tok in w[1:]:
                try:
                    if tok.startswith("#"):
                        self.runs = int(tok[1:])
                    elif tok.startswith("exit="):
                        self.last_exit = int(tok[len("exit="):])
                    elif tok.startswith("kind="):
                        self.last_kind = tok[len("kind="):]
                except ValueError:
                    pass

    # ── 狀態機 ───────────────────────────────────────
    def begin_stop(self, state, force=False):
        """送 SIGTERM、標狀態、記兩個時間點就回（`stopping` 或 `restarting`）。

        暫停中的先 SIGCONT，不然它收不到。`force`＝0.2 秒後再補一發（腰斬正在跑的那次）。
        """
        if self.state == PAUSED:
            self.sig(signal.SIGCONT)
        self.sig(signal.SIGTERM)
        now = time.monotonic()
        self.state = state
        self.stop_deadline = now + TERM_WAIT
        self.force_at = (now + FORCE_GAP) if force else None
        return "%s %s pid=%d force=%s" % (state, self.key, self.proc.pid, bool(force))

    def advance(self, now):
        """推一格，回一句要 log 的話（這一格沒動就 None）。不等、不睡。"""
        if not self.alive():
            return None                                 # 已經死了，交給 reap
        if self.state == PAUSE_PENDING:
            if self.ready and not self.running:         # 在睡覺才停，不腰斬正在跑的
                self.sig(signal.SIGSTOP)
                self.state = PAUSED
                return "paused %s pid=%d runs=%d" % (self.key, self.proc.pid, self.runs)
        elif self.state in (STOPPING, RESTARTING):
            if self.force_at is not None and now >= self.force_at:
                self.force_at = None
                self.sig(signal.SIGTERM)                # 第二發＝腰斬正在跑的那次
            if self.stop_deadline is not None and now >= self.stop_deadline:
                self.stop_deadline = None
                self.killpg()
                return "等不到了，SIGKILL 整個 group：%s pid=%d" % (self.key, self.proc.pid)
        return None

    # ── 小工具 ───────────────────────────────────────
    def alive(self):
        return self.proc.poll() is None

    def code(self):
        """收屍時的退出碼：被訊號 N 砍＝128+N。"""
        c = self.proc.returncode
        return c if c is None or c >= 0 else 128 - c

    def sig(self, s):
        try:
            os.kill(self.proc.pid, s)
        except OSError:                     # 已經死了＝ESRCH，無害
            pass

    def killpg(self):
        try:
            os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
        except OSError:
            pass

    def join(self):
        for t in (self.thread, self.sthread):
            if t is not None:
                t.join(1.0)


def read_status(r):
    """一條執行緒逐行讀 aos-run 的 status 管子，餵給 entry。EOF（它退了）就收工。"""
    try:
        with os.fdopen(r.status_fd, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                r.feed(line.rstrip("\n"))
    except OSError:
        pass


def read_stderr(r, say):
    """另一條執行緒逐行讀 aos-run 的 stderr：原樣（前面加 key）進 daemon.log。

    近況不從這裡解——那是 status 那條的事，這裡純粹是給人看的流水帳。
    """
    for raw in r.proc.stderr:                           # 一行一行來，不等它退
        say("%s %s" % (r.key, raw.decode("utf-8", "replace").rstrip("\n")))
    try:
        r.proc.stderr.close()
    except OSError:
        pass
