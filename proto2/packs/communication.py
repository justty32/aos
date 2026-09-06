"""communication 工具包 — 用通訊錄跟別的 agent 寄信。"""
import os


PROMPT = (
    "交流：寄信前如果不確定名字，先用 mail_who。mail_send 寄一封新信；"
    "讀完別人的信後用 mail_reply 回覆，source 跟 id 照 inbox_read 的結果填。"
    "mail_broadcast 把同一句話寄給指定的人；不給 to 時只寄給父與直接小孩。"
    "寄出後若要等回覆，用 mail_wait 登記剛才拿到的 id；系統會睡到回信或新信來。"
)

TOOLS = [
    {"name": "mail_send", "description": "寄一封新信給通訊錄裡的一個人。",
     "parameters": {"type": "object", "properties": {
         "to": {"type": "string", "description": "收件人的通訊錄名字"},
         "content": {"type": "string", "description": "要說的話"}},
         "required": ["to", "content"]}},
    {"name": "mail_reply", "description": "回覆一封剛讀過的信，保留回信關係。",
     "parameters": {"type": "object", "properties": {
         "source": {"type": "string", "description": "來信的來源名字"},
         "id": {"type": "string", "description": "來信的檔名"},
         "content": {"type": "string", "description": "回覆內容"}},
         "required": ["source", "id", "content"]}},
    {"name": "mail_broadcast", "description": "把同一句話寄給多人；不給名單就寄給父與直接小孩。",
     "parameters": {"type": "object", "properties": {
         "content": {"type": "string", "description": "要說的話"},
         "to": {"type": "array", "items": {"type": "string"},
                "description": "收件人名字；省略時是父與直接小孩"}},
         "required": ["content"]}},
    {"name": "mail_who", "description": "看通訊錄裡有誰、彼此關係，以及資料夾還在不在。",
     "parameters": {"type": "object", "properties": {
         "alive_only": {"type": "boolean", "description": "只列資料夾還在的人"}}}},
    {"name": "mail_wait", "description": "登記正在等哪封信的回覆；馬上返回，不會阻塞。",
     "parameters": {"type": "object", "properties": {
         "id": {"type": "string", "description": "剛寄出那封信的 id"},
         "note": {"type": "string", "description": "提醒自己在等什麼"}},
         "required": ["id"]}},
]


def _contacts(ctx):
    contacts = dict(ctx.contacts())
    user_dir = os.environ.get("AOS_USER_DIR")
    if user_dir and "user" not in contacts:
        contacts["user"] = {"dir": user_dir, "relation": "user"}
    return contacts


def _entry_dir(ctx, entry):
    path = entry.get("dir") if isinstance(entry, dict) else entry
    if not isinstance(path, str):
        return ""
    try:
        return ctx.world_of(path)
    except ValueError:
        return ""


def _send(ctx, to, content, reply_to=None, thread=None):
    contacts = _contacts(ctx)
    if to not in contacts:
        return {"ok": False, "error": "通訊錄裡沒有這個人：%s" % to}

    target = to if to in ctx.contacts() else ctx.world_of(_entry_dir(ctx, contacts[to]))
    extra = {}
    if reply_to:
        extra["reply_to"] = reply_to
    if thread:
        extra["thread"] = thread
    path = ctx.put_mail(target, ctx.name, content, **extra)
    if not path:
        return {"ok": False, "error": "寄不到這個人：%s" % to}

    mail_id = os.path.basename(path)
    msg = ctx.read_json(path, {})
    msg["to"] = to
    msg["thread"] = thread or os.path.splitext(mail_id)[0]
    ctx.write_json(path, msg)
    result = {"ok": True, "to": to, "id": mail_id}
    if reply_to:
        result["reply_to"] = reply_to
    return result


def _read_letter(ctx, source, mail_id):
    for middle in ("", "read"):
        path = os.path.join(ctx.home, "inbox", source, middle, mail_id)
        data = ctx.read_json(path, None)
        if isinstance(data, dict):
            return data
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    return item
    return None


def _family(ctx):
    names = []
    parent = ctx.parent()
    if parent and parent.get("name"):
        names.append(parent["name"])
    names.extend(ctx.kids().keys())
    return list(dict.fromkeys(names))


def _who(ctx, alive_only=False):
    parent = ctx.parent() or {}
    parent_name = parent.get("name")
    kids = set(ctx.kids())
    rows = []
    for name, entry in sorted(_contacts(ctx).items()):
        path = _entry_dir(ctx, entry)
        relation = entry.get("relation") if isinstance(entry, dict) else None
        if not relation:
            relation = "parent" if name == parent_name else "kid" if name in kids else "contact"
        exists = os.path.isdir(path)
        if alive_only and not exists:
            continue
        rows.append({"name": name, "relation": relation, "dir": path, "exists": exists})
    return rows


def run(name, args, ctx):
    if name == "mail_send":
        return _send(ctx, args.get("to") or "", args.get("content") or "")
    if name == "mail_reply":
        source = args.get("source") or ""
        mail_id = args.get("id") or ""
        original = _read_letter(ctx, source, mail_id)
        if original is None:
            return {"ok": False, "error": "找不到這封信：%s/%s" % (source, mail_id)}
        to = original.get("from") or source
        thread = original.get("thread") or os.path.splitext(mail_id)[0]
        return _send(ctx, to, args.get("content") or "", reply_to=mail_id, thread=thread)
    if name == "mail_broadcast":
        names = args.get("to")
        if names is None:
            names = _family(ctx)
        sent, failed = [], []
        for to in names:
            result = _send(ctx, to, args.get("content") or "")
            (sent if result.get("ok") else failed).append(to)
        return {"ok": not failed, "sent": sent, "failed": failed}
    if name == "mail_who":
        return _who(ctx, bool(args.get("alive_only")))
    if name == "mail_wait":
        reply_to = args.get("id") or ""
        request = ctx.send("mail", {"reply_to": reply_to, "note": args.get("note") or ""},
                           mail_reply_to=reply_to, timeout_steps=120)
        ctx.write_json(os.path.join(ctx.home, "side", "mail-meta", request),
                       {"reply_to": reply_to, "note": args.get("note") or ""})
        ctx.sleep_until("mail", request)
        return {"ok": True, "id": request}
    return {"error": "communication 沒有這個工具：%s" % name}


def on_result(ctx, kind, name, result):
    meta = ctx.read_json(os.path.join(ctx.home, "side", "mail-meta", name), {})
    if result.get("error"):
        return None
    text = "你等的那封回來了：%s" % meta.get("reply_to")
    if meta.get("note"):
        text += "（%s）" % meta["note"]
    if result.get("content"):
        text += "：" + str(result["content"])
    return text


def on_reply(ctx, msg):
    user_dir = os.environ.get("AOS_USER_DIR")
    if not user_dir:
        return
    path = ctx.put_mail(user_dir, ctx.name, msg.get("content") or "")
    if path:
        mail = ctx.read_json(path, {})
        mail["to"] = "user"
        ctx.write_json(path, mail)
