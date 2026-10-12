#!/usr/bin/env python3
"""aos-seq：照順序一個個跑 inst，像 `&&`。純標準庫。

    python3 aos_seq.py TARGET...

- 先把全部 TARGET 讀好、驗過（同 aos_inst 的 load，另外每個都要寫 exit），有一個不對就印「代號: 白話」、退出碼 125，一個都不跑。
- 每個用 `aos_inst.py` 跑，跑完讀它的 exit 檔：是 0 才跑下一個；遇到第一個不是 0 的就停，退出碼＝它的碼。全部是 0 退出碼 0。
- 跑到某個 inst 時 aos_inst 自己出錯（程式找不到、檔打不開…）：它印一行、seq 停、退出碼沿用 aos_inst 的（127／126／125）。
- 收到 SIGINT／SIGTERM／SIGHUP：轉給正在跑的（aos_inst 再轉給子程式，過它的 grace_ms 再 SIGKILL）、後面的不跑，退出碼＝128＋訊號號碼。
- 子程式留在自己的行程群組（不開 new session），外面整群收時一起收到。
"""
import sys

from aos_tasks import Signals, load_all, result, start


def main(argv=None):
    items = load_all(sys.argv[1:] if argv is None else argv, "aos_seq.py TARGET...")
    if items is None:
        return 125
    code = 0
    with Signals() as sig:
        for item in items:
            if sig.got:
                break
            code = result(start(item, sig), item)[0]
            if code:
                break
    return 128 + sig.got if sig.got else code


if __name__ == "__main__":
    sys.exit(main())
