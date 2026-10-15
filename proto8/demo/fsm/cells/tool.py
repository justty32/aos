"""tool 格：照 prev 裡的工具呼叫跑（demo 只有 clock＝現在時間），結果接進對話，回 next=thinking 讓模型再想一次。"""
import time

from common import args, convo, ret, save

call = args()["prev"] or {}
result = time.strftime("%H:%M:%S") if call.get("tool") == "clock" else "不認得的工具 %r" % call.get("tool")
save(convo() + [{"role": "tool", "text": result}])
ret({"next": "thinking", "data": {"tool": call.get("tool"), "result": result}})
