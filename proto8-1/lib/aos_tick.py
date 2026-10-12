#!/usr/bin/env python3
"""aos-tick：時鐘往前走一格。純標準庫。

    python3 aos_tick.py FILE

- FILE 裡是回合數（十進位＋換行，同 aos_inst 的 exit 檔）。讀出 n、寫回 n＋1 就結束，退出碼 0。
  FILE 不在＝0，所以第一次寫 1。寫進 n＋1 就代表第 n 回合結束、第 n＋1 回合開始（tock 不另外做）。
- 先寫同資料夾的 `.名字.tmp` 再用 os.replace 蓋過去，讀的人不會看到寫一半的。不 fsync。
- 出錯一律 stderr 印一行「代號: 白話」、退出碼 1，FILE 不動：
  BadContent＝內容不是 `\\d+` 加可有可無的一個換行（空檔也算）；ReadFailed／WriteFailed＝讀／寫不了；
  Usage＝參數不是剛好一個。

tick-tock 就是一個時鐘（CONCEPTS C-44）：不包任務、不保證什麼，大家要看就去讀 FILE。打包是規範，之後由 kernel 做。
節奏、停、只走 N 回合交給 loop：寫一份 loop.json，`inst` 那格的 argv 是 aos-tick，外層給 times／interval_ms
（要準時就 interval_mode "fixed"），停＝把它的 ctl.json 改成 {"paused": true}、繼續＝改回來。有沒有 daemon 都行。
同一個 FILE 同時有兩個人在 tick 不管（同一個 loop 本來就不會重疊）。
"""
import os
import re
import sys


class TickError(Exception):
    def __init__(self, code, msg):
        super().__init__("%s: %s" % (code, msg))
        self.code = code


def tick(path):
    """FILE 的回合數加一，回新的數。出錯丟 `TickError`（code＝BadContent／ReadFailed／WriteFailed），FILE 不動。"""
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except FileNotFoundError:
        raw = b"0\n"
    except OSError as e:
        raise TickError("ReadFailed", "讀不了 %s：%s" % (path, e.strerror or e))
    if not re.fullmatch(rb"\d+\n?", raw):          # bytes 的 \d 只認 0-9
        raise TickError("BadContent", "%s 的內容不是回合數：%r" % (path, raw[:40]))
    n = int(raw) + 1
    tmp = os.path.join(os.path.dirname(path), "." + os.path.basename(path) + ".tmp")
    try:
        with open(tmp, "w") as f:
            f.write("%d\n" % n)
        os.replace(tmp, path)
    except OSError as e:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise TickError("WriteFailed", "寫不了 %s：%s" % (path, e.strerror or e))
    return n


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("Usage: 參數要剛好一個：aos-tick FILE", file=sys.stderr)
        return 1
    try:
        tick(os.path.abspath(args[0]))
    except TickError as e:
        print(e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
