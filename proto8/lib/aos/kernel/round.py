# 通用 kernel 的骨架：讀設定、鎖收件箱、照五個口做完一輪。
import fcntl
import json
import os
from types import SimpleNamespace

import letters
import tool_io


class CfgBad(ValueError):
    """包只用這個例外回報自己的設定不對。"""


def load(pack, path):
    path = os.path.abspath(path)
    try:
        with open(path, encoding="utf-8") as stream:
            text = stream.read()
    except FileNotFoundError:
        tool_io.die("CfgMissing", "kernel.json not found: %s" % path)
    except (OSError, UnicodeError) as error:
        tool_io.die("CfgBad", "cannot read kernel.json: %s" % error)
    code, out = letters.run(["aos-directive", "--file", path], text, cwd=os.path.dirname(path))
    try:
        if code != 0:
            raise ValueError("aos-directive exited %d" % code)
        cfg = json.loads(out)
        if not isinstance(cfg, dict):
            raise ValueError("kernel.json must be an object")
        for key in ("next", "count_daemon"):
            if key in cfg:
                if not isinstance(cfg[key], str) or not cfg[key]:
                    raise ValueError("%s must be a non-empty path string" % key)
                cfg[key] = os.path.abspath(os.path.join(os.path.dirname(path), cfg[key]))
        pack.load(cfg, os.path.dirname(path))
    except (ValueError, TypeError) as error:
        tool_io.die("CfgBad", str(error))
    return cfg


def run(pack, cfg_path, name="kernel"):
    """每次執行做一輪；包負責信的規則，骨架只管順序與判決。"""
    cfg = load(pack, cfg_path)
    stack = os.environ.get("AOS_STACK")
    if not stack:
        tool_io.die("StackMissing", "AOS_STACK is not set")
    stack = os.path.abspath(stack)
    requests = os.path.join(stack, "requests")
    ctx = SimpleNamespace(cfg=cfg, stack=stack, requests=requests, name=name,
                          die=tool_io.die, warn=tool_io.warn)
    letters.init(requests, ctx.die)
    try:
        lock = open(os.path.join(requests, ".flock"), "a")
    except OSError as error:
        ctx.die("LockFailed", "cannot open requests/.flock: %s" % error)
    with lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            ctx.die("LockFailed", "cannot lock requests/.flock: %s" % error)
        pack.collect(ctx)
        incoming = pack.check(ctx)
        names = pack.order(ctx, incoming)
        queued = []
        # 逐封判決集中在這一段，之後的 hook 可在判之前、之後插入。
        for letter_name in names:
            letter = incoming[letter_name]
            verdict, detail = pack.admit(ctx, letter_name, letter)
            if verdict == "queue":
                queued.append(detail)
            elif verdict == "refuse":
                pack.refuse(ctx, letter_name, letter, *detail)
            elif verdict == "pass":
                failure = pack.dispatch(ctx, letter_name, letter, detail)
                if failure is not None:
                    pack.refuse(ctx, letter_name, letter, *failure)
        pack.finish(ctx, queued)
    return 0
