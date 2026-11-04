"""selfprog 的工作任務：python3 count.py <輸入檔> <輸出檔>，算字數寫 {"file", "words"}（稍微睡一下，像在做事）。"""
import json
import os
import sys
import time

src, dst = sys.argv[1], sys.argv[2]
with open(src, encoding="utf-8") as f:
    n = len(f.read().split())
time.sleep(0.5)
os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
tmp = os.path.join(os.path.dirname(dst) or ".", "." + os.path.basename(dst) + ".tmp")
with open(tmp, "w", encoding="utf-8") as f:
    json.dump({"file": os.path.basename(src), "words": n}, f)
os.replace(tmp, dst)
