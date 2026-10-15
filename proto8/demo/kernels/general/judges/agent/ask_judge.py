"""agent 判官的入口：通用 kernel 的判官格（stdin＝kernel 的 state 窗子集 queue／running／slots／budget、stdout＝{run, reject}）
↔ agent 當函數（定義資料夾 judges/agent/，C-46：json＋資料夾＋inst，不靠專用程式）。

    aos-demo kernels/general/judges/agent/ask_judge.py [定義資料夾]   （kernel 設定的 judge 指 judges/agent.json 就換上它；PATH 要有 proto8/bin、demo/bin）

定義資料夾＝暫存 frame 的 frame.json 的 parent，沒給＝本資料夾 judges/agent/；相對路徑從 cwd 算。要換腦不必改 judges/agent/：
另開一個資料夾放 brain.json＋frame.json（{"parent": "…/judge"}），把它當引數給（frame 照 frame.json 鏈往上找，近的蓋遠的，C-46）。

開一個暫存 frame：frame.json 指回定義資料夾、args.json＝{"question": stdin 原樣}，在 frame 裡跑 `aos loop judges/agent/loop.json`，
讀 ret.json，把它的 reply 原樣印出來（agent 的 system 提示要它只回那份 JSON；不是 JSON＝kernel 這拍退回規則，同一條路）。
任何失敗（引數不對、定義資料夾不存在、ret.json 是錯或沒有）一律 stderr 一份 `JudgeFailed`、退出 1（10-15 深夜 KISS 批次 1，
原本分五種代號）。frame 用完就刪。只看最後的答案，不靠模型的思考內容（system.md 開頭 /no_think）。
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def fail(msg):
    print(json.dumps({"error": {"code": "JudgeFailed", "msg": msg}}, ensure_ascii=False), file=sys.stderr)
    sys.exit(1)


if len(sys.argv) > 2:
    fail("用法：ask_judge.py [定義資料夾]")
parent = os.path.abspath(sys.argv[1]) if len(sys.argv) == 2 else HERE
if not os.path.isdir(parent):
    fail("定義資料夾 %s 不存在" % parent)
snap = sys.stdin.read()
frame = tempfile.mkdtemp(prefix="aos-judge-frame-")
try:
    for name, doc in (("frame.json", {"parent": parent}), ("args.json", {"question": snap})):
        with open(os.path.join(frame, name), "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False)
    subprocess.run(["aos", "loop", os.path.join(HERE, "loop.json")], cwd=frame, stdout=subprocess.DEVNULL)
    try:
        with open(os.path.join(frame, "ret.json"), encoding="utf-8") as f:
            ret = json.load(f)
    except (OSError, ValueError):
        fail("agent 判官沒寫 ret.json（沒跑完）")
    if "error" in ret:
        fail("agent 判官出錯：%s" % json.dumps(ret["error"], ensure_ascii=False))
    print(ret.get("reply") or "")
finally:
    shutil.rmtree(frame, ignore_errors=True)
