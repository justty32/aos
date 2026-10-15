#!/usr/bin/env python3
"""aos seq：照順序一個個跑 inst，像 `&&`。純標準庫。

    python3 aos_seq.py TARGET...      （PATH 上有 proto8/bin 就寫 `aos seq …`）

- 跑到哪讀到哪：每個用 `aos_inst.py` 跑，跑完讀它 stdout 那份結果的 `code`：是 0 才跑下一個；遇到第一個不是 0 的就停，退出碼＝它的碼（透明轉交子程式的碼）。全部是 0 退出碼 0。
- 跑到某個 inst 時 aos_inst 自己出錯（TARGET 壞了、程式找不到、檔打不開…）：它在 stderr 吐一份錯誤、seq 停、退出碼 1。
- 收到 SIGINT／SIGTERM／SIGHUP：轉給正在跑的（aos_inst 再轉給子程式，過它的 grace_ms 再 SIGKILL）、後面的不跑，stderr 一份 `Signaled`、退出碼 1。
- 子程式留在自己的行程群組（不開 new session），外面整群收時一起收到。
"""
import sys

from aos_tasks import Signals, check_count, result, signaled, start


def main(argv=None):
    targets = sys.argv[1:] if argv is None else argv
    if not check_count(targets, "aos seq TARGET..."):
        return 1
    code = 0
    with Signals() as sig:
        for t in targets:
            if sig.got:
                break
            code = result(start(t, sig), t)[0]
            if code:
                break
    return signaled(sig.got) if sig.got else code


if __name__ == "__main__":
    sys.exit(main())
