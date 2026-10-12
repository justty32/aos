#!/usr/bin/env python3
"""aos-if：先跑條件，結束碼 0 跑 THEN，否則跑 ELSE。純標準庫。

    python3 aos_if.py COND THEN [ELSE]

- 先把全部 TARGET 讀好、驗過（同 aos_inst 的 load），有一個不對就印「代號: 白話」、退出碼 125，一個都不跑。
- 退出碼＝跑到的那支的結束碼；條件不是 0 又沒寫 ELSE＝0（同 sh 的 if）。
- 條件或分支起不來（aos_inst 自己出錯）：印「代號: 白話」、退出碼 127／126／125（同 aos_inst 命令列），不再往下跑。
  條件「跑了、回非 0」才算不成立；條件起不來不會跑 ELSE。
- 收到 SIGINT／SIGTERM／SIGHUP：收掉正在跑的（SIGTERM，過 2 秒再 SIGKILL）、分支不跑，退出碼＝128＋訊號號碼。
- 子程式留在自己的行程群組（不開 new_session），外面整群收時一起收到。
"""
import sys

from aos_tasks import InstError, Signals, exit_code, load_all
from aos_inst import run


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    insts = load_all(args, "aos_if.py COND THEN [ELSE]", 2, 3)
    if insts is None:
        return 125
    with Signals() as sig:
        try:
            code = run(insts[0], stop=sig.stop)
            branch = insts[1] if code == 0 else insts[2] if len(insts) == 3 else None
            code = 0
            if branch is not None and not sig.got:
                code = run(branch, stop=sig.stop)
        except InstError as e:
            print(e, file=sys.stderr)
            code = exit_code(e)
    return 128 + sig.got if sig.got else code


if __name__ == "__main__":
    sys.exit(main())
