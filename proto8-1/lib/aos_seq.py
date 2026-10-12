#!/usr/bin/env python3
"""aos-seq：照順序一個個跑 inst，像 `&&`。純標準庫。

    python3 aos_seq.py TARGET...

- 先把全部 TARGET 讀好、驗過（同 aos_inst 的 load），有一個不對就印「代號: 白話」、退出碼 1，一個都不跑。
- 前一個結束碼是 0 才跑下一個；遇到第一個不是 0 的就停，退出碼＝它的結束碼。全部是 0 退出碼 0。
- 跑到某個 inst 時 aos_inst 自己出錯（程式找不到、檔打不開…）：印「代號: 白話」、停、退出碼 1。
- 收到 SIGINT／SIGTERM／SIGHUP：收掉正在跑的（SIGTERM，過 2 秒再 SIGKILL）、後面的不跑，退出碼＝128＋訊號號碼。
- 子程式留在自己的行程群組（不開 new_session），外面整群收時一起收到。
"""
import sys

from aos_tasks import InstError, Signals, load_all
from aos_inst import run


def main(argv=None):
    insts = load_all(sys.argv[1:] if argv is None else argv, "aos_seq.py TARGET...")
    if insts is None:
        return 1
    code = 0
    with Signals() as sig:
        for inst in insts:
            if sig.got:
                break
            try:
                code = run(inst, stop=sig.stop)
            except InstError as e:
                print(e, file=sys.stderr)
                code = 1
            if code:
                break
    return 128 + sig.got if sig.got else code


if __name__ == "__main__":
    sys.exit(main())
