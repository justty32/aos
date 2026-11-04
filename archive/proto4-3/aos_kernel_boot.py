#!/usr/bin/env python3
"""aos-kernel-boot：把已初始化的 kernel 放上正在跑的 daemon。"""
import os
import sys

import aos_daemon_ctl
import aos_home
from aos_kernel import KHome


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    explicit_home = aos_daemon_ctl._pop_home(argv)
    if len(argv) != 1:
        sys.stderr.write("用法：aos-kernel-boot K [--home H]\n")
        return 2

    shown = argv[0]
    h = KHome(shown)
    cfg = h.config()
    if cfg is None or not os.path.isfile(h.instf):
        sys.stderr.write("aos-kernel-boot: %s 還沒灌作業系統，先跑："
                         "aos-kernel-init %s --ncpu N\n" % (shown, shown))
        return 1

    home = aos_home.Home(aos_home.resolve_home(explicit_home))
    if not home.alive():
        sys.stderr.write("aos-kernel-boot: daemon 沒在跑（硬體沒上電），先跑：aos-daemon &\n")
        return 1

    key = os.path.realpath(h.instf)
    ent = ((home.state() or {}).get("runs") or {}).get(key)
    if isinstance(ent, dict) and ent.get("state") in ("running", "paused"):
        print("kernel 已經在跑了（pid %s）" % ent.get("pid"))
        return 0

    args = ["--interval-ms", str(cfg["interval_ms"])]
    if cfg["timeout_ms"]:
        args += ["--timeout-ms", str(cfg["timeout_ms"])]
    code = aos_daemon_ctl.ask(home, {"op": "add", "target": h.instf, "args": args}, quiet=True)
    if code:
        return code
    print("開機了：kernel 上了 daemon（%s，每 %d ms 一回合）；看狀態：aos-kernel ls %s"
          % (h.instf, cfg["interval_ms"], h.dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
