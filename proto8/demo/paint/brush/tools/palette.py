"""工具 palette（調色盤）：stdin＝引數 {"subject"}，stdout 吐 {"subject", "colors"}。寫死的對照表，找不到就給灰、黑。"""
import json
import sys

TABLE = {"貓": ["橘", "白", "黑"], "狗": ["棕", "白"], "海": ["藍", "白"], "樹": ["綠", "棕"], "太陽": ["黃", "紅"]}
subject = str(json.load(sys.stdin).get("subject", ""))
colors = next((v for k, v in TABLE.items() if k in subject), ["灰", "黑"])
print(json.dumps({"subject": subject, "colors": colors}, ensure_ascii=False))
