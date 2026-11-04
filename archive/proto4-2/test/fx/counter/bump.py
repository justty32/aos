#!/usr/bin/env python3
# 每次執行把 count.txt 加一（沒有就當 0）。cwd 預設＝資料夾本身。
import os
n = 0
if os.path.exists("count.txt"):
    n = int(open("count.txt").read().strip() or 0)
open("count.txt", "w").write(str(n + 1))
print("count=%d tick=%s" % (n + 1, os.environ.get("AOS_TICK")))
