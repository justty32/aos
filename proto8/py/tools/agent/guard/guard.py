#!/usr/bin/env python3
# guard - before_tool hook logic: blocks file-tool writes outside the write scope (scope.py: AOS_WS plus
# AOS_WRITE_ALLOW, minus the deny list), inside any proc's stack (rule proc-stack), inside a definition (rule
# definition-marker), inside .git, paths with # outside the json tools, paths starting with ~ (write, edit, mkdir, trash,
# remove, copy, move, ws_write, json_set/add/del/multi_set), risky shell commands
# (a plain read-only shell command skips the deny patterns), subagent ops, clock_register boxes and daemons, mail to
# control, kernel or other agents' queue mailboxes, mail to a box that is not a mailbox on its own daemon's table, in
# its workspace or listed in mail_allow_box, mail through another daemon, mail keep files outside the scope,
# kernel_gate and agents_ctl ops, and every tool it has no rule for; an unreadable daemon table or an argument of a
# wrong type blocks too (exit 10). Config: the JSON file named by $AOS_GUARD_CFG, else none (defaults).
# Derived from fsm-guard (commit 313ce20ec): same checks and tests, made neutral, with one write scope source.
import json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import scope   # noqa: E402  (next to this file)
sys.path.pop(0)

BLOCK = 10   # exit code of a before_tool hook that blocks the call

resolve, under, own_stack = scope.resolve, scope.under, scope.own_stack


def out(msg):
    sys.stdout.write("[aos] guard: " + msg + "\n")
    sys.exit(BLOCK)


def fail(code, why):
    # a broken config or event: an error line and exit 1; a failing before_tool hook stops the event, so the call never runs
    sys.stderr.write("guard: error: %s %s\n" % (code, " ".join(str(why).split())))
    sys.exit(1)


MAIL_FOREIGN_QUEUE = ("deny", "allow")   # guard.json mail_foreign_queue; missing = "deny"


def _strings(v):
    return isinstance(v, list) and all(isinstance(x, str) and x for x in v)


def _regex(v):
    try:
        re.compile(v)
        return True
    except (re.error, TypeError):
        return False


def check_cfg(cfg):
    """Types of the config keys the checks use, so that a later exception can only come from the arguments
    (those block, exit 10); a wrong config type is CfgBad (exit 1)."""
    def bad(key, what):
        fail("CfgBad", "%s in the guard config must be %s" % (key, what))
    v = cfg.get("mail_foreign_queue", "deny")
    if v not in MAIL_FOREIGN_QUEUE:
        fail("CfgBad", "mail_foreign_queue in the guard config must be \"deny\" or \"allow\" (got %s)" % json.dumps(v))
    for key in ("clock_boxes", "mail_deny", "mail_allow_box"):
        if key in cfg and not _strings(cfg[key]):
            bad(key, "a list of paths")
    if "shell_deny" in cfg and not (_strings(cfg["shell_deny"]) and all(_regex(p) for p in cfg["shell_deny"])):
        bad("shell_deny", "a list of regular expressions")
    if cfg.get("mail_allow_to") is not None and not (isinstance(cfg["mail_allow_to"], str) and _regex(cfg["mail_allow_to"])):
        bad("mail_allow_to", "a regular expression")
    for key in ("subagent", "kernel_gate", "agents_ctl"):
        rule = cfg.get(key)
        if rule is None:
            continue
        if not isinstance(rule, dict):
            bad(key, "an object")
        if "ops" in rule and not (isinstance(rule["ops"], list) and all(isinstance(x, str) for x in rule["ops"])):
            bad(key + ".ops", "a list of names")
    sub = cfg.get("subagent")
    if sub is not None:
        if not isinstance(sub.get("def"), str) or not sub["def"]:
            bad("subagent.def", "a path")
        if sub.get("ws") is not None and not isinstance(sub["ws"], str):
            bad("subagent.ws", "a path")
        if sub.get("name") is not None and not (isinstance(sub["name"], str) and _regex(sub["name"])):
            bad("subagent.name", "a regular expression")
    mx = (cfg.get("agents_ctl") or {}).get("max_timeout_s")
    if mx is not None and (not isinstance(mx, (int, float)) or isinstance(mx, bool)):
        bad("agents_ctl.max_timeout_s", "a number")


def load_cfg():
    try:
        cfg = scope.load_cfg()
    except scope.ScopeError as e:
        fail(e.code, e.why)
    check_cfg(cfg)
    return cfg


_scope = []
_event_stack = []   # the "stack" field of the hook event, set by main()


def table_bad(why):
    out("blocked: %s, so this call cannot be checked. Try once more; if it is blocked again, stop and report this "
        "as BLOCKED." % why)


def write_scope():
    if not _scope:
        try:
            _scope.append(scope.write_scope(stack=(_event_stack or [None])[0]))
        except scope.ScopeError as e:
            if e.code == "TableBad":
                table_bad(e.why)
            fail(e.code, e.why)
    return _scope[0]


def allow_text(ws):
    extra = os.environ.get("AOS_WRITE_ALLOW", "")
    return "AOS_WS=%s, %s" % (ws, "AOS_WRITE_ALLOW=%s" % extra if extra else "AOS_WRITE_ALLOW not set")


def tool_path(raw, ws):
    """A path argument of a tool, placed the way the tool places it: relative = from AOS_WS, no ~ expansion
    (rule no-tilde: a path starting with ~ is blocked, the tool would take it literally), then realpath."""
    if raw.startswith("~"):
        out("blocked: %s starts with ~, which tools do not expand: use an absolute path or one relative to AOS_WS." % raw)
    return resolve(raw, ws, home=False)


def places(p, ws):
    """Where a tool may act for path p: realpath of the whole path (write, edit, keep follow a final link) and
    realpath of its folder plus the last part (trash, remove, copy, move act on the entry itself). Both are checked."""
    full = tool_path(p, ws)
    q = p.rstrip("/")
    last = os.path.basename(q)
    if not q or last in (".", ".."):
        return [full]
    entry = os.path.join(tool_path(os.path.dirname(q) or ".", ws), last)
    return [full] if entry == full else [full, entry]


def check_path(raw, cfg, ws, json_tool=False):
    if not isinstance(raw, str) or not raw:
        out("blocked: a path argument is missing or not a string.")
    if "\0" in raw:
        out("blocked: a path argument holds a NUL character.")
    p = raw
    if json_tool:                # json tools cut FILE#/POINTER at the first #, as the tool does
        p = raw.split("#", 1)[0]
        if not p:
            out("blocked: %s has no file name before #." % raw)
    elif "#" in raw:             # rule no-hash-outside-json: the other tools take # literally
        out("blocked: %s: # is not allowed in paths of this tool. Stop and report this as BLOCKED." % raw)
    sc = write_scope()
    for real in places(p, ws):
        check_real(raw, real, cfg, ws, sc)


def check_read_path(raw):
    """A path the tool only reads (copy.from): not scope-checked, but # and a leading ~ are refused as for writes."""
    if isinstance(raw, str):
        if "#" in raw:
            out("blocked: %s: # is not allowed in paths of this tool. Stop and report this as BLOCKED." % raw)
        if raw.startswith("~"):
            out("blocked: %s starts with ~, which tools do not expand: use an absolute path or one relative to AOS_WS." % raw)


def check_real(raw, real, cfg, ws, sc):
    if any(part in scope.deny_parts(cfg) for part in real.split("/")):
        out("blocked: %s is inside .git. Do not change .git; stop and report this as BLOCKED." % raw)
    for d in sc["deny"]:
        if under(real, [d["path"]]):
            out("blocked: %s is inside a folder no agent may write (%s, from %s). Stop and report this as BLOCKED."
                % (raw, d["path"], d["from"]))
    st = scope.proc_stack(real)   # rule proc-stack: any proc's or daemon's stack, ours or a neighbour's; no config lifts it
    if st:
        out("blocked: %s is inside a proc's stack (%s, rule: proc-stack). Stop and report this as BLOCKED." % (raw, st))
    df = scope.definition_marker(real)   # rule definition-marker: works without the daemon table
    if df:
        out("blocked: %s is inside an agent definition (%s holds %s, rule: definition-marker). Stop and report this "
            "as BLOCKED." % (raw, df, scope.DEF_MARKER))
    if not under(real, [a["path"] for a in sc["allow"]]):
        out("blocked: %s is outside the folders you may write (%s). Stop and report this as BLOCKED." % (raw, allow_text(ws)))


PATH_ARGS = {"write": ["path"], "edit": ["path"], "mkdir": ["path"], "trash": ["path"], "remove": ["path"],
             "ws_write": ["path"], "json_set": ["path"], "json_add": ["path"], "json_del": ["path"],
             "copy": ["to"], "move": ["from", "to"]}
READ_ARGS = {"copy": ["from"]}   # read, not written: only the path rules no-hash-outside-json and no-tilde
JSON_TOOLS = scope.JSON_TOOLS
# every tool the guard has a rule for; any other name is blocked (mount the hook with a condition listing only these)
KNOWN_TOOLS = tuple(PATH_ARGS) + ("json_multi_set", "shell", "run_python", "subagent", "clock_register",
                                  "mailbox_send", "mailbox_read", "kernel_gate", "agents_ctl")

# ---- relaxed shell check: "plain read-only" commands skip shell_deny ----
# Anything this tokenizer is not sure about returns None (= strict path). It knows for every
# character whether it was quoted, so a quoted ";" or "|" is never taken for a separator.
PLAIN_CMDS = {"cat", "head", "tail", "wc", "grep", "egrep", "fgrep", "rg", "ls", "pwd", "cd", "echo",
              "printf", "true", "false", "test", "pgrep", "ps", "stat", "basename", "dirname", "realpath",
              "readlink", "du", "df", "cmp", "md5sum", "sha1sum", "sha256sum", "nl", "cut", "uniq", "tr",
              "column", "comm", "jq", "date", "id", "whoami", "uname", "which", "sort", "sed"}
WORD_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_./,:=@%+*?!~^-")
NAME_START = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_")
NAME_CHARS = NAME_START | set("0123456789")
REDIRS = ("2>/dev/null", ">/dev/null", "2>&1")   # the only redirections allowed; dropped from the words
WORD_END = set(" \t\n;|&")
# rg long options allowed (exactly, optionally with =VALUE); every other --option goes strict
# (rg runs programs with --pre and --hostname-bin, and decompressors with -z/--search-zip).
RG_LONG = {"files", "no-filename", "with-filename", "line-number", "no-line-number", "ignore-case",
           "smart-case", "case-sensitive", "fixed-strings", "word-regexp", "line-regexp", "count",
           "count-matches", "files-with-matches", "files-without-match", "hidden", "no-ignore", "glob",
           "iglob", "type", "type-not", "type-list", "context", "after-context", "before-context",
           "max-count", "max-depth", "max-columns", "only-matching", "invert-match", "regexp", "json",
           "multiline", "multiline-dotall", "no-heading", "heading", "column", "vimgrep", "null", "trim",
           "stats", "text", "follow", "sort", "sortr", "color", "pcre2", "quiet", "passthru", "replace"}
SED_SCRIPT = re.compile(r"(?:[0-9]+(?:,(?:[0-9]+|\$))?|\$)p")
SORT_OPT = re.compile(r"-[unrVhf]+")
CMD_WORD = re.compile(r"[A-Za-z0-9_-]+")
# variables that change what a plain command really runs: with one of these the relaxed check is skipped
RISKY_ENV = ("BASH_ENV", "ENV", "RIPGREP_CONFIG_PATH")


def shell_words(text):
    """Split text into simple commands of words; None if anything is not plainly understood."""
    if any(ord(c) < 32 and c not in "\t\n" or ord(c) == 127 for c in text):
        return None                                   # NUL, CR, other control characters
    cmds, cur, w = [], [], None                       # w = current word: {"v", "unq", "dollar", "glob"}
    i, n = 0, len(text)

    def word():
        return {"v": "", "unq": True, "dollar": False, "glob": False}

    def dollar(j, w):
        # text[j] == "$": only $NAME is allowed ($_ is not: it holds the last argument of the previous command)
        k = j + 1
        if k >= n or text[k] not in NAME_START:
            return None
        while k < n and text[k] in NAME_CHARS:
            k += 1
        if text[j + 1:k] == "_":
            return None
        w["v"] += text[j:k]
        w["dollar"] = True
        w["unq"] = False
        return k

    while i < n:
        c = text[i]
        if w is None and c not in " \t" and c not in WORD_END:
            hit = next((r for r in REDIRS if text.startswith(r, i) and (i + len(r) == n or text[i + len(r)] in WORD_END)), None)
            if hit:
                i += len(hit)
                continue
        if c in " \t":
            if w is not None:
                cur.append(w)
                w = None
            i += 1
        elif c in ";|&\n":
            if c == "&" and not text.startswith("&&", i):
                return None                           # background & (or &> and friends)
            if w is not None:
                cur.append(w)
                w = None
            if not cur:
                return None                           # empty command: ;; or | newline or a leading separator
            cmds.append(cur)
            cur = []
            i += 2 if text.startswith("&&", i) or text.startswith("||", i) else 1
        elif c == "'":
            w = w or word()
            j = text.find("'", i + 1)
            if j < 0:
                return None
            w["v"] += text[i + 1:j]
            w["unq"] = False
            i = j + 1
        elif c == '"':
            w = w or word()
            w["unq"] = False
            i += 1
            while True:
                if i >= n:
                    return None
                d = text[i]
                if d == '"':
                    i += 1
                    break
                if d in "\\`":
                    return None
                if d == "$":
                    i = dollar(i, w)
                    if i is None:
                        return None
                    continue
                w["v"] += d
                i += 1
        elif c == "$":
            return None                               # unquoted $NAME: bash splits it on IFS and globs it (found in review)
        elif c in WORD_CHARS:
            w = w or word()
            if c in "*?":
                w["glob"] = True
            w["v"] += c
            i += 1
        else:
            return None                               # \ ` # { } [ ] ( ) < > non-ASCII ...
    if w is not None:
        cur.append(w)
    if not cur:
        return None                                   # empty text or a trailing separator
    cmds.append(cur)
    return cmds


def plain_cmd(words):
    first, args = words[0], words[1:]
    if not first["unq"] or not CMD_WORD.fullmatch(first["v"]) or first["v"] not in PLAIN_CMDS:
        return False
    for a in args:
        # an unquoted glob may expand to a file name like --pre=sh: it must start with a literal, not - * ? $
        if a["glob"] and (a["v"][:1] in ("", "-", "*", "?", "$")):
            return False
    name = first["v"]
    if name in ("rg", "sed", "sort", "printf") and any(a["dollar"] for a in args):
        return False                                  # options of these must be visible as written
    if name == "rg":
        for a in args:
            v = a["v"]
            if v.startswith("--") and v != "--":
                if v[2:].split("=", 1)[0] not in RG_LONG:
                    return False
            elif v.startswith("-") and "z" in v:
                return False
    elif name == "sed":
        if len(args) < 2 or args[0]["v"] != "-n" or not SED_SCRIPT.fullmatch(args[1]["v"]):
            return False
        if any(a["v"].startswith("-") for a in args[2:]):
            return False                              # GNU sed would permute a later -e/-f/-i in
    elif name == "sort":
        if any(a["v"].startswith("-") and not SORT_OPT.fullmatch(a["v"]) for a in args):
            return False
    elif name == "printf":
        if args and args[0]["v"].startswith("-"):
            return False                              # printf -v NAME assigns a variable (PATH ...)
    elif name == "uniq":
        # uniq INPUT OUTPUT writes OUTPUT: at most one non-option word, no $NAME or glob that could become two
        # "-" alone and "--" are operands / end options: then a later -X is OUTPUT (found in review)
        if any(a["dollar"] or a["glob"] or a["v"] in ("-", "--") for a in args) \
                or sum(not a["v"].startswith("-") for a in args) > 1:
            return False
    elif name == "date":
        # date -s / --set / -us / MMDDhhmm set the clock: every word is +FORMAT or an option without s (found in review)
        for a in args:
            v = a["v"]
            if a["dollar"] or a["glob"] or not v.startswith(("-", "+")) or v.startswith("--s") or v == "--" \
                    or (v.startswith("-") and not v.startswith("--") and "s" in v):
                return False
    return True


def plain_read_only(text):
    """True only if every simple command is a plain read-only command (see README)."""
    if not isinstance(text, str):
        return False
    cmds = shell_words(text)
    return cmds is not None and all(plain_cmd(c) for c in cmds)


def untrusted_env(env=None):
    """Why the shell environment cannot be trusted for the relaxed check (a relative or empty PATH entry,
    BASH_ENV / ENV / RIPGREP_CONFIG_PATH set, an exported bash function), else None."""
    env = os.environ if env is None else env
    for k in RISKY_ENV:
        if k in env:
            return "%s is set" % k
    funcs = sorted(k for k in env if k.startswith("BASH_FUNC_"))
    if funcs:
        return "an exported bash function (%s) is set" % funcs[0]
    for part in env.get("PATH", "").split(os.pathsep):
        if not os.path.isabs(part):
            return "PATH has a relative or empty entry"   # never the entry itself: no environment values in messages
    return None


# ---- mail: no letters to a daemon's ctl mailbox, a kernel's request mailbox or another agent's queue ----
def daemon_ctl_box(real):
    """The daemon ctl mailbox real is at or under, else None. A daemon stack is a folder with procs_state.json;
    its ctl mailbox is <stack>/<procs_state.json#/procs_requests> (default procs_requests). A path part named
    procs_requests counts as a ctl mailbox even without the marker file."""
    if "procs_requests" in real.split("/"):
        return real
    d = real
    while True:
        st = os.path.join(d, "procs_state.json")
        if os.path.isfile(st):
            name = "procs_requests"
            try:
                with open(st, encoding="utf-8") as f:
                    v = json.load(f).get("procs_requests")
                if isinstance(v, str) and v:
                    name = v
            except (OSError, ValueError, AttributeError):
                pass
            box = os.path.realpath(os.path.join(d, name))
            if under(real, [box]):
                return box
        up = os.path.dirname(d)
        if up == d:
            return None
        d = up


def kernel_box(real):
    """True if real is a kernel request mailbox: a path part named requests (<station stack>/requests,
    $AOS_LLM_KERNEL/requests, <stack>/hookeds/kernel_gate/requests, <stack>/hookeds/<gate>/requests), or at or
    under $AOS_KERNEL or $AOS_LLM_KERNEL when they are set."""
    if "requests" in real.split("/"):
        return True
    env = [os.environ.get(k, "") for k in ("AOS_KERNEL", "AOS_LLM_KERNEL")]
    return under(real, [os.path.realpath(e) for e in env if e])


def foreign_queue(real):
    """The queue folder real is at or under when it is not the agent's own <stack>/queue, else None.
    By name: any path part named queue counts (a letter there goes straight into that agent's conversation)."""
    parts = real.split("/")
    mine = own_stack()
    mine = os.path.realpath(mine) if mine else None
    for i, part in enumerate(parts):
        if part == "queue" and i > 0:
            parent = "/".join(parts[:i]) or "/"
            if parent != mine:
                return "/".join(parts[:i + 1])
    return None


def check_keep(name, args, cfg, ws):
    """keep of mailbox_read / mailbox_send: a file name is written by the tool (opened for append, created), so it
    gets the write check. mailbox_read: true / false is not a path (true archives into the agent's own mailbox).
    mailbox_send: false = no keep; true is not a mode of the tool (it would pass true on as a file name)."""
    keep = args.get("keep")
    if keep is None or keep is False or keep == "":
        return
    if keep is True:
        if name == "mailbox_send":
            out("blocked: keep of mailbox_send is a file name (one JSON line per letter sent), not true.")
        return
    if not isinstance(keep, str):
        out("blocked: keep must be %s." % ("a file name" if name == "mailbox_send" else "true, false or a file name"))
    check_path(keep, cfg, ws)


def check_daemon(name, args, ws):
    """daemon of mailbox_send / clock_register: only the agent's own daemon (realpath of AOS_DAEMON), or none."""
    d = args.get("daemon")
    if d is None or d == "":
        return
    own = scope.daemon_folder()
    if not isinstance(d, str) or not own or tool_path(d, ws) != own:
        out("blocked: %s may only use your own daemon (AOS_DAEMON): leave out daemon." % name)


MAILBOX = "mailbox"   # a proc's mailbox is <stack>/mailbox (aos-mailbox BOX; the reply_to of its letters)


def box_allowed(real, cfg, ws):
    """The places a mailbox_send box may be (at or under one of them): <stack>/mailbox of every row on the own
    daemon table and of the agent itself (AOS_STACK, the event's stack), the agent's own <stack>/queue, with
    "mail_foreign_queue": "allow" also <stack>/queue of every row, the workspace, and the mail_allow_box entries.
    Nothing else: not another daemon's procs, not the user zone, unless listed in mail_allow_box."""
    try:
        rows = [st for st, _ in scope.table_rows() if st]
    except scope.ScopeError as e:
        table_bad(e.why)
    ev = (_event_stack or [None])[0]
    mine = [os.path.realpath(s) for s in (own_stack(), own_stack({"AOS_STACK": ev}) if ev else "") if s]
    places = [os.path.join(s, MAILBOX) for s in rows + mine] + [os.path.join(s, "queue") for s in mine]
    if cfg.get("mail_foreign_queue", "deny") == "allow":
        places += [os.path.join(s, "queue") for s in rows]
    places = [os.path.realpath(p) for p in places] + [os.path.realpath(ws)]
    places += [resolve(r, ws) for r in cfg.get("mail_allow_box", [])]
    return under(real, places)


def check_mail(args, cfg, ws):
    check_keep("mailbox_send", args, cfg, ws)
    check_daemon("mailbox_send", args, ws)
    box = args.get("box")
    if box not in (None, ""):
        if not isinstance(box, str):
            out("blocked: box must be a path string.")
        if "\0" in box:
            out("blocked: box holds a NUL character.")
        real = tool_path(box, ws)
        extra = [resolve(r, ws) for r in cfg.get("mail_deny", [])]
        if daemon_ctl_box(real) or kernel_box(real) or under(real, extra):
            out("blocked: you may not mail %s: it is a control or kernel mailbox. Mail whoever gave you the task instead." % box)
        q = foreign_queue(real) if cfg.get("mail_foreign_queue", "deny") == "deny" else None
        if q:
            out("blocked: you may not mail %s: it is another agent's queue (%s), and a letter there goes straight into "
                "its conversation. Send to its mailbox instead." % (box, q))
        if not box_allowed(real, cfg, ws):
            out("blocked: you may not mail %s: a box must be the mailbox of a proc on your own daemon's table, a folder "
                "in your workspace, or one listed in the guard config (mail_allow_box). To answer a letter from your own "
                "daemon, its reply_to works; otherwise mail by name (to) or ask whoever gave you the task." % box)
    to = args.get("to")
    pat = cfg.get("mail_allow_to")
    if to not in (None, "") and pat is not None and not re.fullmatch(pat, str(to)):
        out("blocked: you may not mail %r: only names matching %s. Mail whoever gave you the task instead." % (to, pat))


STRICT_NOTE = (" (strict check: a command skips it only if every part is a plain read-only command like rg, grep, cat,"
               " sed -n 'N,Mp', pgrep, with no substitutions or redirections; if this is a false positive,"
               " split the command or ask whoever gave you the task)")


def check_shell(name, args, cfg):
    text = args.get("command") if name == "shell" else args.get("code")
    if not isinstance(text, str):
        text = json.dumps(args)
    if "shell_deny" not in cfg:
        out("blocked: you may not use %s: the guard config has no shell rules (shell_deny)." % name)
    why = untrusted_env() if name == "shell" else None
    if name == "shell" and not why and plain_read_only(text):
        sys.exit(0)
    for pat in cfg.get("shell_deny", []):
        if re.search(pat, text):
            note = ""
            if name == "shell":
                note = STRICT_NOTE
                if why:
                    note += " (the relaxed check is off because the shell environment is not trusted: %s)" % why
            out("blocked: this command matches a forbidden pattern (%s). This command is not allowed here; "
                "stop and report this as BLOCKED." % pat + note)


def check_subagent(args, cfg, ws):
    rule = cfg.get("subagent")
    if rule is None:
        out("blocked: you may not use subagent.")
    op = args.get("op")
    if op not in rule.get("ops", []):
        out("blocked: subagent op %r is not allowed for you (allowed: %s). Do not change another agent's tools, brain, "
            "system text or hooks." % (op, ", ".join(rule.get("ops", []))))
    if op == "add":
        for k in ("def_json", "ws_json", "stack", "stack_json", "envs", "auto_restart", "limits"):
            if k in args:
                out("blocked: subagent add may not set %s." % k)
        d = args.get("def")
        if not isinstance(d, str) or not d or tool_path(d, ws) != resolve(rule["def"], ws):
            out("blocked: subagent add must use def %s." % rule["def"])
        aw, rw = args.get("ws"), rule.get("ws")
        if isinstance(aw, str) and aw:
            tool_path(aw, ws)    # rule no-tilde before the literal comparison
        if not (aw == rw or (isinstance(aw, str) and isinstance(rw, str) and aw and rw and tool_path(aw, ws) == resolve(rw, ws))):
            out("blocked: subagent add must use ws %s." % rule.get("ws"))
        pat = rule.get("name")
        if pat is not None and not re.fullmatch(pat, str(args.get("name", ""))):
            out("blocked: the name must match %s." % pat)
    if op == "rm" and args.get("purge"):
        out("blocked: rm a subagent without purge; its stack is kept as a record.")
    if op == "history" and (args.get("args") or {}).get("op") not in ("ls", None):
        out("blocked: you may only read a subagent's history (op ls).")


def check_agents_ctl(args, cfg):
    rule = cfg.get("agents_ctl")
    if rule is None:
        out("blocked: you may not use agents_ctl.")
    if args.get("op") not in rule.get("ops", []):
        out("blocked: agents_ctl op %r is not allowed for you (allowed: %s). Use it only to ring the bell: stop yourself."
            % (args.get("op"), ", ".join(rule.get("ops", []))))
    if rule.get("self_only"):
        me = os.path.basename(own_stack())
        if not me or args.get("name") != me:
            out("blocked: agents_ctl may only stop yourself (the name is the last part of your AOS_STACK); you asked "
                "for %r." % (args.get("name"),))
    t = args.get("timeout_s")
    mx = rule.get("max_timeout_s")
    if mx is not None and (not isinstance(t, (int, float)) or isinstance(t, bool) or t <= 0 or t > mx):
        out("blocked: agents_ctl stop needs timeout_s between 1 and %s (got %r)." % (mx, t))
    if args.get("no_wait") is not True:
        out("blocked: ring the bell with \"no_wait\": true (otherwise stopping yourself waits for the end of this very "
            "step and runs into timeout_s).")
    extra_keys = sorted(set(args) - {"op", "name", "timeout_s", "no_wait"})
    if extra_keys:
        out("blocked: agents_ctl stop takes only op, name, timeout_s, no_wait (got %s)." % ", ".join(extra_keys))


def main():
    try:
        event = json.load(sys.stdin)
    except ValueError as e:
        fail("ArgumentsBad", "the event on stdin is not JSON: %s" % e)
    if not isinstance(event, dict):
        fail("ArgumentsBad", "the event on stdin is not a JSON object")
    cfg = load_cfg()
    name, args = event.get("name"), event.get("arguments") or {}
    if not isinstance(args, dict):
        out("blocked: the arguments of %s are not a JSON object." % name)
    ws = os.environ.get("AOS_WS")
    if not ws:
        out("blocked: AOS_WS is not set in the hook, so paths cannot be checked.")
    if name not in KNOWN_TOOLS:
        out("blocked: guard has no rule for this tool (%s); remove it from the hook's condition or add a rule."
            % json.dumps(name))
    st = event.get("stack")   # written by the hook runner (hook_run.py), not by the agent's arguments
    if st not in (None, ""):
        if not isinstance(st, str) or "\0" in st:
            out("blocked: the stack field of the hook event is not a path string.")
        _event_stack.append(st)
    try:
        dispatch(name, args, cfg, ws)
    except (TypeError, ValueError, AttributeError, KeyError, IndexError) as e:
        # the config types were checked in load_cfg: what is left is an argument of the wrong type or shape
        out("blocked: the arguments of %s could not be checked (%s): check their types against the tool's "
            "description." % (name, type(e).__name__))
    sys.exit(0)


def dispatch(name, args, cfg, ws):
    if name in PATH_ARGS:
        for k in READ_ARGS.get(name, []):
            check_read_path(args.get(k))
        for k in PATH_ARGS[name]:
            check_path(args.get(k), cfg, ws, json_tool=name in JSON_TOOLS)
    elif name == "json_multi_set":
        for it in args.get("items") or [None]:
            check_path((it or {}).get("path") if isinstance(it, dict) else None, cfg, ws, json_tool=True)
    elif name in ("shell", "run_python"):
        check_shell(name, args, cfg)
    elif name == "subagent":
        check_subagent(args, cfg, ws)
    elif name == "clock_register":
        check_daemon("clock_register", args, ws)
        box = args.get("box")
        if box not in (None, "") and (not isinstance(box, str) or tool_path(box, ws) not in [resolve(b, ws) for b in cfg.get("clock_boxes", [])]):
            out("blocked: clock_register may only wake you (leave out box) or mail %s." % (", ".join(cfg.get("clock_boxes", [])) or "nobody else"))
    elif name == "mailbox_send":
        check_mail(args, cfg, ws)
    elif name == "mailbox_read":
        check_keep("mailbox_read", args, cfg, ws)
    elif name == "kernel_gate":
        rule = cfg.get("kernel_gate")
        if rule is None:
            out("blocked: you may not use kernel_gate.")
        if args.get("op") not in rule.get("ops", []):
            out("blocked: kernel_gate op %r is not allowed for you (allowed: %s). Never switch the gate off."
                % (args.get("op"), ", ".join(rule.get("ops", []))))
    elif name == "agents_ctl":
        check_agents_ctl(args, cfg)


if __name__ == "__main__":
    main()
