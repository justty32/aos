"""範例第一步：CSV → JSON。用法：convert.py <in.csv> <out.json> <request>。輸出帶 request，下一步據此核對版本。"""
import csv
import json
import os
import sys

src, dst, req = sys.argv[1:4]
with open(src, newline="", encoding="utf-8") as f:
    rows = [dict(r, amount=float(r["amount"])) for r in csv.DictReader(f)]
os.makedirs(os.path.dirname(dst), exist_ok=True)
tmp = dst + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump({"request": req, "rows": rows}, f, ensure_ascii=False)
os.replace(tmp, dst)          # 原子：下一步不會讀到半份
