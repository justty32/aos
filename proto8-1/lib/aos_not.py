#!/usr/bin/env python3
"""aos-not：跑一個 inst，把結果反過來。純標準庫。

    python3 aos_not.py TARGET

- 結束碼 0 → 退出碼 1；不是 0 → 退出碼 0。
- TARGET 不對、或起不來（aos_inst 自己出錯）：印「代號: 白話」、退出碼 1（這不反過來）。
- 收到 SIGINT／SIGTERM／SIGHUP：收掉它（SIGTERM，過 2 秒再 SIGKILL），退出碼＝128＋訊號號碼（不反過來）。
- 子程式留在自己的行程群組（不開 new_session），外面整群收時一起收到。
"""
import sys

from aos_tasks import InstError, Signals, load_all
from aos_inst import run


def main(argv=None):
    insts = load_all(sys.argv[1:] if argv is None else argv, "aos_not.py TARGET", 1, 1)
    if insts is None:
        return 1
    with Signals() as sig:
        try:
            code = 0 if run(insts[0], stop=sig.stop) else 1
        except InstError as e:
            print(e, file=sys.stderr)
            code = 1
    return 128 + sig.got if sig.got else code


if __name__ == "__main__":
    sys.exit(main())
