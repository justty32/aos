# aos/apps/eca/hook.py - 這支的 hook 遙控器（open：hook 停下換成 Fail）與 before_queue、tool_added 兩個點的這支這邊。
import json
import os
import subprocess

from aos import flags as aos_flags
from aos.agentlib import agent_hooks

from .common import NAME, Fail


# ---- hook（py/aos/agentlib/agent_hooks.py 的遙控器；圖紙 thinking/2026-11/10/self-family/hook § 6 eca 縮水版；
#      11-20 hook 介面第 2 刀：一輪開一次，一路傳下去）----

def _fail(code, sentence):
    raise Fail(code, sentence)


def open_hooks(template, stack):
    """這一輪的 hook 遙控器：hook 停下（HookFailed／HooksBad）＝丟 Fail；不能攔的點的 hook 失敗＝一行 warning。"""
    return agent_hooks.open(template, stack, fail=_fail, warn=lambda line: aos_flags.warn(NAME, line))


def before_queue(hooks, box, sig, body):
    """好信交出去之前跑 before_queue：回（可能改過 content 的）body；被攔下＝記 dropped、aos-post done 收掉、mailbox_warning 一行、回 None。"""
    content = hooks.take_letter(box, sig, body["content"])
    return None if content is None else dict(body, content=content)


def tool_added(hooks, cfg):
    """tool_added：這隻實際生效的登記檔（cfg["registry"]）的名單比上次多出來的，一個名字一次；沒這種 hook＝不叫 aos-tools、刪 seen 檔。"""
    def listed():
        if not cfg.get("registry"):
            return []
        try:
            r = subprocess.run(["aos-tools", "--file", cfg["registry"], "ls", "--json"], stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, text=True)          # stderr 不吞：aos-tools 自己說哪裡壞
        except OSError as e:
            raise Fail("ToolsBad", "aos-tools cannot start: %s" % e)
        if r.returncode != 0:
            raise Fail("ToolsBad", "aos-tools ls exited %d" % r.returncode)
        try:
            return [(t["name"], os.path.abspath(t["path"]) if t.get("path") else None) for t in json.loads(r.stdout)]
        except (ValueError, TypeError, KeyError) as e:
            raise Fail("ToolsBad", "aos-tools ls --json printed something else: %s" % e)
    hooks.announce_tools(listed)
