"""daemon-cli.md：aos-daemon boot／halt／ls／scale／kill。

家一律 --target → AOS_DAEMON_HOME → 目前資料夾。ls 只偷看檔案、不放單（daemon 沒在跑也看得到）；
scale／kill 放單、等回音（10 秒）。退出碼：0 成功；1 讀驗／I/O／daemon 回錯；2 用法錯。
"""
import argparse
import json
import os
import sys
import time

import aos_client
import aos_daemon
import aos_daemon_pools as pools
import aos_daemon_rpc
import aos_home

TARGET_HELP = "daemon 家（省略＝AOS_DAEMON_HOME，再沒有就目前資料夾）"
WAIT_MS = 10000
COLUMNS = ("running", "busy", "pending", "dead", "failed", "killing", "draining")  # restarting 併進 running 那格


class CliError(aos_home.HomeError):
    pass


def _peek(path):
    try:
        value = aos_home.read_json(path)
    except aos_home.HomeError:
        return None
    return value if isinstance(value, dict) else None


def _kid_files(home, name):
    """{號: kids 檔內容}；O(這池的檔數)。"""
    found = {}
    kid_dir = pools.pool_dir(home, name) / "kids"
    if kid_dir.is_dir():
        for leaf in kid_dir.iterdir():
            stem = leaf.name[:-5] if leaf.name.endswith(".json") else ""
            if pools.NAME_RE.fullmatch(stem):
                record = _peek(leaf)
                if record is not None:
                    found[int(stem)] = record
    return found


def _busy(decl, i, record, want):
    if not want or decl is None or decl.get("home") is None or record.get("state") not in ("running", "killing"):
        return None
    return aos_daemon_rpc.is_busy(decl["home"].replace("{name}", str(i), 1))


def _pool_view(home, name, want_busy):
    decl, summary = _peek(pools.pool_dir(home, name) / "pool.json"), _peek(pools.pool_dir(home, name) / "summary.json")
    if summary is None and decl is None:
        return None
    view = dict(summary) if summary is not None else {
        "pool": name, "owner": decl.get("owner"), "count": decl.get("count"), "ver": decl.get("ver")}
    view["busy"] = None
    if want_busy and decl is not None and decl.get("home") is not None:
        view["busy"] = sum(bool(_busy(decl, i, r, True)) for i, r in _kid_files(home, name).items()
                           if r.get("state") == "running")
    return view, decl


def _header(home):
    alive = aos_daemon.is_alive(home)
    pid = aos_daemon.read_state(home).get("pid") if alive else None
    return {"running": alive, "pid": pid}


def _clock(epoch):
    return time.strftime("%H:%M:%S", time.localtime(epoch)) if isinstance(epoch, (int, float)) else "-"


def _table(rows):
    """一列是 [(標籤, 值)...]；同一欄的值補到一樣寬。"""
    widths = {}
    for row in rows:
        for k, (label, value) in enumerate(row):
            widths[k] = max(widths.get(k, 0), len(str(value)))
    return ["  ".join(("%s %s" % (label, str(value).ljust(widths[k])) if label else str(value).ljust(widths[k]))
                      for k, (label, value) in enumerate(row)).rstrip() for row in rows]


def _running_text(summary):
    """restarting 是 running 的子集：印成「2（含 restarting 1）」，0 就只印「2」（使用者代裁，09-24）。"""
    running, restarting = summary.get("running"), summary.get("restarting")
    text = "-" if running is None else str(running)
    return text + ("（含 restarting %s）" % restarting if restarting else "")


def _summary_row(view):
    row = [("", view["pool"]), ("owner", view.get("owner")), ("want", view.get("count"))]
    for key in COLUMNS:
        value = _running_text(view) if key == "running" else view.get(key)
        row.append((key, "-" if value is None else value))
    return row


def ls(home, pool=None, as_json=False, busy=True):
    home = str(home)
    head = _header(home)
    if pool is None:
        views = {}
        root = pools.pools_dir(home)
        for path in sorted(root.iterdir()) if root.is_dir() else ():
            got = _pool_view(home, path.name, busy) if path.is_dir() else None
            if got is not None:
                views[path.name] = got[0]
        if as_json:
            print(json.dumps({"daemon": head, "pools": views}, ensure_ascii=False))
            return 0
        total = sum(sum(v.get(k) or 0 for k in ("running", "pending", "dead", "failed", "killing", "draining"))
                    for v in views.values())
        state = ("daemon running  pid %s" % head["pid"]) if head["running"] else "daemon not running（以下是最後的摘要）"
        print("%s  pools %d  children %d" % (state, len(views), total))
        for line in _table([_summary_row(v) for v in views.values()]):
            print(line)
        return 0
    if not pools.valid_pool_name(pool):
        raise CliError("FieldTypeMismatch", "池名不合法：%s" % pool)
    got = _pool_view(home, pool, busy)
    if got is None:
        raise CliError("NotFound", "沒有這個池：%s" % pool)
    view, decl = got
    files = _kid_files(home, pool)
    wanted = pools.members(decl["count"], decl.get("skip", [])) if decl is not None else []
    children = {}
    for i in wanted:
        record = dict(files.get(i) or {"state": "pending"})
        record["busy"] = _busy(decl, i, record, busy)
        children[str(i)] = record
    for i in sorted(set(files) - set(wanted)):
        record = dict(files[i])
        record["busy"] = _busy(decl, i, record, busy)
        record["draining"] = True
        children[str(i)] = record
    if as_json:
        print(json.dumps({"daemon": head, "pool": pool, "summary": view, "children": children},
                         ensure_ascii=False))
        return 0
    print("daemon running  pid %s" % head["pid"] if head["running"] else "daemon not running（以下是最後的摘要）")
    print(_table([_summary_row(view)])[0])
    rows = []
    for i, r in children.items():
        state = "draining" if r.get("draining") else r.get("state")
        if state == "pending" and "gen" not in r:
            rows.append([("", i), ("", state), ("", "-")])
            continue
        busy_text = {True: "busy", False: "idle", None: "-"}[r.get("busy")]
        row = [("", i), ("", state), ("pid", r.get("pid") if r.get("pid") is not None else "-"),
               ("gen", r.get("gen")), ("", busy_text), ("exits", r.get("exits")), ("streak", r.get("streak"))]
        if state in ("dead", "failed"):
            row += [("next", _clock(r.get("next_at"))), ("last_exit", r.get("last_exit"))]
        elif r.get("since") is not None:
            row.append(("since", _clock(r.get("since"))))
        rows.append(row)
    for line in _table(rows):
        print(line)
    return 0


def _call(home, method, params):
    if not aos_daemon.is_alive(home):
        raise CliError("NotRunning", "daemon 沒在跑，不放單（先 aos-daemon boot）")
    try:
        response = aos_client.call(home, method, params, client="cli", timeout_ms=WAIT_MS, poll_ms=20)
    except aos_client.ClientError as exc:
        if exc.code == "ReadFailed":
            raise CliError("Timeout", "等回音逾時（%d 秒）；單已放出、未撤回" % (WAIT_MS // 1000)) from exc
        raise
    error = response.get("error")
    if error is not None:
        data = error.get("data") or {}
        raise CliError(data.get("code") or str(error.get("code")), error.get("message"))
    return response["result"]


def scale(home, pool, count, skip=None, inst=None, cpu_home=None, force=False):
    home = str(home)
    old = _peek(pools.pool_dir(home, pool) / "pool.json")
    owner = "cli"
    if old is not None:
        owner = old.get("owner")
        if owner != "cli" and not force:
            raise CliError("Owned", "池 %s 是 %s 的；請改用 aos-kernel cpu add／rm（救急才加 --force）" % (pool, owner))
    params = {"pool": pool, "owner": owner, "count": count,
              "skip": skip if skip is not None else (old.get("skip", []) if old else [])}
    if inst is not None:
        params["target"] = os.path.abspath(inst)
    if cpu_home is not None:
        params["home"] = os.path.abspath(cpu_home)
    result = _call(home, "scale", params)
    print("pool %s count %d -> %d (ver %d)" % (pool, old.get("count", 0) if old else 0,
                                                result["count"], result["ver"]))
    return 0


def kill(home, pool, names, every):
    params = {"pool": pool, "all": True} if every else {"pool": pool, "names": names}
    result = _call(str(home), "kill", params)
    if result["killed"]:
        print("killed %s" % " ".join(result["killed"]))
    if result["skipped"]:
        print("skipped %s" % " ".join("%s (%s)" % item for item in result["skipped"].items()))
    if not result["killed"] and not result["skipped"]:
        print("killed -")
    return 0


def _skip(text):
    items = [x for x in text.split(",") if x != ""]
    if not all(pools.NAME_RE.fullmatch(x) for x in items) or len(set(items)) != len(items):
        raise argparse.ArgumentTypeError("--skip 要逗號分隔、不重複的非負整數")
    return sorted(int(x) for x in items)


def _count(text):
    if not pools.NAME_RE.fullmatch(text) or int(text) > pools.MAX_COUNT:
        raise argparse.ArgumentTypeError("--count 必須是 0～%d 的整數" % pools.MAX_COUNT)
    return int(text)


def _pool(text):
    if not pools.valid_pool_name(text):
        raise argparse.ArgumentTypeError("池名 1～64 bytes、只用 A-Z a-z 0-9 _ . -")
    return text


def _parser():
    parser = argparse.ArgumentParser(prog="aos-daemon", description=(
        "daemon：boot 跑起來（前景程式）、halt 送停機通知並等它退出、ls 看池、scale 改池的顆數、kill 砍掉重來"))
    commands = parser.add_subparsers(dest="command", metavar="{boot,halt,ls,scale,kill}")
    subs = {}
    def sub(name, text):
        p = subs[name] = commands.add_parser(name, help=text, description=text)
        p.add_argument("--target", metavar="D", help=TARGET_HELP)
        return p
    sub("boot", "跑 daemon（前景程式，自己放背景）；會照 pool.json 把孩子拉回來")
    p = sub("halt", "停止 daemon 並等待退出（pool.json 留著，下次 boot 拉回來）")
    p.add_argument("--wait-ms", type=int, default=30000, metavar="N", help="等退出的上限，非負毫秒（預設 30000）")
    p = sub("ls", "看池（偷看檔案、不放單；daemon 沒在跑也看得到最後的摘要）")
    p.add_argument("--pool", type=_pool, metavar="P", help="只看這池，一顆一行")
    p.add_argument("--json", action="store_true", help="印成一份 JSON")
    p.add_argument("--no-busy", action="store_true", help="不逐顆偷看忙不忙（上萬顆時省一點）")
    p = sub("scale", "宣告池 P 要幾顆（池不在就建，owner 記成 cli）")
    p.add_argument("--pool", type=_pool, required=True, metavar="P")
    p.add_argument("--count", type=_count, required=True, metavar="N")
    p.add_argument("--skip", type=_skip, metavar="I,J", help="不要的號（省略＝沿用現在的）")
    p.add_argument("--inst", metavar="PATTERN", help="第 i 號的 aos-exec 目標樣板，含一個 {name}（池不在時必填）")
    p.add_argument("--home", metavar="PATTERN", help="第 i 號 cpu 的家樣板，含一個 {name}（ls 數忙用）")
    p.add_argument("--force", action="store_true", help="改別人（例如 kernel）的池；只給救急用")
    p = sub("kill", "把某幾顆砍掉重來（宣告不變，砍完會再拉）")
    p.add_argument("--pool", type=_pool, required=True, metavar="P")
    p.add_argument("names", nargs="*", metavar="NAME")
    p.add_argument("--all", action="store_true", help="整池每顆都重來")
    return parser, subs


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    parser, subs = _parser()
    try:
        options = parser.parse_args(args)
        if options.command is None:
            parser.print_usage(sys.stderr)
            parser.exit(2, "aos-daemon: error: 要給子命令：aos-daemon boot [--target D]／aos-daemon halt [--target D]"
                           "／ls／scale／kill\n")
        if options.target == "":
            subs[options.command].error("--target 不可為空")
        if options.command == "halt" and options.wait_ms < 0:
            subs["halt"].error("--wait-ms 必須是非負整數")
        if options.command == "kill":
            if options.all == bool(options.names):
                subs["kill"].error("NAME… 與 --all 恰好給一個")
            if not all(pools.NAME_RE.fullmatch(n) for n in options.names):
                subs["kill"].error("NAME 是十進位號碼（不帶前導 0）")
        if options.command == "scale":
            for key in ("inst", "home"):
                value = getattr(options, key)
                if value is not None and value.count("{name}") != 1:
                    subs["scale"].error("--%s 要恰好含一個 {name}" % key)
    except SystemExit as exc:
        return exc.code
    home, source = aos_home.resolve_target(options.target, "AOS_DAEMON_HOME")
    note = aos_home.target_note("D", home, source, "AOS_DAEMON_HOME")
    try:
        if options.command == "halt":
            return aos_daemon.stop(str(home), options.wait_ms)
        if options.command == "boot":
            return aos_daemon.run(str(home))
        if options.command == "ls":
            return ls(home, options.pool, options.json, not options.no_busy)
        if options.command == "scale":
            old = _peek(pools.pool_dir(home, options.pool) / "pool.json")
            if old is None and options.count > 0 and options.inst is None:
                subs["scale"].print_usage(sys.stderr)
                sys.stderr.write("aos-daemon scale: error: 池 %s 不在，要給 --inst\n" % options.pool)
                return 2
            return scale(home, options.pool, options.count, options.skip, options.inst, options.home, options.force)
        return kill(home, options.pool, options.names, options.all)
    except aos_home.HomeError as exc:
        pools.log(exc.code, exc.msg + note)
    except (OSError, ValueError, TypeError) as exc:
        pools.log("IOFailed", str(exc) + note)
    return 1
