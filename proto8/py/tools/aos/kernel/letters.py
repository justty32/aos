# 包 aos-post 的信件本身：認領、看信、收信、拒信與排隊 body；轉寄、代回與轉寄對照表在 forwarding.py。
import json
import os
import re
import subprocess

from aos import tool_io

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


def refuse(ctx, name, letter, code, msg, extra=None):
    ctx.warn("letter %s refused: %s %s" % (name, code, msg))
    reply = {"applied": False, "error": dict(extra or {}, code=code, msg=msg)}
    rc, _ = post(["done", "--reply", ctx.requests, name], json.dumps(reply, ensure_ascii=False))
    if rc != 0:
        ctx.warn("letter %s: could not send the reply, letter dropped" % name)
        post(["done", ctx.requests, name])
