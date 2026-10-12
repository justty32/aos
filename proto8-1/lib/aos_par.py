#!/usr/bin/env python3
"""aos-par：全部 inst 一起跑，等全部結束。純標準庫。

    python3 aos_par.py TARGET...

- 先把全部 TARGET 讀好、驗過（同 aos_inst 的 load），有一個不對就印「代號: 白話」、退出碼 1，一個都不跑。
- 一個失敗不影響其他的，照樣等全部結束。全部是 0 退出碼 0；否則照參數順序取第一個不是 0 的結束碼。
- 某個 inst 起不來（aos_inst 自己出錯）：照參數順序印「代號: 白話」，那一個算 1。
- 收到 SIGINT／SIGTERM／SIGHUP：全部收掉（SIGTERM，過 2 秒再 SIGKILL），退出碼＝128＋訊號號碼。
- 子程式留在自己的行程群組（不開 new_session），外面整群收時一起收到。
"""
import sys
import threading

from aos_tasks import InstError, Signals, load_all
from aos_inst import run


def main(argv=None):
    insts = load_all(sys.argv[1:] if argv is None else argv, "aos_par.py TARGET...")
    if insts is None:
        return 1
    codes = [None] * len(insts)
    with Signals() as sig:
        def one(i):
            try:
                codes[i] = run(insts[i], stop=sig.stop)
            except InstError as e:
                codes[i] = e
        threads = [threading.Thread(target=one, args=(i,)) for i in range(len(insts))]
        for t in threads:
            t.start()
        for t in threads:
            while t.is_alive():
                t.join(0.05)    # 不用無限 join，主執行緒才接得到訊號
    for c in codes:
        if isinstance(c, InstError):
            print(c, file=sys.stderr)
    if sig.got:
        return 128 + sig.got
    for c in codes:
        c = 1 if isinstance(c, InstError) else c
        if c:
            return c
    return 0


if __name__ == "__main__":
    sys.exit(main())
