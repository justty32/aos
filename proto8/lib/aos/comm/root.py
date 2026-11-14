"""root - 布告欄寫在哪一份 stack：自己的根（05 A2：工具小格 <root>/tools/<名> 認回 <root>）、使用者專區。"""
import os

from . import Fail


def own_root(flag=None, env=None):
    """--stack 給了就照字面用；否則 $AOS_STACK：形如 <root>/tools/<名> 且 <root>/mailbox 在＝<root>，不然就是它本身；
    兩個都沒有＝StackMissing。不叫 aos-agent ctl who（批 1 隊長定）。回絕對路徑。"""
    env = os.environ if env is None else env
    if flag:
        return os.path.abspath(flag)
    s = env.get("AOS_STACK", "")
    if not s:
        raise Fail("StackMissing", "no --stack and no AOS_STACK; say whose board this is with --stack STACK")
    s = os.path.abspath(s)
    tools = os.path.dirname(s)
    if os.path.basename(tools) == "tools":
        root = os.path.dirname(tools)
        if os.path.isdir(os.path.join(root, "mailbox")):
            return root
    return s


def user_zone(env=None):
    """使用者專區：$AOS_USER_ZONE ＞ ~/.aos/user（跟 aos-user、user_zone_guard 同一套）。"""
    env = os.environ if env is None else env
    return os.path.abspath(os.path.expanduser(env.get("AOS_USER_ZONE") or "~/.aos/user"))
