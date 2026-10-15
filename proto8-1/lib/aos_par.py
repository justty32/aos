#!/usr/bin/env python3
"""aos-par：全部 inst 一起跑，等全部結束。純標準庫。

    python3 aos_par.py TARGET...

- 先把全部 TARGET 讀好、驗過（同 aos_inst 的 load；不必寫 exit），有一個不對就在 stderr 吐一份 `{"error": {"code", "msg"}}`、退出碼 1，一個都不跑。
- 每個用 `aos_inst.py` 跑，一起起來；一個失敗不影響其他的，照樣等全部結束。
  然後照參數順序讀各自 stdout 那份結果的 `code`：全部是 0 退出碼 0；否則取第一個不是 0 的碼（透明轉交子程式的碼）。
- 某個 inst 起不來（aos_inst 自己出錯）：它自己在 stderr 吐一份錯誤，那一個算 1。
- 收到 SIGINT／SIGTERM／SIGHUP：轉給全部（aos_inst 再轉給子程式，過它的 grace_ms 再 SIGKILL），stderr 一份 `Signaled`、退出碼 1。
- 子程式留在自己的行程群組（不開 new session），外面整群收時一起收到。
"""
import sys

from aos_tasks import Signals, load_all, result, signaled, start


def main(argv=None):
    items = load_all(sys.argv[1:] if argv is None else argv, "aos_par.py TARGET...")
    if items is None:
        return 1
    with Signals() as sig:
        procs = [start(item, sig) for item in items]
        codes = [result(p, item)[0] for p, item in zip(procs, items)]
    if sig.got:
        return signaled(sig.got)
    for c in codes:
        if c:
            return c
    return 0


if __name__ == "__main__":
    sys.exit(main())
