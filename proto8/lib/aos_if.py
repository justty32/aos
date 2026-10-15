#!/usr/bin/env python3
"""aos if：先跑條件，結束碼 0 跑 THEN，否則跑 ELSE。純標準庫。

    python3 aos_if.py COND THEN [ELSE]      （PATH 上有 proto8/bin 就寫 `aos if …`）

- 每個用 `aos_inst.py` 跑，結果讀它 stdout 那份結果的 `code`。退出碼＝跑到的那支的碼（透明轉交）；條件不是 0 又沒寫 ELSE＝0（同 sh 的 if）。
- 條件或分支起不來（aos_inst 自己出錯）：它在 stderr 吐一份錯誤，退出碼 1，不再往下跑。
  條件「跑了、回非 0」才算不成立；條件起不來不會跑 ELSE。
- 要「反過來」就把兩個分支對調：`aos if X 失敗格 成功格`（aos-not 10-15 深夜刪）。
- 收到 SIGINT／SIGTERM／SIGHUP：轉給正在跑的（aos_inst 再轉給子程式，過它的 grace_ms 再 SIGKILL）、分支不跑，stderr 一份 `Signaled`、退出碼 1。
- 子程式留在自己的行程群組（不開 new session），外面整群收時一起收到。
"""
import sys

from aos_tasks import Signals, check_count, result, signaled, start


def main(argv=None):
    targets = sys.argv[1:] if argv is None else argv
    if not check_count(targets, "aos if COND THEN [ELSE]", 2, 3):
        return 1
    with Signals() as sig:
        code, ran = result(start(targets[0], sig), targets[0])
        if ran and not sig.got:         # 條件真的跑了才分支
            branch = targets[1] if code == 0 else targets[2] if len(targets) == 3 else None
            code = 0 if branch is None else result(start(branch, sig), branch)[0]
    return signaled(sig.got) if sig.got else code


if __name__ == "__main__":
    sys.exit(main())
