"""mailbox 工具包 — 讀自己的信箱。

信箱在 `<home>/inbox/<來源>/`，一個來源一個資料夾；讀過的信搬進該來源的 `read/`。
狀態機那邊只會跟模型說「你有新信：team 1 封」，信的內容要模型自己用這四個工具去拿。
"""

PROMPT = ("信箱：你的信在 inbox/ 底下，一個來源一個資料夾（user、team、kernel、別的 agent…）。"
          "有人跟你說「你有新信」的時候，先用 inbox_sources 看哪個來源有未讀，"
          "再用 inbox_list 看有哪幾封，用 inbox_read 讀一封、或 inbox_read_all 把一個來源一次讀完。"
          "讀過的信會被搬進 read/，之後不會再出現在未讀裡，所以看到了就要處理掉。")

TOOLS = [
    {"name": "inbox_sources",
     "description": "看信箱有哪些來源，每個來源各有幾封未讀、幾封讀過。",
     "parameters": {"type": "object", "properties": {
         "unread_only": {"type": "boolean", "description": "只列還有未讀的來源"}}}},
    {"name": "inbox_list",
     "description": "列一個來源的未讀信：每封的 id（就是檔名）、時間、誰寄的、開頭一小段。",
     "parameters": {"type": "object", "properties": {
         "source": {"type": "string", "description": "來源名字，例如 user、team"}},
         "required": ["source"]}},
    {"name": "inbox_read",
     "description": "讀某個來源的某一封未讀信；讀完那封會被搬進 read/，不再算未讀。",
     "parameters": {"type": "object", "properties": {
         "source": {"type": "string", "description": "來源名字"},
         "id": {"type": "string", "description": "信件 id，就是 inbox_list 給你的檔名"}},
         "required": ["source", "id"]}},
    {"name": "inbox_read_all",
     "description": "一次讀完一個來源所有未讀的信，全部搬進 read/。",
     "parameters": {"type": "object", "properties": {
         "source": {"type": "string", "description": "來源名字"}},
         "required": ["source"]}},
]


def run(name, args, ctx):
    src = args.get("source") or ""
    if name == "inbox_sources":
        only = bool(args.get("unread_only"))
        rows = []
        for s in ctx.sources():
            row = {"source": s, "unread": len(ctx.unread(s)), "read": len(ctx.read_done(s))}
            if only and not row["unread"]:
                continue
            rows.append(row)
        return rows
    if name == "inbox_list":
        rows = []
        for fname in ctx.unread(src):
            for mail in ctx.mail_of(src, fname):
                rows.append({"id": fname, "time": mail.get("time") or "",
                             "from": mail.get("from") or src, "preview": ctx.preview(mail)})
        return rows
    if name == "inbox_read":
        fname = args.get("id") or ""
        if fname not in ctx.unread(src):
            return {"error": "這個來源沒有這封未讀的信：%s/%s" % (src, fname)}
        mails = ctx.mail_of(src, fname)
        ctx.mark_read(src, fname)
        return {"source": src, "id": fname, "mails": mails}
    if name == "inbox_read_all":
        out = []
        for fname in ctx.unread(src):
            out.append({"id": fname, "mails": ctx.mail_of(src, fname)})
            ctx.mark_read(src, fname)
        return {"source": src, "count": len(out), "letters": out}
    return {"error": "mailbox 沒有這個工具：%s" % name}
