#!/usr/bin/env python3
"""aos-kernel：作業系統的第一個程序——管一張「哪顆 cpu 上是哪個行程」的表。

    aos-kernel init DIR --ncpu N [--interval-ms X] [--timeout-ms Y] [--quantum Q]
    aos-kernel tick                 # 在家裡跑一回合（cwd 就是家）
    aos-kernel ls                   # 印給人看：每顆 cpu 上是誰、佇列裡誰在等

[proto4 筆記第 18 節](../proto4/notes/2026-09-08-ideas.md)的原型。**硬體是 daemon**
（`ctl add foo.json` ＝插一顆 cpu），**kernel 是唯一碰 ctl、唯一改 cpu 那份 inst.json 的人**
（§16）。kernel 自己也是一個 proc：它的家裡有一份 `inst.json`，使用者手動
`aos-daemon-ctl add K/inst.json` ＝上電，之後 kernel 每回合自己跑一次 `tick`。

家（DIR）長這樣：

    DIR/inst.json       kernel 自己那顆 cpu 的指令，只有 kernel 能動
    DIR/config.json     {"ncpu":N,"interval_ms":X,"timeout_ms":Y,"quantum":Q}
    DIR/procs/<pid>.json  就緒佇列，檔名去掉 .json ＝ pid
    DIR/procs/bad/      退件（不是 JSON 物件／沒有 argv／沒寫 cwd）
    DIR/cpus/<n>.json   每顆 cpu 一份 inst.json，這個路徑就是 daemon 表上的 key
    DIR/state.json      kernel 自己的表：cpu n → pid、上去的時間、上去時的 runs、佇列
    DIR/kernel.log      每回合一行流水帳

`tick` 一回合五步（順序固定），做完一律退出 0——**kernel 不會因為外面的事死掉**，
daemon 沒在跑、ctl 失敗都只是記一行 log。五步見 `aos_kernel_tick.tick()`。
"""
import argparse
import json
import os
import sys
import time

import aos_home

HERE = os.path.dirname(os.path.abspath(__file__))
CTL_BIN = os.path.join(HERE, "aos-daemon-ctl")
KERNEL_BIN = os.path.join(HERE, "aos-kernel")
IDLE_INST = {"argv": ["true"], "cwd": "."}
DEFAULTS = {"interval_ms": 1000, "timeout_ms": 0, "quantum": 5}
USAGE = ("用法：aos-kernel init DIR --ncpu N [--interval-ms X] [--timeout-ms Y] "
         "[--quantum Q]\n      aos-kernel tick\n      aos-kernel ls\n")


def pid_key(pid):
    """檔名排序：數字比數字、非數字按字串排在數字後面。"""
    return (0, int(pid), "") if pid.isdigit() else (1, 0, pid)


class KHome:
    """家的版面（哪個檔在哪）＋讀寫 config／state／log。"""

    def __init__(self, d):
        self.dir = os.path.abspath(d)
        self.instf = os.path.join(self.dir, "inst.json")
        self.configf = os.path.join(self.dir, "config.json")
        self.procs = os.path.join(self.dir, "procs")
        self.bad = os.path.join(self.procs, "bad")
        self.cpus = os.path.join(self.dir, "cpus")
        self.statef = os.path.join(self.dir, "state.json")
        self.logf = os.path.join(self.dir, "kernel.log")

    def cpu(self, n):
        return os.path.join(self.cpus, "%d.json" % n)

    def proc(self, pid):
        return os.path.join(self.procs, "%s.json" % pid)

    def config(self):
        """讀 config.json；讀不到＝這裡不是家，回 None。"""
        try:
            with open(self.configf, encoding="utf-8") as f:
                cfg = json.load(f)
        except (OSError, ValueError):
            return None
        if not isinstance(cfg, dict) or not isinstance(cfg.get("ncpu"), int):
            return None
        out = dict(DEFAULTS)
        out.update({k: v for k, v in cfg.items() if isinstance(v, int)})
        return out

    def state(self):
        """讀 state.json；沒有＝空表。"""
        st = None
        try:
            with open(self.statef, encoding="utf-8") as f:
                st = json.load(f)
        except (OSError, ValueError):
            st = None
        if not isinstance(st, dict):
            st = {}
        cpus = st.get("cpus")
        queue = st.get("queue")
        return {"cpus": cpus if isinstance(cpus, dict) else {},
                "queue": [q for q in queue if isinstance(q, str)]
                         if isinstance(queue, list) else []}

    def save(self, st):
        aos_home.write_json(self.statef, st)      # 先 .tmp 再 rename

    def log(self, line):
        with open(self.logf, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), line))

    def pids(self):
        """佇列裡有哪些 pid（procs/*.json，不含 bad/），照 pid 順序。"""
        try:
            names = os.listdir(self.procs)
        except OSError:
            return []
        out = [n[:-5] for n in names
               if n.endswith(".json") and os.path.isfile(os.path.join(self.procs, n))]
        return sorted(out, key=pid_key)


def cmd_init(argv):
    ap = argparse.ArgumentParser(prog="aos-kernel init", add_help=True)
    ap.add_argument("dir")
    ap.add_argument("--ncpu", type=int, required=True)
    ap.add_argument("--interval-ms", type=int, default=DEFAULTS["interval_ms"])
    ap.add_argument("--timeout-ms", type=int, default=DEFAULTS["timeout_ms"])
    ap.add_argument("--quantum", type=int, default=DEFAULTS["quantum"])
    try:
        a = ap.parse_args(argv)
    except SystemExit:
        return 2
    if a.ncpu < 1 or a.interval_ms < 0 or a.timeout_ms < 0 or a.quantum < 1:
        sys.stderr.write("aos-kernel: --ncpu／--quantum 至少 1，時間不能是負數\n")
        return 2
    h = KHome(a.dir)
    if os.path.exists(h.dir):
        sys.stderr.write("aos-kernel: 已經有這個資料夾了，不動它：%s\n" % h.dir)
        return 1
    for p in (h.dir, h.procs, h.bad, h.cpus):
        os.makedirs(p)
    # argv[0] 寫絕對路徑：daemon→aos-run→aos-exec 繼承下來的 PATH 未必找得到 aos-kernel
    aos_home.write_json(h.instf, {"argv": [KERNEL_BIN, "tick"], "cwd": "."})
    aos_home.write_json(h.configf, {"ncpu": a.ncpu, "interval_ms": a.interval_ms,
                                    "timeout_ms": a.timeout_ms, "quantum": a.quantum})
    aos_home.write_json(h.statef, {"cpus": {str(n): None for n in range(a.ncpu)},
                                   "queue": []})
    h.log("init ncpu=%d interval=%dms timeout=%dms quantum=%d"
          % (a.ncpu, a.interval_ms, a.timeout_ms, a.quantum))
    print("家建好了：%s（ncpu=%d）" % (h.dir, a.ncpu))
    print("開機：aos-daemon & ； aos-daemon-ctl add %s" % h.instf)
    return 0


def _here_or_die():
    """cwd 就是家；沒有 config.json ＝不是家。"""
    h = KHome(os.getcwd())
    cfg = h.config()
    if cfg is None:
        sys.stderr.write("aos-kernel: 這裡不是 kernel 的家（沒有 config.json）：%s\n" % h.dir)
        return None, None
    return h, cfg


def cmd_tick(argv):
    if argv:
        sys.stderr.write("aos-kernel: tick 不吃參數（cwd 就是家）\n")
        return 2
    h, cfg = _here_or_die()
    if h is None:
        return 1
    import aos_kernel_tick
    return aos_kernel_tick.tick(h, cfg)


def cmd_ls(argv):
    if argv:
        sys.stderr.write("aos-kernel: ls 不吃參數（cwd 就是家）\n")
        return 2
    h, cfg = _here_or_die()
    if h is None:
        return 1
    st = h.state()
    runs = (aos_home.Home(aos_home.resolve_home()).state() or {}).get("runs", {})
    now = time.time()
    print("家 %s  ncpu=%d interval=%dms timeout=%dms quantum=%d"
          % (h.dir, cfg["ncpu"], cfg["interval_ms"], cfg["timeout_ms"], cfg["quantum"]))
    print("CPU  PID   ON        RUNS  CPU_STATE")
    for n in range(cfg["ncpu"]):
        cur = st["cpus"].get(str(n))
        ent = runs.get(os.path.realpath(h.cpu(n)))
        state = ent.get("state", "?") if ent else "沒插上"
        if cur:
            got = ent.get("runs", 0) - cur.get("runs_at", 0) if ent else "-"
            print("%-4d %-5s %-9s %-5s %s"
                  % (n, cur.get("pid"), "%.1fs" % (now - cur.get("since", now)),
                     got, state))
        else:
            print("%-4d %-5s %-9s %-5s %s" % (n, "idle", "-", "-", state))
    q = st["queue"]
    print("佇列（%d 個）：%s" % (len(q), " ".join(q) if q else "沒人在等"))
    bad = sorted(os.listdir(h.bad)) if os.path.isdir(h.bad) else []
    if bad:
        print("退件（%d 個）：%s" % (len(bad), " ".join(bad)))
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        sys.stderr.write(USAGE)
        return 2
    cmd, rest = argv[0], argv[1:]
    if cmd in ("-h", "--help", "help"):
        sys.stdout.write(USAGE)
        return 0
    if cmd == "init":
        return cmd_init(rest)
    if cmd == "tick":
        return cmd_tick(rest)
    if cmd == "ls":
        return cmd_ls(rest)
    sys.stderr.write("aos-kernel: 不認得的子命令：%s\n%s" % (cmd, USAGE))
    return 2


if __name__ == "__main__":
    sys.exit(main())
