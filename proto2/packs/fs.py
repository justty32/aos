"""fs 工具包 — 讀寫檔案、列資料夾、精準修改，並跑短指令。"""

import datetime
import os
import signal
import subprocess
import time


PROMPT = (
    "檔案與短指令：第一次碰一個資料夾，先用 ls 看有什麼。想看檔案時用 read，"
    "而且只讀需要的行數範圍；結果太長就縮小 start／count 再讀。只改一小段時用 edit，"
    "old 要抄到在檔裡剛好出現一次。新檔或確定要整份重寫才用 write。"
    "sh 只跑很快會結束的指令，會超過一分鐘的改用 run_long。"
)

TOOLS = [
    {
        "name": "read",
        "description": "讀文字檔的一段，回行數範圍、總行數和內容。預設從第 1 行讀 200 行。",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "檔案路徑，從世界資料夾算起"},
                "start": {"type": "integer", "minimum": 1, "description": "開始行，預設 1"},
                "count": {"type": "integer", "minimum": 1, "description": "讀幾行，預設 200"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write",
        "description": "覆蓋或追加文字檔；父資料夾不存在會建立。小修改請用 edit。",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "檔案路徑，從世界資料夾算起"},
                "text": {"type": "string", "description": "要寫入的文字"},
                "append": {"type": "boolean", "description": "true 是追加；預設 false，會整檔覆蓋"},
            },
            "required": ["path", "text"],
        },
    },
    {
        "name": "ls",
        "description": "列一層資料夾，不會往下遞迴。預設不列點開頭的名字。",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "資料夾路徑，預設是世界資料夾"},
                "all": {"type": "boolean", "description": "true 才列點開頭的名字"},
            },
        },
    },
    {
        "name": "edit",
        "description": "精準換掉一小段文字。old 剛好出現一次才會修改，否則原檔不動。",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "檔案路徑，從世界資料夾算起"},
                "old": {"type": "string", "description": "原文，要抄到只出現一次"},
                "new": {"type": "string", "description": "換成的新文字，可以是空字串"},
            },
            "required": ["path", "old", "new"],
        },
    },
    {
        "name": "sh",
        "description": "在世界資料夾跑一條短指令。回退出碼、秒數，以及 stdout／stderr 各最後 1500 字。",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "要交給 shell 跑的指令"},
                "stdin": {"type": "string", "description": "可選，餵給指令的標準輸入"},
                "timeout": {
                    "type": "number",
                    "minimum": 0.1,
                    "maximum": 120,
                    "description": "幾秒後算逾時，預設 60，最長 120",
                },
            },
            "required": ["command"],
        },
    },
]


def _path(ctx, path):
    return os.path.join(ctx.world, path)


def _short(ctx, text):
    short = ctx.truncate(text)
    return short, short != text


def _tail(text, size=1500):
    if text is None:
        return "", False
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    return text[-size:], len(text) > size


def _read(args, ctx):
    shown_path = args.get("path") or ""
    start = int(args.get("start") or 1)
    count = int(args.get("count") or 200)
    if start < 1 or count < 1:
        return {"error": "start 和 count 都要大於 0"}
    try:
        with open(_path(ctx, shown_path), encoding="utf-8") as f:
            lines = f.readlines()
    except (OSError, UnicodeError) as e:
        return {"error": "讀不到 %s：%s" % (shown_path, e)}
    total = len(lines)
    selected = "".join(lines[start - 1:start - 1 + count])
    text, cut_by_chars = _short(ctx, selected)
    end = min(total, start - 1 + count) if start <= total else 0
    remaining = max(0, total - end)
    result = {"path": shown_path, "start": start, "end": end, "total": total, "text": text}
    if remaining or cut_by_chars:
        result["truncated"] = True
        notes = []
        if remaining:
            notes.append("總共 %d 行，還有 %d 行沒看；用 start=%d 續讀" % (total, remaining, end + 1))
        if cut_by_chars:
            notes.append("這段文字仍太長；請縮小 start／count")
        result["note"] = "；".join(notes)
    return result


def _write(args, ctx):
    shown_path = args.get("path") or ""
    text = args.get("text")
    if text is None:
        return {"error": "少了要寫入的 text"}
    append = bool(args.get("append"))
    path = _path(ctx, shown_path)
    try:
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "a" if append else "w", encoding="utf-8") as f:
            f.write(text)
    except (OSError, UnicodeError) as e:
        return {"error": "寫不了 %s：%s" % (shown_path, e)}
    return {"path": shown_path, "bytes": len(text.encode("utf-8")),
            "mode": "append" if append else "overwrite"}


def _ls(args, ctx):
    shown_path = args.get("path") or "."
    show_all = bool(args.get("all"))
    try:
        entries = [e for e in os.scandir(_path(ctx, shown_path))
                   if show_all or not e.name.startswith(".")]
        entries.sort(key=lambda e: e.name.casefold())
        total = len(entries)
        rows = []
        for entry in entries[:200]:
            stat = entry.stat()
            changed = datetime.datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds")
            rows.append("%s\t%s\t%d bytes\t%s" %
                        ("dir" if entry.is_dir() else "file", entry.name, stat.st_size, changed))
    except OSError as e:
        return {"error": "列不了 %s：%s" % (shown_path, e)}
    text, cut_by_chars = _short(ctx, "\n".join(rows))
    result = {"path": shown_path, "total": total, "shown": min(total, 200), "text": text}
    if total > 200 or cut_by_chars:
        result["truncated"] = True
        if total > 200:
            result["note"] = "只列前 200 個，還有 %d 個沒列" % (total - 200)
        if cut_by_chars:
            extra = "清單文字太長；請改列更小的資料夾"
            result["note"] = result.get("note", "") + ("；" if result.get("note") else "") + extra
    return result


def _edit(args, ctx):
    shown_path = args.get("path") or ""
    old = args.get("old")
    new = args.get("new")
    if old is None or new is None:
        return {"error": "old 和 new 都要給"}
    path = _path(ctx, shown_path)
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except (OSError, UnicodeError) as e:
        return {"error": "讀不到 %s：%s" % (shown_path, e)}
    matches = text.count(old)
    if matches != 1:
        return {"error": "old 出現 %d 次，檔案沒改；請把 old 抄長一點，讓它剛好只出現一次" % matches}
    index = text.index(old)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text.replace(old, new, 1))
    except (OSError, UnicodeError) as e:
        return {"error": "寫不了 %s：%s" % (shown_path, e)}
    return {"path": shown_path, "line": text[:index].count("\n") + 1,
            "replaced_chars": len(old)}


def _sh(args, ctx):
    command = args.get("command") or ""
    timeout = args.get("timeout", 60)
    try:
        timeout = float(timeout)
    except (TypeError, ValueError):
        return {"error": "timeout 要是秒數，預設 60，最長 120"}
    if timeout <= 0 or timeout > 120:
        return {"error": "timeout 要大於 0，而且最長 120 秒"}
    started = time.monotonic()
    process = subprocess.Popen(command, shell=True, cwd=ctx.world,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        stdout, stderr = process.communicate(input=args.get("stdin"), timeout=timeout)
    except subprocess.TimeoutExpired as e:
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
        if e.output and not stdout:
            stdout = e.output
        if e.stderr and not stderr:
            stderr = e.stderr
        out, out_cut = _tail(stdout)
        err, err_cut = _tail(stderr)
        return {"error": "跑超過 %g 秒被停止了；長指令請改用 run_long" % timeout,
                "exit": None, "seconds": round(time.monotonic() - started, 3),
                "stdout": out, "stderr": err,
                "stdout_truncated": out_cut, "stderr_truncated": err_cut}
    out, out_cut = _tail(stdout)
    err, err_cut = _tail(stderr)
    return {"exit": process.returncode, "seconds": round(time.monotonic() - started, 3),
            "stdout": out, "stderr": err,
            "stdout_truncated": out_cut, "stderr_truncated": err_cut}


def run(name, args, ctx):
    handlers = {"read": _read, "write": _write, "ls": _ls, "edit": _edit, "sh": _sh}
    handler = handlers.get(name)
    if handler is None:
        return {"error": "fs 沒有這個工具：%s" % name}
    return handler(args, ctx)
