#!/usr/bin/env python3
"""aos-kernel-init：重灌 kernel 的家——很久一次的事，跟每回合跑的心跳（`aos-kernel-tick`）
及給人看的 `aos-kernel ls` 不同壽命（[proto4 筆記 §19.4／§19.7]
(../proto4/notes/2026-09-08-ideas.md)），所以拆成自己的命令。

    aos-kernel-init DIR --ncpu N [--interval-ms X] [--timeout-ms Y] [--quantum Q]

建出來的家（DIR）長什麼樣、`inst.json`／`config.json`／`state.json`／`kernel.log`／
`procs/`／`cpus/` 各是什麼，見 `aos_kernel.py` 的 docstring 與 `KHome`（家的版面共用
那一份，不重複定義）。
"""
import argparse
import os
import sys

import aos_home
from aos_kernel import DEFAULTS, KHome

HERE = os.path.dirname(os.path.abspath(__file__))
TICK_BIN = os.path.join(HERE, "aos-kernel-tick")


def cmd_init(argv):
    ap = argparse.ArgumentParser(prog="aos-kernel-init", add_help=True)
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
        sys.stderr.write("aos-kernel-init: --ncpu／--quantum 至少 1，時間不能是負數\n")
        return 2
    h = KHome(a.dir)
    if os.path.exists(h.dir):
        sys.stderr.write("aos-kernel-init: 已經有這個資料夾了，不動它：%s\n" % h.dir)
        return 1
    for p in (h.dir, h.procs, h.bad, h.cpus):
        os.makedirs(p)
    # argv[0] 寫絕對路徑：daemon→aos-run→aos-exec 繼承下來的 PATH 未必找得到 aos-kernel-tick
    aos_home.write_json(h.instf, {"argv": [TICK_BIN], "cwd": "."})
    aos_home.write_json(h.configf, {"ncpu": a.ncpu, "interval_ms": a.interval_ms,
                                    "timeout_ms": a.timeout_ms, "quantum": a.quantum})
    aos_home.write_json(h.statef, {"cpus": {str(n): None for n in range(a.ncpu)},
                                   "queue": []})
    h.log("init ncpu=%d interval=%dms timeout=%dms quantum=%d"
          % (a.ncpu, a.interval_ms, a.timeout_ms, a.quantum))
    print("家建好了：%s（ncpu=%d）" % (h.dir, a.ncpu))
    print("開機：aos-daemon & ； aos-daemon-ctl add %s" % h.instf)
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    return cmd_init(argv)


if __name__ == "__main__":
    sys.exit(main())
