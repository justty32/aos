"""kids 工具包：生小孩、看進度、寄活、暫停與收掉。"""
import os
import shutil


MAX_DEPTH = 2
PROMPT = (
    "子 agent：spawn 生一個有自己人格與記憶的小孩。clock 不確定就用 shared；"
    "使用者說 coder、manager 或 chat 時，把同名值放進 template；模板會帶自己的工具包。"
    "shared 跟你一起走，own 有自己的鐘。kids_tell 派活，kids_list 看進度，"
    "kids_pause／kids_resume 暫停或續跑，kids_kill 收掉。不要卡在這一格等小孩；"
    "先告訴使用者你已派工，下一格再看信箱或 kids_list。小孩回話會自動進你的信箱。"
)


def _object(properties, required=None):
    spec = {"type": "object", "properties": properties}
    if required:
        spec["required"] = required
    return spec


TOOLS = [
    {"name": "spawn", "description": "生一個子 agent。shared 跟你走；own 自己走。",
     "parameters": _object({
         "name": {"type": "string", "description": "名字，只能用英數字、底線、減號"},
         "persona": {"type": "string", "description": "它的人格與工作方式"},
         "packs": {"type": "array", "items": {"type": "string"},
                   "description": "它可用的工具包；不給就抄你的"},
         "clock": {"type": "string", "enum": ["shared", "own"],
                   "description": "shared 跟你走（預設）；own 自己走"},
         "task": {"type": "string", "description": "生完立刻交給它的第一件事"},
         "template": {"type": "string", "description": "可選的出廠模板名字"},
     }, ["name", "persona"])},
    {"name": "kids_list", "description": "看所有小孩的鐘、進度、未讀信與最後回話。",
     "parameters": _object({})},
    {"name": "kids_pause", "description": "暫停一個小孩。",
     "parameters": _object({"name": {"type": "string", "description": "小孩名字"}}, ["name"])},
    {"name": "kids_resume", "description": "讓暫停的小孩繼續走。",
     "parameters": _object({"name": {"type": "string", "description": "小孩名字"}}, ["name"])},
    {"name": "kids_kill", "description": "收掉一個小孩。預設保留它的資料夾與記憶。",
     "parameters": _object({
         "name": {"type": "string", "description": "小孩名字"},
         "keep_files": {"type": "boolean", "description": "是否留檔，預設 true"},
     }, ["name"])},
    {"name": "kids_tell", "description": "寄一件事給小孩做。",
     "parameters": _object({
         "name": {"type": "string", "description": "小孩名字"},
         "text": {"type": "string", "description": "要它做的事"},
     }, ["name", "text"])},
]


def _registry(ctx):
    data = ctx.kids()
    return data if isinstance(data, dict) else {}


def _save_registry(ctx, data):
    ctx.write_json(os.path.join(ctx.home, "kids.json"), data)


def _kid(ctx, name):
    info = _registry(ctx).get(name)
    if not isinstance(info, dict):
        return None, None, "找不到這個小孩：%s" % name
    if not info.get("alive", True):
        return info, None, "這個小孩已經收掉了：%s" % name
    path = info.get("dir") or os.path.join(ctx.kids_dir(), name)
    if not os.path.isdir(path):
        return info, None, "找不到小孩的資料夾：%s" % path
    return info, os.path.abspath(path), None


def _depth(ctx):
    """沿 parent.json 往上數。spawn 生的子世界都是平鋪 home，最多只走兩次。"""
    depth = 0
    parent = ctx.parent()
    while isinstance(parent, dict) and parent.get("dir"):
        depth += 1
        parent = ctx.read_json(os.path.join(parent["dir"], "parent.json"), None)
    return depth


def _inst_lines(ctx):
    path = os.path.join(ctx.world, ".aos", "inst")
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return path, f.read().splitlines()
    except OSError:
        return path, []


def _shared_command(ctx, child):
    return "aos-exec " + os.path.relpath(child, ctx.world)


def _set_shared(ctx, child, action):
    path, lines = _inst_lines(ctx)
    command = _shared_command(ctx, child)
    paused = "# " + command
    found = False
    out = []
    for line in lines:
        if line.strip() == command:
            found = True
            if action == "pause":
                out.append(paused)
            elif action == "resume":
                out.append(line)
        elif line.strip() == paused:
            found = True
            if action == "resume":
                out.append(command)
            elif action == "pause":
                out.append(line)
        else:
            out.append(line)
    if not found:
        return False, "父的 .aos/inst 找不到這個小孩"
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(out) + ("\n" if out else ""))
    except OSError as e:
        return False, "改不了父的 .aos/inst：%s" % e
    words = {"pause": "暫停了", "resume": "續跑了", "kill": "收掉了"}
    return True, words[action]


def _shared_paused(ctx, child):
    _path, lines = _inst_lines(ctx)
    return ("# " + _shared_command(ctx, child)) in [line.strip() for line in lines]


def _own_paused(ctx, child, fallback=False):
    daemon = os.environ.get("AOS_DAEMON_DIR")
    clocks = os.path.join(daemon, "clocks") if daemon else ""
    if os.path.isdir(clocks):
        for filename in os.listdir(clocks):
            if not filename.endswith(".json"):
                continue
            row = ctx.read_json(os.path.join(clocks, filename), None)
            if (isinstance(row, dict) and row.get("dir")
                    and os.path.realpath(row["dir"]) == os.path.realpath(child)):
                return row.get("state") == "paused"
    return bool(fallback)


def _unread(child):
    box = os.path.join(child, "inbox")
    if not os.path.isdir(box):
        return 0
    total = 0
    for source in os.listdir(box):
        folder = os.path.join(box, source)
        if os.path.isdir(folder):
            total += sum(name.endswith(".json") for name in os.listdir(folder))
    return total


def _last_reply(ctx, child):
    box = os.path.join(child, "outbox")
    if not os.path.isdir(box):
        return ""
    names = sorted(name for name in os.listdir(box) if name.endswith(".json"))
    if not names:
        return ""
    msg = ctx.read_json(os.path.join(box, names[-1]), {})
    text = str(msg.get("content") or "") if isinstance(msg, dict) else ""
    return ctx.truncate(" ".join(text.split()), 120)


def _spawn(args, ctx):
    name = args.get("name") or ""
    clock = args.get("clock") or "shared"
    if clock not in ("shared", "own"):
        return {"ok": False, "name": name, "path": None, "clock": clock,
                "message": "clock 只能是 shared 或 own"}
    depth = _depth(ctx)
    if depth >= MAX_DEPTH:
        return {"ok": False, "name": name, "path": None, "clock": clock,
                "message": "你已經在第 %d 層，不能再生了" % depth}
    task = args.get("task")
    ok, message = ctx.spawn(
        name, args.get("persona") or "", clock, args.get("template"),
        packs=args.get("packs") if "packs" in args else None,
        task=task, depth=depth + 1)
    child = os.path.abspath(os.path.join(ctx.kids_dir(), name)) if ok else None
    if not ok:
        return {"ok": False, "name": name, "path": None, "clock": clock,
                "message": message}

    return {"ok": True, "name": name, "path": child, "clock": clock,
            "message": message}


def _list(ctx):
    rows = []
    for name, info in sorted(_registry(ctx).items()):
        if not isinstance(info, dict):
            continue
        child = os.path.abspath(info.get("dir") or os.path.join(ctx.kids_dir(), name))
        state = ctx.read_json(os.path.join(child, "state.json"), {})
        state = state if isinstance(state, dict) else {}
        clock = info.get("clock") or "shared"
        if not info.get("alive", True):
            paused = False
        elif clock == "own":
            paused = _own_paused(ctx, child, info.get("paused", False))
        else:
            paused = _shared_paused(ctx, child)
        rows.append({
            "name": name, "clock": clock, "state": state.get("state") or "idle",
            "busy": state.get("busy") or 0, "step": state.get("step") or 0,
            "unread": _unread(child), "last": _last_reply(ctx, child), "paused": paused,
        })
    return rows


def _pause_or_resume(name, ctx, resume=False):
    info, child, error = _kid(ctx, name)
    if error:
        return {"ok": False, "name": name, "message": error}
    if info.get("clock") == "own":
        ok, message = (ctx.continue_clock(child) if resume else ctx.pause_clock(child))
    else:
        ok, message = _set_shared(ctx, child, "resume" if resume else "pause")
    if ok:
        registry = _registry(ctx)
        registry[name]["paused"] = not resume
        _save_registry(ctx, registry)
    return {"ok": ok, "name": name, "message": message}


def _kill(args, ctx):
    name = args.get("name") or ""
    keep = args.get("keep_files", True) is not False
    info, child, error = _kid(ctx, name)
    if error:
        return {"ok": False, "name": name, "kept": keep, "message": error}
    if info.get("clock") == "own":
        ok, message = ctx.unregister_clock(child)
    else:
        ok, message = _set_shared(ctx, child, "kill")
    if not ok:
        return {"ok": False, "name": name, "kept": keep, "message": message}
    registry = _registry(ctx)
    registry[name]["alive"] = False
    registry[name]["paused"] = False
    _save_registry(ctx, registry)
    if not keep:
        shutil.rmtree(child)
    return {"ok": True, "name": name, "kept": keep,
            "message": "小孩收掉了，%s" % ("資料夾留著" if keep else "資料夾也刪了")}


def _tell(args, ctx):
    name = args.get("name") or ""
    _info, child, error = _kid(ctx, name)
    if error:
        return {"ok": False, "name": name, "path": None, "message": error}
    path = ctx.put_mail(child, "parent", args.get("text") or "")
    if not path:
        return {"ok": False, "name": name, "path": None, "message": "信沒有寄出去"}
    return {"ok": True, "name": name, "path": path}


def run(name, args, ctx):
    if name == "spawn":
        return _spawn(args, ctx)
    if name == "kids_list":
        return _list(ctx)
    if name == "kids_pause":
        return _pause_or_resume(args.get("name") or "", ctx)
    if name == "kids_resume":
        return _pause_or_resume(args.get("name") or "", ctx, resume=True)
    if name == "kids_kill":
        return _kill(args, ctx)
    if name == "kids_tell":
        return _tell(args, ctx)
    return {"error": "kids 沒有這個工具：%s" % name}
