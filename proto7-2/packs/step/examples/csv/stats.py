"""範例第二步：讀第一步已提交的 JSON，產生每個部門的筆數／總額／平均。

用法：stats.py <data.json> <期待的 request> <report.json>。data.json 的 request 不是期待的那一版＝退出碼 1（不拿錯版本算）。"""
import json
import os
import sys

src, want, dst = sys.argv[1:4]
with open(src, encoding="utf-8") as f:
    data = json.load(f)
if data.get("request") != want:
    print("data.json 是 %r 的版本，要的是 %r" % (data.get("request"), want), file=sys.stderr)
    sys.exit(1)
by = {}
for r in data["rows"]:
    d = by.setdefault(r["dept"], {"n": 0, "sum": 0.0})
    d["n"] += 1
    d["sum"] += r["amount"]
for d in by.values():
    d["avg"] = round(d["sum"] / d["n"], 2)
tmp = dst + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump({"from": want, "rows": len(data["rows"]), "by_dept": by}, f, ensure_ascii=False, sort_keys=True)
os.replace(tmp, dst)
