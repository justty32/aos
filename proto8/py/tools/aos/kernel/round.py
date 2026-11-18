# 通用 kernel 的骨架：讀設定、鎖收件箱，串起五個口與三個 hook 時機。
import fcntl
import json
import os
from types import SimpleNamespace

import letters
import hold
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
    # 包有 held 才收 after_verdict hook 的「先留著」（hold）：留著的信每輪交給 held 看要不要先拒（例如寄件人的期限）。
    ctx.can_hold = hasattr(pack, "held")
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
            ctx.held = []
            held_before = hold.view(ctx) if ctx.can_hold else {}
            for letter_name in names:
                letter = incoming[letter_name]
                was_queued = letter_name in ctx.previous
                was_held = letter_name in held_before
                waited = was_queued or was_held
                changed_body = decided = False
                if waited:
                    letters.restore_body(ctx, letter_name, letter)
                    said = hold.decision(ctx, letter_name) if ctx.can_hold else None
                    # 有人表態拒＝照它拒；留著的信另外每輪問包要不要先拒（寄件人的期限）。
                    failure = said[1] if said and said[0] == "refuse" else (
                        pack.held(ctx, letter_name, letter) if was_held else None)
                    if failure is not None:
                        pack.refuse(ctx, letter_name, letter, *failure)
                        letters.remove_body(ctx, letter_name)
                        continue
                    if was_held and said is None:
                        ctx.held.append(held_before[letter_name])  # 還沒人表態：繼續留著，不重判、不再問 hook。
                        continue
                    decided = said is not None  # 表態 pass：這輪重判一次，hook 再回 hold 不算數。
                else:
                    result = hooks.before_verdict(ctx, letter_name, letter)
                    if result["blocked"]:
                        pack.refuse(ctx, letter_name, letter, *hooks.rejected(result))
                        letters.remove_body(ctx, letter_name)
                        continue
                    changed_body = "body" in result["changed"]
                verdict, detail = pack.admit(ctx, letter_name, letter)
                if not was_queued or verdict != "queue":
                    verdict, detail = hooks.after_verdict(ctx, letter_name, letter, verdict, detail, decided)
                if verdict in ("queue", "hold"):
                    if changed_body:
                        letters.save_body(ctx, letter_name, letter["body"])
                    elif not waited:
                        letters.remove_body(ctx, letter_name)
                    if verdict == "queue":
                        ctx.queued.append(detail)
                    else:
                        ctx.held.append(hold.row(ctx, letter_name, letter))
                elif verdict == "refuse":
                    pack.refuse(ctx, letter_name, letter, *detail)
                    letters.remove_body(ctx, letter_name)
                elif verdict == "pass":
                    failure = pack.dispatch(ctx, letter_name, letter, detail)
                    if failure is not None:
                        pack.refuse(ctx, letter_name, letter, *failure)
                    letters.remove_body(ctx, letter_name)
            pack.finish(ctx, ctx.queued)
            if ctx.can_hold:
                hold.finish(ctx)
        except hook_run.HookFailed as error:
            ctx.die("HookFailed", str(error))
    return 0
