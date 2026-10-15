"""kernel demo 的假腦（思考介面，lib/agent.md）：最後一則 user 開頭是「快」睡 0.05 秒，否則睡 1 秒；回一則 assistant，附 usage。"""
import json
import sys
import time

last = json.load(sys.stdin)["messages"][-1]["content"]
time.sleep(0.05 if last.startswith("快") else 1.0)
print(json.dumps({"role": "assistant", "content": "收到 %s" % last, "usage": {"total_tokens": 7}}, ensure_ascii=False))
