# aos_agent/ctl/who.py - 由 stack 路徑查詢所屬 agent。
import json
import os
from ..common import Fail, daemon_path, parse, table, under


def cmd(argv):
    """ctl who（11-05 feat-proto 件 1 代定 1）：S（--stack ＞ $AOS_STACK）落在表上哪一隻的 stack 裡——那列的 stack 是 S 本身或 S 的上層
    （工具的小格 <agent stack>/tools/<名>/ 也認得）；好幾列都包住 S＝取最深的那列。只查 daemon 表（C-52 經機制看上層），不從 S 往上爬猜。"""
    opts, rest = parse(argv, {"--stack": "stack"}, {"--json": "json"})
    if rest:
        raise Fail("ArgumentsBad", "who takes no positional arguments: %s (give the path with --stack S)" % rest[0])
    s = opts.get("stack") or os.environ.get("AOS_STACK", "")
    if not s:
        raise Fail("StackMissing", "no --stack and no AOS_STACK; give the stack path to look up")
    hit = None
    for n, r in table(quiet=True).items():
        st = r.get("stack")
        if isinstance(st, str) and st and under(s, st):
            if hit is None or len(os.path.realpath(st)) > len(os.path.realpath(hit[1]["stack"])):
                hit = (n, r)
    if hit is None:
        raise Fail("InstanceMissing", "%s is not inside the stack of any proc on the daemon table %s" % (os.path.abspath(s), daemon_path()))
    n, r = hit
    if opts.get("json"):
        print(json.dumps({"name": n, "stack": r.get("stack"), "ws": r.get("ws"), "def": r.get("def")}, ensure_ascii=False))
    else:
        print(n)
