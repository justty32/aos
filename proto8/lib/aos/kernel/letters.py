# 包 aos-post 的收信、轉寄、拒信、代回、轉寄對照表與排隊 body。
import json
import os
import re
import subprocess

import tool_io

NOT_FOUND = 10
ORDERED = re.compile(r"^[0-9]{12}\.")


def run(argv, stdin_text="", cwd=None):
    """下層 stderr 原樣放行，不接來猜錯誤。"""
    try:
        result = subprocess.run(argv, input=stdin_text, stdout=subprocess.PIPE,
                                text=True, cwd=cwd)
    except OSError as error:
        tool_io.die("CommandMissing", "%s failed to start (must be on PATH): %s" % (argv[0], error))
    return result.returncode, result.stdout


def post(args, stdin_text=""):
    return run(["aos-post"] + args, stdin_text)


def init(box, die):
    if post(["init", box])[0] != 0:
        die("PostFailed", "cannot create mailbox %s" % box)


def take_all(box, die):
    if post(["take-all", box])[0] not in (0, NOT_FOUND):
        die("PostFailed", "cannot take letters from mailbox %s" % box)


def letter_key(name):
    """同 aos-post：有序信先、再依名字。"""
    return (0 if ORDERED.match(name) else 1, name)


def names(box):
    return sorted((n for n in os.listdir(os.path.join(box, "cur"))
                   if not n.startswith(".")), key=letter_key)


def done(box, name, die):
    if post(["done", box, name])[0] != 0:
        die("PostFailed", "cannot finish letter %s" % name)


def see(box, name, ctx, reply=False):
    code, out = post(["see", box, name])
    if code not in (0, 1):
        ctx.die("PostFailed", "aos-post see %s exited %d" % (name, code))
    try:
        letter = json.loads(out) if code == 0 else None
        if not isinstance(letter, dict) or "body" not in letter:
            raise ValueError("missing body")
        return letter
    except ValueError:
        ctx.warn("%s %s is broken; dropped" % ("reply" if reply else "letter", name))
        done(box, name, ctx.die)
        return None


def write_json(path, value, label, die):
    """同夾暫存再換名，不留半份表。"""
    try:
        with open(path + ".tmp", "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False)
            stream.write("\n")
        os.replace(path + ".tmp", path)
    except OSError as error:
        die("StateBad", "cannot write %s: %s" % (label, error))


def body_path(ctx, name):
    return os.path.join(ctx.stack, "bodies", name + ".json")


def save_body(ctx, name, body):
    path = body_path(ctx, name)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    except OSError as error:
        ctx.die("StateBad", "cannot create bodies/: %s" % error)
    write_json(path, body, "queued body %s" % name, ctx.die)


def restore_body(ctx, name, letter):
    try:
        with open(body_path(ctx, name), encoding="utf-8") as stream:
            letter["body"] = json.load(stream)
    except FileNotFoundError:
        pass  # 沒改過 body 的排隊信沒有另存檔。
    except (OSError, ValueError, UnicodeError) as error:
        ctx.die("StateBad", "cannot read queued body %s: %s" % (name, error))


def remove_body(ctx, name):
    try:
        os.unlink(body_path(ctx, name))
    except FileNotFoundError:
        pass
    except OSError as error:
        ctx.die("StateBad", "cannot remove queued body %s: %s" % (name, error))


def read_forwarded(path, die):
    try:
        with open(path, encoding="utf-8") as stream:
            rows = json.load(stream)
        if not isinstance(rows, dict) or any(
                not isinstance(row, dict) or not isinstance(row.get("letter"), str)
                or "reply_to" not in row
                or (row["reply_to"] is not None and not isinstance(row["reply_to"], str))
                for row in rows.values()):
            raise ValueError("invalid forwarding records")
        return rows
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as error:
        die("StateBad", "cannot read forwarded.json: %s" % error)


def write_forwarded(ctx):
    write_json(ctx.forwarded_path, ctx.forwarded, "forwarded.json", ctx.die)


def record_keys(ctx, name):
    return [key for key, row in ctx.forwarded.items()
            if key == name or row["letter"] == name]


def in_box(box, name):
    """這封信（有序轉普通時比尾名）是不是還躺在那個信箱裡。"""
    tail = name.split(".", 1)[1] if ORDERED.match(name) else name
    return any(os.path.exists(os.path.join(box, slot, candidate))
               for slot in ("new", "cur") for candidate in (name, tail))


def already_forwarded(ctx, name):
    return bool(record_keys(ctx, name)) or in_box(ctx.next_box, name)


def finish_forwarded(ctx, name):
    done(ctx.requests, name, ctx.die)
    remove_body(ctx, name)
    removed = [key for key in record_keys(ctx, name)
               if ctx.forwarded[key]["reply_to"] is None]
    for key in removed:
        del ctx.forwarded[key]
    if removed:
        write_forwarded(ctx)


def relay_replies(ctx, before_reply=None):
    """逐封代回前可插回呼；傳入（原信記錄、回信），回傳要寄的 body。"""
    init(ctx.replies, ctx.die)
    take_all(ctx.replies, ctx.die)
    for name in names(ctx.replies):
        letter = see(ctx.replies, name, ctx, reply=True)
        if letter is None:
            continue
        key = letter.get("in_reply_to")
        original = ctx.forwarded.get(key) if isinstance(key, str) else None
        if original is None:
            ctx.warn("reply %s has no forwarding record; dropped" % name)
        else:
            body = before_reply(original, letter) if before_reply else letter["body"]
            if original["reply_to"]:
                if not os.path.isdir(original["reply_to"]):
                    failed = True
                else:
                    failed = post(["send", "--in-reply-to", original["letter"], original["reply_to"]],
                                  json.dumps(body, ensure_ascii=False))[0] != 0
                if failed:
                    ctx.warn("reply %s could not be relayed; dropped" % name)
            del ctx.forwarded[key]
            write_forwarded(ctx)
        done(ctx.replies, name, ctx.die)


def forward(ctx, name, letter, box=None):
    """box＝hook 替這一封指定的下一站；沒給就寄站原本的下一站。"""
    if box and in_box(box, name):
        # 上一輪已寄進指定的站、原信還沒收就中斷：不再寄第二次。
        finish_forwarded(ctx, name)
        return None
    is_ordered = bool(ORDERED.match(name))
    tail = name.split(".", 1)[1] if is_ordered else name
    preserve = is_ordered and ctx.cfg.get("keep_ordered", False)
    reply_to = letter.get("reply_to")
    original_reply = os.path.abspath(os.path.join(ctx.requests, reply_to)) if reply_to else None
    relay = bool(original_reply and ctx.cfg.get("reply_via_me", False))
    args = ["send"]
    if original_reply:
        args += ["--reply-to", ctx.replies if relay else original_reply]
    if preserve:
        args += ["--ordered"]
    args += [box or ctx.next_box, tail]
    code, out = post(args, json.dumps(letter["body"], ensure_ascii=False))
    if code != 0:
        return "ForwardFailed", "aos-post send to the next mailbox exited %d (reason in its stderr)" % code
    if preserve or relay:
        ctx.forwarded[out.strip()] = {"letter": name, "reply_to": original_reply if relay else None,
                                     "sender": letter.get("sender")}
        write_forwarded(ctx)
    finish_forwarded(ctx, name)
    return None


def refuse(ctx, name, letter, code, msg):
    ctx.warn("letter %s refused: %s %s" % (name, code, msg))
    reply = {"applied": False, "error": {"code": code, "msg": msg}}
    rc, _ = post(["done", "--reply", ctx.requests, name], json.dumps(reply, ensure_ascii=False))
    if rc != 0:
        ctx.warn("letter %s: could not send the reply, letter dropped" % name)
        post(["done", ctx.requests, name])
