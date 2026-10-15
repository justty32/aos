"""demo 的格共用：資料夾位置（DEMO_DIR）與對話檔 work/convo.json 的讀寫。"""
import json
import os
import sys

DIR = os.environ["DEMO_DIR"]
CONVO = os.path.join(DIR, "work", "convo.json")


def args():
    """fsm 從 stdin 給的 {"state", "step", "prev"}。"""
    return json.load(sys.stdin)


def ret(doc):
    """stdout 吐一份結果（N-12）：fsm 讀最後一份的 next、data。"""
    print(json.dumps(doc, ensure_ascii=False))


def convo():
    with open(CONVO, encoding="utf-8") as f:
        return json.load(f)


def save(msgs):
    tmp = os.path.join(os.path.dirname(CONVO), ".convo.json.tmp")       # 先寫 . 開頭的暫存檔再改名（N-05）
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(msgs, f, ensure_ascii=False, indent=1)
    os.replace(tmp, CONVO)
