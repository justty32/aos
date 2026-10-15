"""demo 的格共用：對話檔 history.json（cwd＝frame 裡，OpenAI messages 陣列）的讀寫、吐結果。"""
import json
import os

HISTORY = "history.json"


def ret(doc):
    """stdout 吐一份結果（N-12）：fsm 讀最後一份的 next。"""
    print(json.dumps(doc, ensure_ascii=False))


def history():
    with open(HISTORY, encoding="utf-8") as f:
        return json.load(f)


def save(msgs):
    tmp = "." + HISTORY + ".tmp"                      # 先寫暫存檔再改名（N-05）
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(msgs, f, ensure_ascii=False, indent=1)
    os.replace(tmp, HISTORY)
