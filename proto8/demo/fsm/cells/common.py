"""demo 的格共用：資料夾位置（環境變數 DEMO_DIR）與對話檔 history（設定的 `history`，OpenAI messages 陣列）的讀寫。"""
import json
import os
import sys

DIR = os.environ["DEMO_DIR"]
CFG = {}


def args():
    """fsm 從 stdin 給的那份＝fsm 設定本身＋`fsm_state`（state 窗整份）。內層的格拿到的是內層設定＋外層 cfg 當預設。"""
    CFG.update(json.load(sys.stdin))
    return CFG


def ret(doc):
    """stdout 吐一份結果（N-12）：fsm 讀最後一份的 next、data。"""
    print(json.dumps(doc, ensure_ascii=False))


def history():
    with open(CFG["history"], encoding="utf-8") as f:
        return json.load(f)


def save(msgs):
    path = CFG["history"]
    tmp = os.path.join(os.path.dirname(path), "." + os.path.basename(path) + ".tmp")   # 先寫暫存檔再改名（N-05）
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(msgs, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)
