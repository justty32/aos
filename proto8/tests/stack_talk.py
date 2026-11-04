"""stack_talk - 測試用：對一個 stack 說一句、等它答（11-04 起 aos-say／aos-listen 併進 aos-agent、extras/human 刪了；
aos-agent 只管 daemon 表上的，直接 aos-exec 跑的照 aos-agent 02「沒有 --stack」那節：寫信進 <stack>/queue、讀 <stack>/history.jsonl）。
say＝lib/aos/aos_ws.put；listen＝等最新那封不在 queue 的 new/ cur/、history 最後一則是回答，回 (returncode, stdout, stderr) 跟原本的 aos-listen 一樣形狀。"""
import os, sys, time
from types import SimpleNamespace

from aos_bins import ROOT, path_with  # noqa: E402
sys.path.insert(0, str(ROOT / "lib" / "aos"))
import aos_ws  # noqa: E402


def say(stack, text, env=None):
    """寄一封（沒 queue 先 init）；回信件名稱。env＝aos-post 要的 PATH（沒給＝aos_bins 的）。"""
    old = os.environ.get("PATH")
    os.environ["PATH"] = (env or {}).get("PATH") or path_with()
    try:
        return aos_ws.put(str(stack), text)
    finally:
        if old is not None:
            os.environ["PATH"] = old


def listen(stack, timeout=30):
    stack = str(stack)
    queued = aos_ws.names(stack, "new") + aos_ws.names(stack, "cur")
    sig = max(queued, key=aos_ws.letter_key) if queued else None
    end = time.monotonic() + timeout
    while True:
        h = aos_ws.history(stack)
        gone = sig is None or not any(sig in aos_ws.names(stack, s) for s in ("new", "cur"))
        if gone and h and aos_ws.is_answer(h[-1]):
            t = aos_ws.text_of(h[-1])
            return SimpleNamespace(returncode=0, stdout=t if t.endswith("\n") else t + "\n", stderr="")
        if time.monotonic() >= end:
            return SimpleNamespace(returncode=1, stdout="", stderr="stack_talk: AnswerMissing 等了 %g 秒（%s）" % (timeout, sig))
        time.sleep(0.05)
