"""agent 判官的入口：通用 kernel 的判官格（stdin＝kernel 的 state 窗子集 queue／running／slots／budget、stdout＝{run, defer, reject}）↔ agent 當函數（aos_agent_call）。

    python3 judge/ask_judge.py judge/agent.json      （kernel 設定的 judge 指 judge-agent.json 就換上它）

把它原樣當 user 訊息交給 agent，拿它最後一句話裡的 JSON 物件（第一個 { 到最後一個 }）印出來。
agent 出錯、回的不是 JSON＝stderr 一份錯誤、退出 1——kernel 這拍就退回規則。frame 用完就刪。
只看最後的答案，不靠模型的思考內容（system.md 開頭 /no_think，Qwen3 會照辦；見 lib agent.md）。
"""
import json
import os
import shutil
import sys
import tempfile

LIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "lib")
sys.path.insert(0, LIB)
import aos_agent_call  # noqa: E402
import aos_cli  # noqa: E402

snap = sys.stdin.read()
frame = tempfile.mkdtemp(prefix="aos-judge-frame-")
try:
    out = aos_agent_call.Agent(sys.argv[1]).call(frame, history=[{"role": "user", "content": snap}])
    text = out.get("reply") or ""
    doc = json.loads(text[text.index("{"):text.rindex("}") + 1])
    print(json.dumps(doc, ensure_ascii=False))
except aos_cli.CliError as e:
    aos_cli.error(e.code, e.msg)
    sys.exit(1)
except (ValueError, IndexError) as e:
    aos_cli.error("JudgeReplyBad", "agent 的回覆不是 JSON 物件：%s" % e)
    sys.exit(1)
finally:
    shutil.rmtree(frame, ignore_errors=True)
