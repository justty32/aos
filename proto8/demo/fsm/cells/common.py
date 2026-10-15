"""demo 的格共用：資料夾位置（DEMO_DIR）與對話檔 history（DEMO_HISTORY，OpenAI messages 陣列）的讀寫。"""
import json
import os
import sys

DIR = os.environ["DEMO_DIR"]
HISTORY = os.environ["DEMO_HISTORY"]


def args():
    """fsm 從 stdin 給的 {"state", "step", "prev"}。"""
    return json.load(sys.stdin)


def ret(doc):
    """stdout 吐一份結果（N-12）：fsm 讀最後一份的 next、data。"""
    print(json.dumps(doc, ensure_ascii=False))


def history():
    with open(HISTORY, encoding="utf-8") as f:
        return json.load(f)


def save(msgs):
    tmp = os.path.join(os.path.dirname(HISTORY), "." + os.path.basename(HISTORY) + ".tmp")   # 先寫暫存檔再改名（N-05）
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(msgs, f, ensure_ascii=False, indent=1)
    os.replace(tmp, HISTORY)
