# 通用 kernel 的骨架：讀設定、鎖收件箱，串起五個口與三個 hook 時機。
import fcntl
import json
import os
from types import SimpleNamespace

import letters
import hooks
import hook_run
import tool_io


class CfgBad(ValueError):
    """包只用這個例外回報自己的設定不對。"""


def load(pack, path):
    path = os.path.abspath(path)
    if hasattr(pack, "read"):
        # 包自己讀設定（問腦那包：每組指示詞用到才解，不能整份先過 aos-directive）；hooks 也由它驗。
        return pack.read(path)
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
        cfg["hooks"] = hooks.load(cfg.get("hooks", {}), path)
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
                          die=tool_io.die, warn=tool_io.warn, route={})
    # 包有 check_next 才收 after_verdict hook 替單封信指定的下一站；指定的路徑記在 ctx.route[信名]。
    ctx.check_next = (lambda box: pack.check_next(ctx, box)) if hasattr(pack, "check_next") else None
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
        try:
            ctx.previous = {}
            pack.collect(ctx, before_reply=lambda original, reply: hooks.before_reply(ctx, original, reply))
            incoming = pack.check(ctx)
            names = pack.order(ctx, incoming)
            ctx.queued = []
            for letter_name in names:
                letter = incoming[letter_name]
                was_queued = letter_name in ctx.previous
                changed_body = False
                if was_queued:
                    letters.restore_body(ctx, letter_name, letter)
                else:
                    result = hooks.before_verdict(ctx, letter_name, letter)
                    if result["blocked"]:
                        pack.refuse(ctx, letter_name, letter, *hooks.rejected(result))
                        letters.remove_body(ctx, letter_name)
                        continue
                    changed_body = "body" in result["changed"]
                verdict, detail = pack.admit(ctx, letter_name, letter)
                if not was_queued or verdict != "queue":
                    verdict, detail = hooks.after_verdict(ctx, letter_name, letter, verdict, detail)
                if verdict == "queue":
                    if changed_body:
                        letters.save_body(ctx, letter_name, letter["body"])
                    elif not was_queued:
                        letters.remove_body(ctx, letter_name)
                    ctx.queued.append(detail)
                elif verdict == "refuse":
                    pack.refuse(ctx, letter_name, letter, *detail)
                    letters.remove_body(ctx, letter_name)
                elif verdict == "pass":
                    failure = pack.dispatch(ctx, letter_name, letter, detail)
                    if failure is not None:
                        pack.refuse(ctx, letter_name, letter, *failure)
                    letters.remove_body(ctx, letter_name)
            pack.finish(ctx, ctx.queued)
        except hook_run.HookFailed as error:
            ctx.die("HookFailed", str(error))
    return 0
