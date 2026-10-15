#!/usr/bin/env python3
"""aos par：全部 inst 一起跑，等全部結束。純標準庫。

    python3 aos_par.py TARGET...      （PATH 上有 proto8/bin 就寫 `aos par …`）

- 每個用 `aos_inst.py` 跑，一起起來；一個失敗不影響其他的，照樣等全部結束。
  然後照參數順序讀各自 stdout 那份結果的 `code`：全部是 0 退出碼 0；否則取第一個不是 0 的碼（透明轉交子程式的碼）。
- 某個 inst 起不來（aos_inst 自己出錯）：它自己在 stderr 吐一份錯誤，那一個算 1。
- 收到 SIGINT／SIGTERM／SIGHUP：轉給全部（aos_inst 再轉給子程式，過它的 grace_ms 再 SIGKILL），stderr 一份 `Signaled`、退出碼 1。
- 子程式留在自己的行程群組（不開 new session），外面整群收時一起收到。
"""
import sys

from aos_tasks import Signals, check_count, result, signaled, start


def main(argv=None):
    targets = sys.argv[1:] if argv is None else argv
    if not check_count(targets, "aos par TARGET..."):
        return 1
    with Signals() as sig:
        procs = [start(t, sig) for t in targets]
        codes = [result(p, t)[0] for p, t in zip(procs, targets)]
    if sig.got:
        return signaled(sig.got)
    for c in codes:
        if c:
            return c
    return 0


if __name__ == "__main__":
    sys.exit(main())
