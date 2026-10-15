"""agent 判官的入口：通用 kernel 的判官格（stdin＝kernel 的 state 窗子集 queue／running／slots／budget、stdout＝{run, defer, reject}）
↔ agent 當函數（定義資料夾 judge/，C-46：json＋資料夾＋inst，不靠專用程式）。

    aos-demo kernels/general/judge/ask_judge.py [定義資料夾]   （kernel 設定的 judge 指 judge-agent.json 就換上它；PATH 要有 proto8/bin、demo/bin）

定義資料夾＝暫存 frame 的 env.json 的 parent，沒給＝本資料夾 judge/；相對路徑從 cwd 算。要換腦不必改 judge/ 也不必抄腳本：
另開一個資料夾放 brain.json＋env.json（{"parent": "…/judge"}），把它當引數給（frame 照 env.json 鏈往上找，近的蓋遠的，C-46）。
（10-15 使用者「都按照推薦」：原本寫死 judge/，見 thinking 2026-10-15-litellm-live #2）

開一個暫存 frame：env.json 指回定義資料夾、args.json＝{"question": stdin 原樣}，在 frame 裡跑 `aos loop judge/loop.json`，
讀 ret.json，拿它 reply 裡的 JSON 物件（第一個 { 到最後一個 }）印出來。
agent 出錯（ret.json 是錯、沒有 ret.json）、回的不是 JSON＝stderr 一份錯誤、退出 1——kernel 這拍就退回規則。frame 用完就刪。
只看最後的答案，不靠模型的思考內容（system.md 開頭 /no_think，Qwen3 會照辦；見 lib agent.md）。
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def fail(code, msg):
    print(json.dumps({"error": {"code": code, "msg": msg}}, ensure_ascii=False), file=sys.stderr)
    sys.exit(1)


if len(sys.argv) > 2:
    fail("Usage", "ask_judge.py [定義資料夾]")
parent = os.path.abspath(sys.argv[1]) if len(sys.argv) == 2 else HERE
if not os.path.isdir(parent):
    fail("DefinitionMissing", "定義資料夾 %s 不存在" % parent)
snap = sys.stdin.read()
frame = tempfile.mkdtemp(prefix="aos-judge-frame-")
try:
    for name, doc in (("env.json", {"parent": parent}), ("args.json", {"question": snap})):
        with open(os.path.join(frame, name), "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False)
    subprocess.run(["aos", "loop", os.path.join(HERE, "loop.json")], cwd=frame, stdout=subprocess.DEVNULL)
    try:
        with open(os.path.join(frame, "ret.json"), encoding="utf-8") as f:
            ret = json.load(f)
    except (OSError, ValueError):
        fail("ReturnMissing", "agent 判官沒寫 ret.json（沒跑完）")
    if "error" in ret:
        fail("JudgeFailed", "agent 判官出錯：%s" % json.dumps(ret["error"], ensure_ascii=False))
    text = ret.get("reply") or ""
    try:
        doc = json.loads(text[text.index("{"):text.rindex("}") + 1])
    except (ValueError, IndexError) as e:
        fail("JudgeReplyBad", "agent 的回覆不是 JSON 物件：%s" % e)
    print(json.dumps(doc, ensure_ascii=False))
finally:
    shutil.rmtree(frame, ignore_errors=True)
