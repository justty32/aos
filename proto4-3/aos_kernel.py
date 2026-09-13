#!/usr/bin/env python3
"""aos-kernel：作業系統的第一個程序——管一張「哪顆 cpu 上是哪個行程」的表。

    aos-kernel ls [DIR]                         # 印給人看
    aos-kernel add [DIR] INST.json [--name NAME] # 排一個行程進佇列
    aos-kernel rm [DIR] NAME                     # 請 kernel 拿掉一個行程

`init`（重灌，很久一次）與 `tick`（心跳，每回合）都拆成自己的獨立指令了：
`aos-kernel-init`（見 `aos_kernel_init.py`）與 `aos-kernel-tick`（見
`aos_kernel_tick.py`）。`aos-kernel` 這支是給人用的：`ls`／`add`／`rm` 與 module 的子命令，不是心跳的一部分
（[proto4 筆記 §19.4／§19.7](../proto4/notes/2026-09-08-ideas.md)）。

[proto4 筆記第 18 節](../proto4/notes/2026-09-08-ideas.md)的原型。**硬體是 daemon**
（`ctl add foo.json` ＝插一顆 cpu），**kernel 是唯一碰 ctl、唯一改 cpu 那份 inst.json 的人**
（§16）。kernel 自己也是一個 proc：它的家裡有一份 `inst.json`，使用者手動
`aos-daemon-ctl add K/inst.json` ＝上電，之後 kernel 每回合自己跑一次 `aos-kernel-tick`。

家（DIR）長這樣：

    DIR/inst.json       kernel 自己那顆 cpu 的指令，只有 kernel 能動
    DIR/config.json     上述整數設定，另有 "modules":["/abs/xxx_module.py"]
    DIR/procs/<pid>.json  就緒佇列，檔名去掉 .json ＝ pid
    DIR/procs/bad/      退件（格式／欄位不合、連續回 125，或一般失敗達 bad_after 次）
    DIR/procs/done/     回保留退出碼做完的行程；rm 拿掉的不會進來
    DIR/cpus/<n>.json   每顆 cpu 一份 inst.json，這個路徑就是 daemon 表上的 key
    DIR/syscalls/       給 kernel 的單子
    DIR/syscalls/done/  單子的回音
    DIR/state.json      kernel 自己的表：cpu n → pid、runs、waiting 與佇列
    DIR/kernel.log      每回合一行流水帳

一回合七步（順序固定），做完一律退出 0——**kernel 不會因為外面的事死掉**，
daemon 沒在跑、ctl 或 module 失敗都只是記一行 log。七步見 `aos_kernel_tick.tick()`。
"""
import json
import os
import sys
import time

import aos_home

HERE = os.path.dirname(os.path.abspath(__file__))
CTL_BIN = os.path.join(HERE, "aos-daemon-ctl")
IDLE_INST = {"argv": ["true"], "cwd": "."}
DEFAULTS = {"interval_ms": 1000, "timeout_ms": 0, "quantum": 5, "done_exit": 100,
            "wait_exit": 101, "bad_after": 10}
USAGE = ("用法：aos-kernel ls [DIR]\n"
         "      aos-kernel add [DIR] INST.json [--name NAME]\n"
         "      aos-kernel rm [DIR] NAME\n"
         "      aos-kernel <MODULE> [DIR] ...\n")
INIT_HINT = ("aos-kernel: init 改成獨立指令 aos-kernel-init（不再是 aos-kernel 的子命令）："
             "aos-kernel-init DIR --ncpu N [--interval-ms X] [--timeout-ms Y] [--quantum Q] "
             "[--done-exit N] [--wait-exit N] [--bad-after N] [--module PATH]...\n")
TICK_HINT = "aos-kernel: tick 改成獨立指令 aos-kernel-tick（不再是 aos-kernel 的子命令）\n"


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
        self.done = os.path.join(self.procs, "done")
        self.cpus = os.path.join(self.dir, "cpus")
        self.syscalls = os.path.join(self.dir, "syscalls")
        self.syscalls_done = os.path.join(self.syscalls, "done")
        self.statef = os.path.join(self.dir, "state.json")
        self.logf = os.path.join(self.dir, "kernel.log")

    def cpu(self, n):
        return os.path.join(self.cpus, "%d.json" % n)

    def proc(self, pid):
        return os.path.join(self.procs, "%s.json" % pid)

    def proc_done(self, pid):
        return os.path.join(self.done, "%s.json" % pid)

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
        modules = cfg.get("modules", [])
        out["modules"] = (modules if isinstance(modules, list)
                          and all(isinstance(item, str) for item in modules) else [])
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
        waiting = st.get("waiting")
        return {"cpus": cpus if isinstance(cpus, dict) else {},
                "queue": [q for q in queue if isinstance(q, str)]
                         if isinstance(queue, list) else [],
                "waiting": ({pid: runs for pid, runs in waiting.items()
                             if isinstance(pid, str) and isinstance(runs, int) and runs > 0}
                            if isinstance(waiting, dict) else {})}

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


def here_or_die(prog):
    """cwd 就是家；沒有 config.json ＝不是家。`prog` 是報錯時要冒充的指令名。"""
    h = KHome(os.getcwd())
    cfg = h.config()
    if cfg is None:
        sys.stderr.write("aos-kernel: %s 不是 kernel 的家（還沒灌？先跑："
                         "aos-kernel-init %s --ncpu N）\n" % (h.dir, h.dir))
        return None, None
    return h, cfg


def cmd_ls(argv):
    if len(argv) > 1:
        sys.stderr.write(USAGE)
        return 2
    if argv:
        try:
            os.chdir(argv[0])
        except OSError:
            sys.stderr.write("aos-kernel: %s 不是 kernel 的家（還沒灌？先跑："
                             "aos-kernel-init %s --ncpu N）\n" % (argv[0], argv[0]))
            return 1
    h, cfg = here_or_die("aos-kernel")
    if h is None:
        return 1
    st = h.state()
    from aos_kernel_status import show
    show(h, cfg, st, pid_key)
    return 0


def cmd_module(name, argv):
    """`aos-kernel NAME [K] ...`；module 子命令也可把 K 放在動作之後。"""
    kernel_dir = os.getcwd()
    rest = list(argv)
    candidates = range(min(2, len(rest)))
    found = next((i for i in candidates if os.path.isdir(rest[i])
                  and os.path.isfile(os.path.join(rest[i], "config.json"))), None)
    if found is not None:
        kernel_dir = rest.pop(found)
    h = KHome(kernel_dir)
    cfg = h.config()
    if cfg is None:
        sys.stderr.write("aos-kernel: %s 不是 kernel 的家（還沒灌？先跑："
                         "aos-kernel-init %s --ncpu N）\n" % (h.dir, h.dir))
        return 1
    from aos_kernel_module import load_modules
    for module in load_modules(cfg):
        if module.NAME == name and getattr(module, "cli", None) is not None:
            try:
                return module.cli(h, cfg, rest)
            except BaseException as exc:
                sys.stderr.write("aos-kernel: module %s 壞了：%s\n"
                                 % (name, str(exc).replace("\n", " ")))
                return 1
    return None


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
        sys.stderr.write(INIT_HINT)
        return 2
    if cmd == "tick":
        sys.stderr.write(TICK_HINT)
        return 2
    if cmd == "ls":
        return cmd_ls(rest)
    if cmd == "add":
        from aos_kernel_add import cmd_add
        return cmd_add(rest)
    if cmd == "rm":
        from aos_kernel_syscall import cmd_rm
        return cmd_rm(rest)
    code = cmd_module(cmd, rest)
    if code is not None:
        return code
    sys.stderr.write("aos-kernel: 不認得的子命令：%s\n%s" % (cmd, USAGE))
    return 2


if __name__ == "__main__":
    sys.exit(main())
