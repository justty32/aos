#!/usr/bin/env python3
# NAME - 純函數（selfopt extract_tool 建的殼）：照同資料夾 rules.json 的規則依序做正規式替換
# 介面（proto8/lib 契約）：stdin {"text": 原文, …其餘忽略} → stdout 一行 {"text": 改後, "changes": [{"rule": 第幾條, "note", "counter_replaced"}]}（只列有換到的）。
# rules.json：[{"pattern": 正規式, "replace": 換成（可用 \1）, "max_count"?: 最多換幾處（0＝全部）, "note"?: 這條為什麼}]。
# 錯：stderr 與 stdout 各一行「NAME: 代號 原因」退 1——ArgumentsBad（stdin 不是 {text}）、TableBad（rules.json 讀不了或規則壞）。
import json, os, re, sys

NAME = os.path.basename(os.path.dirname(os.path.realpath(__file__)))


def die(code, reason):
    line = "%s: %s %s" % (NAME, code, reason)
    print(line, file=sys.stderr)
    print(line)
    sys.exit(1)


try:
    args = json.loads(sys.stdin.read() or "{}")
except ValueError as e:
    die("ArgumentsBad", "stdin 不是 JSON：%s" % e)
if not isinstance(args, dict) or not isinstance(args.get("text"), str):
    die("ArgumentsBad", "缺 text（字串）")
try:
    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "rules.json"), encoding="utf-8") as f:
        rules = json.load(f)
    compiled = [(re.compile(r["pattern"]), r["replace"], int(r.get("max_count", 0)), r.get("note", "")) for r in rules]
except (OSError, ValueError, KeyError, TypeError, re.error) as e:
    die("TableBad", "rules.json 讀不了或規則壞：%s" % e)
text, changes = args["text"], []
for i, (rx, rep, cap, note) in enumerate(compiled, 1):
    try:
        text, c = rx.subn(rep, text, count=cap)
    except (re.error, IndexError) as e:
        die("TableBad", "第 %d 條換不了：%s" % (i, e))
    if c:
        changes.append({"rule": i, "note": note, "counter_replaced": c})
print(json.dumps({"text": text, "changes": changes}, ensure_ascii=False))
