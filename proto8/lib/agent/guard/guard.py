#!/usr/bin/env python3
# guard - before_tool hook logic: blocks file-tool writes outside the write scope (scope.py: AOS_WS plus
# AOS_WRITE_ALLOW, minus the deny list), inside .git, risky shell commands (a plain read-only shell command skips
# the deny patterns), subagent ops, clock_register boxes, mail to control, kernel or other agents' queue
# mailboxes, kernel_gate and agents_ctl ops. Config: the JSON file named by $AOS_GUARD_CFG, else none (defaults).
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
    # a broken config or event: an error line and exit 1; mounted with on_error "stop" the call never runs
    sys.stderr.write("guard: error: %s %s\n" % (code, " ".join(str(why).split())))
    sys.exit(1)


MAIL_FOREIGN_QUEUE = ("deny", "allow")   # guard.json mail_foreign_queue; missing = "deny"


def load_cfg():
    try:
        cfg = scope.load_cfg()
    except scope.ScopeError as e:
        fail(e.code, e.why)
    v = cfg.get("mail_foreign_queue", "deny")
    if v not in MAIL_FOREIGN_QUEUE:
        fail("CfgBad", "mail_foreign_queue in the guard config must be \"deny\" or \"allow\" (got %s)" % json.dumps(v))
    return cfg


_scope = []


def write_scope():
    if not _scope:
        try:
            _scope.append(scope.write_scope())
        except scope.ScopeError as e:
            fail(e.code, e.why)
    return _scope[0]


def allow_text(ws):
    extra = os.environ.get("AOS_WRITE_ALLOW", "")
    return "AOS_WS=%s, %s" % (ws, "AOS_WRITE_ALLOW=%s" % extra if extra else "AOS_WRITE_ALLOW not set")


def check_path(raw, cfg, ws):
    if not isinstance(raw, str) or not raw:
        out("blocked: a path argument is missing or not a string.")
    p = raw.split("#", 1)[0] if "#" in raw else raw
    real = resolve(p, ws)
    if any(part in cfg.get("deny_parts", [".git"]) for part in real.split("/")):
        out("blocked: %s is inside .git. Do not change .git; stop and report this as BLOCKED." % raw)
    sc = write_scope()
    for d in sc["deny"]:
        if under(real, [d["path"]]):
            out("blocked: %s is inside a folder no agent may write (%s, from %s). Stop and report this as BLOCKED."
                % (raw, d["path"], d["from"]))
    if not under(real, [a["path"] for a in sc["allow"]]):
        out("blocked: %s is outside the folders you may write (%s). Stop and report this as BLOCKED." % (raw, allow_text(ws)))


PATH_ARGS = {"write": ["path"], "edit": ["path"], "mkdir": ["path"], "trash": ["path"], "remove": ["path"],
             "json_set": ["path"], "json_add": ["path"], "json_del": ["path"],
             "copy": ["to"], "move": ["from", "to"]}

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
    $AOS_LLM_KERNEL/requests, <stack>/hooks/kernel_gate/requests, <stack>/hooks/<gate>/requests), or at or
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


def check_mail(args, cfg, ws):
    box = args.get("box")
    if box not in (None, ""):
        if not isinstance(box, str):
            out("blocked: box must be a path string.")
        real = resolve(box, ws)
        extra = [resolve(r, ws) for r in cfg.get("mail_deny", []) if isinstance(r, str) and r]
        if daemon_ctl_box(real) or kernel_box(real) or under(real, extra):
            out("blocked: you may not mail %s: it is a control or kernel mailbox. Mail whoever gave you the task instead." % box)
        q = foreign_queue(real) if cfg.get("mail_foreign_queue", "deny") == "deny" else None
        if q:
            out("blocked: you may not mail %s: it is another agent's queue (%s), and a letter there goes straight into "
                "its conversation. Send to its mailbox instead." % (box, q))
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
        if not isinstance(d, str) or resolve(d, ws) != resolve(rule["def"], ws):
            out("blocked: subagent add must use def %s." % rule["def"])
        aw, rw = args.get("ws"), rule.get("ws")
        if not (aw == rw or (isinstance(aw, str) and isinstance(rw, str) and aw and rw and resolve(aw, ws) == resolve(rw, ws))):
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
    if name in PATH_ARGS:
        for k in PATH_ARGS[name]:
            check_path(args.get(k), cfg, ws)
    elif name == "json_multi_set":
        for it in args.get("items") or [None]:
            check_path((it or {}).get("path") if isinstance(it, dict) else None, cfg, ws)
    elif name in ("shell", "run_python"):
        check_shell(name, args, cfg)
    elif name == "subagent":
        check_subagent(args, cfg, ws)
    elif name == "clock_register":
        box = args.get("box")
        if box not in (None, "") and (not isinstance(box, str) or resolve(box, ws) not in [resolve(b, ws) for b in cfg.get("clock_boxes", [])]):
            out("blocked: clock_register may only wake you (leave out box) or mail %s." % (", ".join(cfg.get("clock_boxes", [])) or "nobody else"))
    elif name == "mailbox_send":
        check_mail(args, cfg, ws)
    elif name == "kernel_gate":
        rule = cfg.get("kernel_gate")
        if rule is None:
            out("blocked: you may not use kernel_gate.")
        if args.get("op") not in rule.get("ops", []):
            out("blocked: kernel_gate op %r is not allowed for you (allowed: %s). Never switch the gate off."
                % (args.get("op"), ", ".join(rule.get("ops", []))))
    elif name == "agents_ctl":
        check_agents_ctl(args, cfg)
    sys.exit(0)


if __name__ == "__main__":
    main()
