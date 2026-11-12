# aos_eca/hook.py - 這支跑的 hook（before_queue、tool_added；fire 把 hook 停下換成 Fail）。
import json
import os
import subprocess

import aos_flags

from .common import NAME, Fail, hooks, post, write_atomic


# ---- hook（lib/agent/hooks.py；圖紙 thinking/2026-11/10/self-family/hook § 6 eca 縮水版）----

def fire(event, data, template, stack):
    """跑 hook；hook 停下＝這支的錯（HookFailed／HooksBad）。"""
    try:
        return hooks.fire(event, data, template, stack, warn=lambda line: aos_flags.warn(NAME, line))
    except (hooks.HookFailed, hooks.HooksBad) as e:
        raise Fail(type(e).__name__, e)


def before_queue(stack, box, sig, body, template):
    """好信交出去之前跑 before_queue：回（可能改過 content 的）body；被攔下＝aos-post done 收掉、mailbox_warning 一行、回 None。"""
    r = fire("before_queue", {"letter": sig, "content": body["content"]}, template, stack)
    if r["blocked"]:
        post(["done", box, sig])
        write_atomic(os.path.join(stack, "mailbox_warning.txt"), "letter %s dropped by hook %s\n" % (sig, r["hook"]))
        return None
    return dict(body, content=r["data"]["content"])


def tool_added(cfg, template, stack):
    """tool_added：這隻實際生效的登記檔（cfg["registry"]）的名單比上次多出來的，一個名字一次；沒這種 hook＝不叫 aos-tools、刪 seen 檔。"""
    try:
        on = hooks.has("tool_added", template, stack)
    except hooks.HooksBad as e:
        raise Fail("HooksBad", e)
    listed = []
    if on and cfg.get("registry"):
        try:
            r = subprocess.run(["aos-tools", "--file", cfg["registry"], "ls", "--json"], stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, text=True)          # stderr 不吞：aos-tools 自己說哪裡壞
        except OSError as e:
            raise Fail("ToolsBad", "aos-tools cannot start: %s" % e)
        if r.returncode != 0:
            raise Fail("ToolsBad", "aos-tools ls exited %d" % r.returncode)
        try:
            listed = [(t["name"], os.path.abspath(t["path"]) if t.get("path") else None) for t in json.loads(r.stdout)]
        except (ValueError, TypeError, KeyError) as e:
            raise Fail("ToolsBad", "aos-tools ls --json printed something else: %s" % e)
    try:
        added = hooks.tools_added(stack, listed, on)
    except OSError as e:
        raise Fail("WriteFailed", "cannot write %s: %s" % (os.path.join(stack, hooks.SEEN), e))
    for name, where in added:
        fire("tool_added", {"name": name, "path": where}, template, stack)
