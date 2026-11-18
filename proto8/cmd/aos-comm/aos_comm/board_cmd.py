# aos_comm/board_cmd.py - aos-comm board 的五個動作（set、clear、wait、show、ls）：解旗標、找誰的布告欄、叫 py/aos/comm（aos.comm）讀寫、印一行一項或 --json。
# 圖紙：proto8/thinking/2026-11/14/board-1114/ 02 §2、§5.2；05 A2、A7、A13、A14。讀寫與四步全在 comm.board，這裡不重算。
import json
import os

from aos import flags as aos_flags
from aos.comm import Fail, board, root, times, walk

from . import procs
from .common import CTX, parse

ONLY = ("dnd", "away", "waiting", "waiting-user")

HELP = """aos-comm board - my board (what I am doing, whether to disturb me, who I wait for) and the boards of others

usage: aos-comm [-s STACK] [-d DAEMON] board ACTION [FLAGS...] [ARGS...]
       aos-comm board ACTION --help

actions:
  set MODE [TEXT]    replace my whole board (waiting_on stays); MODE = here, busy, dnd or away
  clear              take my board down (mode here, no text, no waiting)
  wait WHO WHAT      add one "I wait for WHO: WHAT" line; wait --done WHO removes WHO's lines
  show [NAME|user|me]  read a board (default: mine), with the daemon's phase and busy
  ls                 one line per proc on the daemon table (--deep: also the tables below)

The board is STACK/board.json (format board/1; the user's is ~/.aos/user/board.json).
more: proto8/cmd/aos-comm/README.md"""

HELPS = {
    "set": """aos-comm board set - replace my whole board

usage: aos-comm board set MODE [TEXT...] [--doing S] [--back WHEN] [--back-text S] [--for WHEN]
                          [--accept LEVEL] [--allow-from N,N...] [--wake] [--deputy NAME]
                          [--clear-on-start] [--by self|auto|user] [-j]

MODE: here (in), busy (in, answers slowly), dnd (do not disturb: only urgent letters notify me),
away (not here / asleep). Fields not given are cleared; waiting_on is kept.
WHEN is a duration from now (30m, 8h, 2d) or an ISO 8601 time with a zone.
--for WHEN sets expires_at; without it dnd expires in 2h and away in 12h (others: 24h after posting).
--back WHEN sets back_at. --wake = urgent letters may wake me (wake_on_urgent).
Prints the board written (key: value lines; -j = one JSON object).""",
    "clear": """aos-comm board clear - take my board down

usage: aos-comm board clear [--by self|auto|user] [-j]

Writes mode here with no text and no waiting lines (keys this version does not know stay).""",
    "wait": """aos-comm board wait - add or remove a waiting line on my board

usage: aos-comm board wait WHO WHAT... [--ref LETTER] [--level urgent|normal|low] [--by B] [-j]
       aos-comm board wait --done WHO [-j]

WHO is a proc name or user. At most 20 lines. --done removes every line for WHO;
nothing to remove = no output, exit 10.""",
    "show": """aos-comm board show - read a board

usage: aos-comm [-d DAEMON] board show [NAME | user | me] [-j]

NAME's stack comes from aos-agent ctl where NAME; user = ~/.aos/user/board.json ($AOS_USER_ZONE);
me or nothing = mine. The board is read as format board/1 says: unreadable = no board;
a time over 5 minutes in the future counts as now (clock_odd); past expires_at, or 24h after
updated_at with no expires_at = stale (text shown, mode counts as here, waiting lines do not count);
phase sleeping or stopped on the daemon table = asleep (mode counts as away); back_at passed = overdue.
-j = one JSON object {who, stack, board (null = none), mode, posted, stale, clock_odd, overdue,
asleep, waiting_on, live ({phase, busy} or null)}. No board is not an error (exit 0).""",
    "ls": """aos-comm board ls - one line per proc with its board

usage: aos-comm [-d DAEMON] board ls [--deep] [--only dnd|away|waiting|waiting-user] [-j]

Lines: NAME TAB MODE TAB DOING TAB WAITING FOR TAB BACK (- = none); MODE notes (stale),
(asleep), (no board); the last line counts. --deep also lists the tables of procs that are
daemons themselves (breadth first, at most 5 levels and 500 procs, then "truncated").
-j = one JSON object {rows, count, truncated, skipped}.""",
}


def _when(text, what, now):
    """30m／8h／2d（從現在起）或 ISO 8601 時間 → 寫進檔的時間字串。"""
    try:
        return times.fmt(now + times.duration(text, what))
    except Fail:
        return times.time_arg(text, what + " (a duration like 30m, 8h, 2d, or an ISO 8601 time)")


def _words(words):
    """位置參數後的 -- 會原樣留在 rest（aos_flags）；TEXT／WHAT 開頭那個 -- 只是分隔、不算字。"""
    return words[1:] if words[:1] == ["--"] else words


def _by(opts):
    by = opts.get("by") or "self"
    if by not in board.BYS:
        raise Fail("ArgumentsBad", "--by must be one of %s, not %r" % (", ".join(board.BYS), by))
    return by


def _own():
    return root.own_root(CTX.get("stack"))


def cmd_set(argv):
    opts, rest = parse(argv, "set", HELPS["set"],
                       {"--doing": "doing", "--back": "back", "--back-text": "back_text", "--for": "for",
                        "--accept": "accept", "--allow-from": "allow_from", "--deputy": "deputy", "--by": "by"},
                       {"--wake": "wake", "--clear-on-start": "clear_on_start", "--json": "json"})
    if not rest:
        raise Fail("ArgumentsBad", "missing MODE (one of %s) (usage: aos-comm board set MODE [TEXT...])" % ", ".join(board.MODES))
    now = times.now()
    text = " ".join(_words(rest[1:])).strip()
    fields = {"text": text or None, "doing": opts.get("doing") or None, "back_text": opts.get("back_text") or None,
              "accept": opts.get("accept") or None, "deputy": opts.get("deputy") or None}
    if opts.get("back"):
        fields["back_at"] = _when(opts["back"], "--back", now)
    if opts.get("for"):
        fields["expires_at"] = _when(opts["for"], "--for", now)
    if opts.get("allow_from"):
        fields["allow_from"] = [n.strip() for n in opts["allow_from"].split(",") if n.strip()]
    if opts.get("wake"):
        fields["wake_on_urgent"] = True
    if opts.get("clear_on_start"):
        fields["clear_on_start"] = True
    b = board.set_board(_own(), rest[0], fields, _by(opts), now)
    _print_written(b, opts)


def cmd_clear(argv):
    opts, rest = parse(argv, "clear", HELPS["clear"], {"--by": "by"}, {"--json": "json"})
    if rest:
        raise Fail("ArgumentsBad", "clear takes no arguments (usage: aos-comm board clear [-j])")
    _print_written(board.clear(_own(), _by(opts)), opts)


def cmd_wait(argv):
    opts, rest = parse(argv, "wait", HELPS["wait"], {"--ref": "ref", "--level": "level", "--by": "by"},
                       {"--done": "done", "--json": "json"})
    if opts.get("done"):
        if len(rest) != 1:
            raise Fail("ArgumentsBad", "wait --done takes one WHO (usage: aos-comm board wait --done WHO)")
        b, n = board.wait_done(_own(), rest[0], _by(opts))
        if not n:
            return 10
        _print_written(b, opts)
        return 0
    if len(rest) < 2:
        raise Fail("ArgumentsBad", "missing WHO or WHAT (usage: aos-comm board wait WHO WHAT...)")
    _print_written(board.wait_add(_own(), rest[0], " ".join(_words(rest[1:])), opts.get("ref"), opts.get("level"), _by(opts)), opts)


def _print_written(b, opts):
    if opts.get("json"):
        print(json.dumps(b, ensure_ascii=False))
    else:
        print("\n".join(lines(dict(board.effective(b), who="me"))))


# ---- 讀 ------------------------------------------------------------------------------

def read_one(who):
    """who＝名字、user、me → 四步算完的結果（加 who、stack）。"""
    daemon = CTX.get("daemon")
    if who == "user":
        stack, live = root.user_zone(), None
    elif who == "me":
        stack = _own()
        live = procs.live_of(procs.row_for(daemon, stack=stack))
    else:
        stack = procs.stack_of(who, daemon)
        live = procs.live_of(procs.row_for(daemon, name=who))
    b, problem = board.load(stack)
    if problem:
        aos_flags.warn(CTX["prog"], "the board of %s is unreadable (%s); counted as no board" % (who, problem))
    return dict(board.effective(b, live=live, problem=problem), who=who, stack=stack)


def cmd_show(argv):
    opts, rest = parse(argv, "show", HELPS["show"], {}, {"--json": "json"})
    if len(rest) > 1:
        raise Fail("ArgumentsBad", "show takes at most one NAME (usage: aos-comm board show [NAME|user|me])")
    r = read_one(rest[0] if rest else "me")
    print(json.dumps(r, ensure_ascii=False) if opts.get("json") else "\n".join(lines(r)))


def _flags(r):
    return [k for k in ("stale", "clock_odd", "overdue", "asleep") if r.get(k)]


def lines(r):
    """一行一項：key: value（給人、給腦看；程式用 -j）。"""
    b = r.get("board") or {}
    out = ["who: %s" % r.get("who", "me")]
    out.append("mode: %s" % r["mode"])
    out.append("posted: %s" % ("%s (seq %s, by %s)" % (b.get("updated_at"), b.get("seq", "-"), b.get("by", "-"))
                               if r["posted"] else "no board"))
    if _flags(r):
        out.append("notes: %s" % " ".join(_flags(r)))
    for k in ("text", "doing"):
        if b.get(k):
            out.append("%s: %s" % (k, " ".join(str(b[k]).splitlines())))
    for w in board.waiting(b):
        out.append("waiting for: %s: %s (since %s)%s" % (w["who"], w.get("what", ""), w.get("since_at", "?"),
                                                         "" if r["waiting_on"] else " [stale, does not count]"))
    if b.get("back_text") or b.get("back_at"):
        out.append("back: %s" % ("%s (%s)" % (b["back_text"], b["back_at"]) if b.get("back_text") and b.get("back_at")
                                 else b.get("back_text") or b["back_at"]))
    for k in ("expires_at", "accept", "deputy", "wake_on_urgent", "clear_on_start"):
        if k in b:
            out.append("%s: %s" % (k, json.dumps(b[k]) if isinstance(b[k], bool) else b[k]))
    if b.get("allow_from"):
        out.append("allow_from: %s" % ", ".join(map(str, b["allow_from"])))
    if r.get("live"):
        out.append("live: phase %s, busy %s" % (r["live"].get("phase") or "-", r["live"].get("busy") or "-"))
    return out


def _keep(r, only):
    waits = r["waiting_on"]
    return {None: True, "dnd": r["mode"] == "dnd", "away": r["mode"] == "away", "waiting": bool(waits),
            "waiting-user": any(w["who"] == "user" for w in waits)}[only]


def cmd_ls(argv):
    opts, rest = parse(argv, "ls", HELPS["ls"], {"--only": "only"}, {"--deep": "deep", "--json": "json"})
    if rest:
        raise Fail("ArgumentsBad", "ls takes no arguments (usage: aos-comm board ls [--deep] [--only ...])")
    only = opts.get("only")
    if only is not None and only not in ONLY:
        raise Fail("ArgumentsBad", "--only must be one of %s, not %r" % (", ".join(ONLY), only))
    top = CTX.get("daemon")
    got = walk.walk(procs.table, deep=bool(opts.get("deep")),
                    top=os.path.abspath(top) if top else None)
    for s in got["skipped"]:
        aos_flags.warn(CTX["prog"], "could not list the table %s: %s %s" % (s["table"], s["code"], s["reason"]))
    now = times.now()
    rows = []
    for row in got["rows"]:
        stack = row.get("stack")
        b, problem = board.load(stack) if isinstance(stack, str) and stack else (None, None)
        r = dict(board.effective(b, now, procs.live_of(row), problem), who=row["path"], stack=stack)
        if _keep(r, only):
            rows.append(r)
    count = {"procs": len(rows), "dnd": sum(r["mode"] == "dnd" for r in rows),
             "away": sum(r["mode"] == "away" for r in rows), "waiting": sum(bool(r["waiting_on"]) for r in rows),
             "waiting_user": sum(1 for r in rows for w in r["waiting_on"] if w["who"] == "user")}
    if opts.get("json"):
        print(json.dumps({"rows": rows, "count": count, "truncated": got["truncated"], "skipped": got["skipped"]},
                         ensure_ascii=False))
        return
    for r in rows:
        print("\t".join(_cols(r)))
    print("%d proc%s: %d dnd, %d away, %d waiting, %d waiting on user%s"
          % (count["procs"], "" if count["procs"] == 1 else "s", count["dnd"], count["away"], count["waiting"],
             count["waiting_user"], " (truncated)" if got["truncated"] else ""))


def _cols(r):
    b = r.get("board") or {}
    notes = _flags(r) if r["posted"] else ["no board"] + (["asleep"] if r["asleep"] else [])
    notes = [n for n in notes if n not in ("clock_odd", "overdue")]
    mode = r["mode"] + (" (%s)" % ", ".join(notes) if notes else "")
    doing = " ".join(str(b.get("doing") or "-").split())
    waits = ", ".join(sorted({w["who"] for w in r["waiting_on"]})) or "-"
    back = b.get("back_text") or b.get("back_at") or "-"
    if r["overdue"]:
        back += " (overdue)"
    return [r["who"], mode, doing, waits, " ".join(str(back).split())]


ACTIONS = {"set": cmd_set, "clear": cmd_clear, "wait": cmd_wait, "show": cmd_show, "ls": cmd_ls}
