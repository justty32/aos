#!/usr/bin/env python3
"""aos-not：跑一個 inst，把結果反過來。純標準庫。

    python3 aos_not.py TARGET

- 用 `aos_inst.py` 跑，讀它 stdout 那份結果的 `code`：0 → 退出碼 1；不是 0 → 退出碼 0。
- TARGET 不對、起不來（aos_inst 自己出錯）＝stderr 一份錯誤、退出碼 1，不反過來（跟「答案是假」的 1 靠 stderr 分：假不寫 stderr）。
- 收到 SIGINT／SIGTERM／SIGHUP：轉給它（aos_inst 再轉給子程式，過它的 grace_ms 再 SIGKILL），stderr 一份 `Signaled`、退出碼 1。
- 子程式留在自己的行程群組（不開 new session），外面整群收時一起收到。
"""
import sys

from aos_tasks import Signals, load_all, result, signaled, start


def main(argv=None):
    items = load_all(sys.argv[1:] if argv is None else argv, "aos_not.py TARGET", 1, 1)
    if items is None:
        return 1
    with Signals() as sig:
        code, ran = result(start(items[0], sig), items[0])
        if ran:
            code = 0 if code else 1
    return signaled(sig.got) if sig.got else code


if __name__ == "__main__":
    sys.exit(main())
