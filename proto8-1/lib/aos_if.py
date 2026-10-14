#!/usr/bin/env python3
"""aos-if：先跑條件，結束碼 0 跑 THEN，否則跑 ELSE。純標準庫。

    python3 aos_if.py COND THEN [ELSE]

- 先把全部 TARGET 讀好、驗過（同 aos_inst 的 load，另外每個都要寫 exit），有一個不對就在 stderr 吐一份 `{"error": {"code", "msg"}}`、退出碼 125，一個都不跑。
- 每個用 `aos_inst.py` 跑，結果讀它的 exit 檔。退出碼＝跑到的那支的碼；條件不是 0 又沒寫 ELSE＝0（同 sh 的 if）。
- 條件或分支起不來（aos_inst 自己出錯）：它在 stderr 吐一份錯誤，退出碼沿用 aos_inst 的（127／126／125），不再往下跑。
  條件「跑了、回非 0」才算不成立；條件起不來不會跑 ELSE。
- 收到 SIGINT／SIGTERM／SIGHUP：轉給正在跑的（aos_inst 再轉給子程式，過它的 grace_ms 再 SIGKILL）、分支不跑，退出碼＝128＋訊號號碼。
- 子程式留在自己的行程群組（不開 new session），外面整群收時一起收到。
"""
import sys

from aos_tasks import Signals, load_all, result, start


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    items = load_all(args, "aos_if.py COND THEN [ELSE]", 2, 3)
    if items is None:
        return 125
    with Signals() as sig:
        code, ran = result(start(items[0], sig), items[0])
        if ran and not sig.got:         # 條件真的跑了才分支
            branch = items[1] if code == 0 else items[2] if len(items) == 3 else None
            code = 0 if branch is None else result(start(branch, sig), branch)[0]
    return 128 + sig.got if sig.got else code


if __name__ == "__main__":
    sys.exit(main())
