# aos_agent/ctl/rm.py - 拔掉 agent 並保護不能刪除的 stack 路徑。
import os
import shutil
from ..common import Fail, ctl_wait, daemon_path, find, is_kernel, need_table, parse, row_named, table
from ..decl import close_screen_if_any


def cmd(argv):
    _, rest = parse(argv)
    if len(rest) != 1:
        raise Fail("ArgumentsBad", "rm needs the name spelled out: aos-agent ctl rm NAME (no --target / AOS_AGENT: it deletes the stack, which cannot be undone)")
    need_table()
    a = find(rest[0])
    close_screen_if_any(a)
    direct = is_kernel(a)
    ctl_wait("rm", {"procs_removed": [a.name]}, lambda _: row_named(a.name) is None, "the daemon has not removed %s yet" % a.name, "CtlRejected", direct)
    others = [r.get("stack") for r in table(quiet=True).values()]   # 表上別隻還在用的 stack（add --stack 撞到別隻的）
    keep = covers(a.stack, [a.row.get("ws"), a.row.get("def"), daemon_path(), os.getcwd(), os.path.expanduser("~")] + others)
    if keep:                                          # 11-04 夜邊緣實測：add --stack . 之後 rm 會連工作區一起刪；stack 蓋住這些的不刪
        print("removed %s; stack %s kept (it is %s or above it)" % (a.name, a.stack, keep))
        return
    shutil.rmtree(a.stack, ignore_errors=True)        # 不封存（使用者 11-02 晚）
    print("removed %s (deleted stack %s)" % (a.name, a.stack))


def covers(stack, paths):
    """stack 是不是 paths 裡某一個、或在它上層（rm 不能刪的）；回那一個或 None。"""
    s = os.path.realpath(stack)
    for p in paths:
        if isinstance(p, str) and p:
            r = os.path.realpath(p)
            if r == s or r.startswith(s.rstrip("/") + "/"):
                return p
    return None
