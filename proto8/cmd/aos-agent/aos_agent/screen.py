# aos_agent/screen.py - 開啟、關閉與追蹤 agent 的畫面子介面。
from .common import Fail, parse, target
from .decl import pass_err, run_entry, screen_entry


def cmd(action):
    def run(argv):
        opts, rest = parse(argv, {"--target": "target"}, {"--detach": "detach"} if action == "open" else None)
        if rest:
            raise Fail("ArgumentsBad", "%s takes no positional arguments: %s (pick the target with --target)" % (action, rest[0]))
        a = target(opts)
        _, entry = screen_entry(a)
        args = [action] + (["--detach"] if opts.get("detach") else [])
        attach = action == "open" and not opts.get("detach")
        rc, err = run_entry(a, entry, args, capture_err=not attach)
        if attach and rc != 0:
            raise Fail("ScreenBad", "the screen entry %s of %s exited %d" % (entry, a.name, rc))
        pass_err(rc, err)
    return run
