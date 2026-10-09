"""假傳輸：先記遠端受理次數，再回覆；這個計數不供閘道恢復查詢。"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "lib"))
from aos7_fs import edit_json  # noqa: E402


def send(node, call_id, request, deadline):
    """模擬一次受理；沒有去重，也沒有隱藏重試。"""
    fake = request.get("fake") or {}
    mode, u = fake.get("mode", "ok"), fake.get("usage", 10)

    def count(remote):
        sends = remote["sends"]
        sends[call_id] = sends.get(call_id, 0) + 1
        return remote
    edit_json(os.path.join(node, "llmcall", "fake-remote.json"), count, default={"sends": {}})
    if mode not in ("ok", "over", "no_usage", "fail", "reject", "late"):
        raise ValueError("未知 mode：%s" % mode)
    if mode == "late":
        time.sleep(fake.get("delay", 0))
    usage = None if mode in ("no_usage", "reject") else {
        "total_tokens": u, "prompt_tokens": u - u // 3, "completion_tokens": u // 3}
    return {"status": "error" if mode == "fail" else "reject" if mode == "reject" else "ok",
            "billed": mode != "reject", "body": "假傳輸處理失敗" if mode == "fail" else
            fake.get("text", '{"v":1,"mode":"keep"}'), "usage": usage}
