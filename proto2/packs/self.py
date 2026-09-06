"""self 工具包 — 看自己現在的狀況（走了幾格、記憶多大、資料夾多大、用掉多少 token）。"""

PROMPT = ("自我檢查：self_status 會告訴你自己現在怎麼樣——被推了幾格、真做事幾格、開機多久、"
          "記憶裡幾則訊息大概多少字、資料夾多大、上一次和整個 LLM 世界今天用掉多少 token。"
          "有人問你「你跑多久了」「你還好嗎」「你吃掉多少」就用它。")

TOOLS = [
    {"name": "self_status",
     "description": "看你自己現在的狀況：走了幾格、真做事幾格、開機多久、記憶多大、"
                    "資料夾多大、上次跟整個 LLM 世界今天用掉多少 token。",
     "parameters": {"type": "object", "properties": {}}},
]


def run(name, args, ctx):
    if name != "self_status":
        return {"error": "self 沒有這個工具：%s" % name}
    return ctx.status()
