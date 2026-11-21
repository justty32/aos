# test_guard - unittest for the guard: runs _entry as a subprocess with a temp guard.json (relaxed shell check, bypasses,
# write scope from AOS_WS / AOS_WRITE_ALLOW, deny list, mail rules). Ported from fsm-guard (commit 313ce20ec).
import json, os, subprocess, sys, tempfile, unittest

sys.dont_write_bytecode = True   # importing guard.py must not leave __pycache__ next to it

HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.dirname(HERE)
GUARD = os.path.join(DIR, "_entry")

# an example shell_deny (git writes, network, kill, aos commands, rm)
EXAMPLE_DENY = [
    "\\bgit\\s+(commit|push|reset|checkout|restore|stash|clean|rebase|merge|switch|branch|tag|am|apply|cherry-pick|revert|rm|mv|add|config|worktree|remote|fetch|pull|gc|update-ref|update-index)\\b",
    "\\b(sudo|su|curl|wget|ssh|scp|nc|pkill|killall|kill)\\b",
    "\\baos-[a-z-]+",
    "\\brm\\s",
]

sys.path.insert(0, DIR)
import guard as G   # noqa: E402
sys.path.pop(0)

# real read-only commands that the strict check used to block (paths made generic, shape kept)
T11 = "cd /work/src && cat src/ctl/set_def.py && cat src/ctl/rm.py && sed -n '135,205p' src/ctl/add.py && sed -n '90,180p' src/ctl/shared.py && rg -n 'def test_|set-def|rm accepted|set_def' src/tests/test_kernel* && sed -n '17,24p' src/README.md"
T14 = "cd /work/src && rg -n 'import process_group|from process_group|import cmd_call|from cmd_call' lib && rg -n 'ModuleMissing|tool_io.py|isolat|kill|signal' lib/a/tests lib/b/tests lib/c/tests && ls -la lib/tests && rg --files /work | rg 'clean|check|\\.sh$'"
T15 = "cd /work/src && rg -n 'from daemon_ctl import|import daemon_ctl|\\bdaemon_ctl\\.[A-Za-z_]+|getattr\\(dc|patch.object\\(dc' src -g '!*.html' -g '!*.md' -g '!*.csv' -g '!*.json' -g '!src/daemon_ctl/**' && printf '\\nAll package attribute names used outside package:\\n' && rg -o --no-filename '\\b(dc|daemon_ctl)\\.[A-Za-z_]+' src -g '!src/daemon_ctl/**' -g '!*.html' -g '!*.md' -g '!*.csv' -g '!*.json' | sort -u && printf '\\nInitial daemon process list:\\n' && pgrep -u \"$USER\" -af aos-daemon"
CPP_RG = "rg -n -A 75 -B 18 'def sender_key_warnings|relative keys count from|test_missing_sender_folder_warns_once' src/a.py cpp/aos-x/src/b.cpp tests/test_a.py cpp/aos-x/tests/test_b.py"
CPP = "cd /work/src && git --no-optional-locks status --short && " + CPP_RG


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = self.tmp.name
        self.ws = os.path.join(t, "ws")
        self.root = os.path.join(t, "root")
        self.box = os.path.join(t, "notify-box")
        self.defdir = os.path.join(t, "defs", "worker")
        self.stack = os.path.join(t, "procs", "w-01")
        for d in (self.ws, self.root, self.box, self.defdir, self.stack):
            os.makedirs(d)
        os.makedirs(os.path.join(self.root, ".git"))
        self.allow = [self.root]   # AOS_WRITE_ALLOW; AOS_WS (self.ws) is always allowed
        self.cfg = {
            "deny_parts": [".git"],
            "shell_deny": EXAMPLE_DENY,
            "subagent": {"ops": ["add", "ls", "rm", "history"], "def": self.defdir, "ws": "team", "name": "w-[0-9]+"},
            "clock_boxes": [self.box],
            "kernel_gate": {"ops": ["on", "ls", "pass", "refuse"]},
            "agents_ctl": {"ops": ["stop"], "self_only": True, "max_timeout_s": 600},
        }
        self.write_cfg()

    def tearDown(self):
        self.tmp.cleanup()

    def write_cfg(self):
        self.cfg_path = os.path.join(self.tmp.name, "guard.json")
        with open(self.cfg_path, "w", encoding="utf-8") as f:
            json.dump(self.cfg, f)

    env_base = {}   # environment every call of a test class gets (before env_extra)

    def run_guard(self, name, arguments, stack=None, env_extra=None, event=None):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("AOS_", "BASH_FUNC_")) and k not in G.RISKY_ENV}
        env.update(AOS_GUARD_CFG=self.cfg_path, AOS_WS=self.ws, AOS_STACK=stack or self.stack)
        if self.allow:
            env["AOS_WRITE_ALLOW"] = os.pathsep.join(self.allow)
        env.update(self.env_base)
        env.update(env_extra or {})
        env = {k: v for k, v in env.items() if v is not None}   # None = drop that variable
        ev = dict(event or {}, name=name, arguments=arguments)   # event = more fields of the hook event (stack ...)
        p = subprocess.run([sys.executable, GUARD], input=json.dumps(ev),
                           capture_output=True, text=True, env=env, timeout=30)
        self.last_err, self.last_out = p.stderr, p.stdout
        return p.returncode, p.stdout

    def allowed(self, name, arguments, **kw):
        code, out = self.run_guard(name, arguments, **kw)
        self.assertEqual(code, 0, "expected allowed, got %d: %s" % (code, out))

    def blocked(self, name, arguments, **kw):
        code, out = self.run_guard(name, arguments, **kw)
        self.assertEqual(code, 10, "expected blocked, got %d: %s" % (code, out))
        self.assertTrue(out.startswith("[aos] guard:"), out)
        return out

    def sh_ok(self, cmd):
        self.assertTrue(G.plain_read_only(cmd), "expected plain read-only: %r" % cmd)
        self.allowed("shell", {"command": cmd})

    def sh_block(self, cmd):
        """Not plain read-only, and the strict regex blocks it."""
        self.assertFalse(G.plain_read_only(cmd), "expected NOT plain read-only: %r" % cmd)
        return self.blocked("shell", {"command": cmd})

    def not_plain(self, cmd):
        """Not plain read-only (strict path). The example regex itself may not catch it: that is today's regex, unchanged."""
        self.assertFalse(G.plain_read_only(cmd), "expected NOT plain read-only: %r" % cmd)


class RecordedFalsePositives(Base):
    def test_t11(self):
        self.sh_ok(T11)

    def test_t14(self):
        self.sh_ok(T14)

    def test_t15(self):
        self.sh_ok(T15)

    def test_cpp_path_rg_part_alone(self):
        self.sh_ok("cd /work/src && " + CPP_RG)

    def test_cpp_path_with_git_stays_strict(self):
        out = self.sh_block(CPP)
        self.assertIn("aos-", out)
        self.assertIn("strict check", out)


class PlainAllowed(Base):
    CASES = [
        'grep "rm accepted" f',
        "rg -n kill_group .",
        'pgrep -u "$USER" -af aos-daemon',
        "sed -n '1,20p' f",
        "ls -la 2>/dev/null | head -5",
        'echo "$HOME"',
        "sort -u f",
        "cat a b && wc -l c",
        "echo 'x; rm y | kill 1'",           # quoted separators are literal
        "echo 'a\nrm -rf x'",                  # newline inside quotes is literal
        "rg -n 'rm x' src 2>&1 | head -3",
        "cat a >/dev/null || echo aos-daemon",
        "sed -n '$p' f",
        "sed -n '5,$p' f",
        "sort -nr f | uniq",
        "printf '%s\\n' kill",
        "rg -n x src/*.py",
        "which kill",
        "jq -r .name aos-x.json",
        "cd /tmp\nls -la",
        "cat 2>/dev/null x",
        "rg -n '\u4e2d\u6587 kill' .",   # non-ASCII on purpose (escaped), inside quotes
        "rg -n x -",
        "sed -n 1p f g",
        "sort -unr f",
        "printf '' aos-x",
        "cat x ~/aos-y",
    ]

    def test_cases(self):
        for c in self.CASES:
            with self.subTest(cmd=c):
                self.sh_ok(c)


class BriefMustBlock(Base):
    CASES = [
        "rm x",
        "cd d && rm x",
        "find . -exec rm {} ;",
        "echo $(kill 1)",
        "echo `kill 1`",
        'bash -c "git commit"',
        "/bin/kill 1",
        "./rm x",
        "X=1 git commit -m m",
        "aos-agent ctl ls",
        "ls | xargs rm x",
    ]

    def test_cases(self):
        for c in self.CASES:
            with self.subTest(cmd=c):
                self.sh_block(c)

    def test_xargs_rm_at_end(self):
        # "ls | xargs rm": xargs is not plain; the example regex \brm\s needs a blank after rm, so the
        # unchanged strict path lets this exact text through (known regex limit, the sandbox bounds it).
        self.not_plain("ls | xargs rm")


class ReviewBypasses(Base):
    # bypasses found in design review
    CASES = [
        "echo ok\nrm -rf x",
        "(true);rm -rf x",
        "true;(rm -rf x)",
        "echo hi |& rm x",
        "case x in a) rm x;; esac",
        "2>/dev/null rm x",
        "1>&2 kill 1",
        "A+=1 rm x",
        "function f { rm x; }; f",
        "coproc rm x",
        "git -c alias.x='!rm x' x",
        "git -c core.pager='rm x' log -1",
        "/usr/bin/time rm x",
        "python3 -c 'import os; os.system(\"rm x\")'",
        "awk 'BEGIN{system(\"rm x\")}'",
        "strace rm x",
        'rg ";" echo --pre=rm pattern .',
        "sed -n '1p' \";\" echo -e '1e rm x' /etc/hosts",
        "sort \";\" echo --compress-program=rm -S 1b /etc/passwd",
        "echo $'\\''; rm -rf x; echo \\'",
        "echo ${a:=x} rm x",
        "./test rm x",
        "/tmp/cat rm x",
        "sed -n '1p' -e '1e rm x' /etc/hosts",
        "sort --comp=rm -S 1b /etc/passwd",
        "sort --compress-program=rm f",
        "echo;# '\nrm -rf x\necho '",
        "cat a#b; rm x",
        "cat x & rm y",
        "rg --pre rm x .",
        "rg --pre=rm x .",
        "sed 's/.*/rm x/e' f",
        "ls > f; rm x",
        "cat f\rkill 1",
        "caté rm x",                          # non-ASCII on purpose
        "echo x; é kill 1",
    ]
    # bypasses where the example regex finds no denied word at all: only check the relaxed path refuses
    NOT_PLAIN_ONLY = [
        "r\\\nm x",
        '"r\\\nm" x',
        "{rm,-f} x",
        "{git,commit} -m x",
        "/bin/[r]m x",
        "/bin/r? x",
        "X=commit; git $X -m msg",
        "git $'commit' -m msg",
        "true $[PATH=0] && diff -l a b",
        "diff -l a b",
        "file -z x",
        "./test",
        "echo ${a:=$}${b:=\\(rm\\ x\\)}${c:=$a$b} ${c@P}",
    ]

    def test_blocked(self):
        for c in self.CASES:
            with self.subTest(cmd=c):
                self.sh_block(c)

    def test_not_plain(self):
        for c in self.NOT_PLAIN_ONLY:
            with self.subTest(cmd=c):
                self.not_plain(c)


class OwnBypassIdeas(Base):
    # more bypass ideas; every one must stay off the relaxed path
    CASES = [
        # $_ is the last argument of the previous command: rg would get --pre=sh
        "echo --pre=sh; rg x $_ ; rm y",
        'echo --pre=sh; rg x "$_" ; rm y',
        "echo $_ rm x",
        # globs that can expand to a planted file name such as --pre=sh or -e1e rm x
        "rg x * ; rm y",
        "sed -n 1p * ; rm y",
        "sort ?* ; rm y",
        "rg x -* ; rm y",
        "cat '-'* ; rm y",
        # $NAME in options of rg/sed/sort/printf
        "rg $OPT x ; rm y",
        'sed -n "$S" f ; rm y',
        "sed -n '1p' $F ; rm y",
        "sort $O f ; rm y",
        "printf $FMT ; rm y",
        # printf -v assigns (PATH, ...)
        "printf -v PATH %s . ; cat rm x",
        "printf -vPATH x ; cat rm x",
        # rg options that run programs
        "rg --hostname-bin=sh x ; rm y",
        "rg --search-zip x ; rm y",
        "rg -z x ; rm y",
        "rg -inz x ; rm y",
        "rg --pre-glob='*' --pre=sh x ; rm y",
        "rg --pr=sh x ; rm y",
        "rg -e --pre=sh x ; rm y",
        # sed forms
        "sed -n '1w out' f ; rm y",
        "sed -n '1p;e rm x' f",
        "sed -n -e '1p' f ; rm y",
        "sed --quiet '1p' f ; rm y",
        "sed -n '1p' f -i ; rm y",
        "sed -n '1p' -- -e ; rm y",
        "sed -n -n '1p' f ; rm y",
        "sed -n 1p f --expression=1e ; rm y",
        # sort forms
        "sort -o out f ; rm y",
        "sort -k1 f ; rm y",
        "sort --files0-from=x ; rm y",
        "sort - f ; rm y",
        # separators and empty commands
        "cat x |\nrm y",
        "cat x &&\nrm y",
        "cat x;;rm y",
        ";rm y",
        # quoting / escaping of the command word
        "\\rm x",
        "$HOME/rm x",
        "${HOME}/rm x",
        "c\"a\"t x; rm y",
        # redirections other than the three allowed ones
        "cat x 1>/dev/null; rm y",
        "cat x &>/dev/null; rm y",
        "cat x >/dev/null2; rm y",
        "cat x 2>&1>/dev/null; rm y",
        "cat x 2>&1&rm y",
        "cat x >out; rm y",
        "cat x <in; rm y",
        "cat <<E\nrm y\nE",
        "cat <<<x; rm y",
        "cat <(rm y)",
        # odd characters
        "cat\u00a0x; rm y",                  # no-break space, on purpose
        "cat x\x0b; rm y",
        "cat x\x00; rm y",
        "cat 'x\r'; rm y",
        "cat x; \u3000rm y",                  # ideographic space, on purpose
        "echo \"\\\"; rm y\"",
        "echo \"`rm y`\"",
        "echo \"$(rm y)\"",
        "echo \"$1\" rm y",
        "echo $$ rm y",
        "echo 'x; rm y",
        "echo \"x; rm y",
        # leading assignments and wrappers
        "EDITOR=rm cat x",
        "env rm x",
        "command rm x",
        "builtin rm x",
        "exec rm x",
        "eval rm x",
        "nohup rm x",
        "timeout 1 rm x",
        "! rm x",
        "time rm x",
        "if true; then rm x; fi",
        "for i in 1; do rm x; done",
        "cat x | sh -c 'rm y'",
        "ls | xargs -I{} rm {}",
        "cat x | tee >(rm y)",
        "git log; rm y",
        "cat x |& cat; rm y",
        "cat x ;& rm y",
        "cat x &&& rm y",
        "cat x ||| rm y",
        "cat x; 2>/dev/null rm y",
        "cat x2>/dev/null; rm y",
        "cat \"x\"2>/dev/null; rm y",
        "cat x ; !rm y",
        "cat x\t#c\nrm y",
        "rg x ~ --type-add 'x:*.x' ; rm y",
        "rg --no-config x ; rm y",
        "rg -g '*' --pre sh x; rm y",
    ]

    def test_cases(self):
        for c in self.CASES:
            with self.subTest(cmd=c):
                self.sh_block(c)

    # regex finds no denied word in these (or nothing harmful at all): only the relaxed path must refuse
    NOT_PLAIN_ONLY = [
        "cat x ;",
        "cat x\n",
        '"rm" x',
        "r''m x",
        "$RM x",
        "c\\at x",
        "cat x; >/dev/null",
        "cat x | >/dev/null",
    ]

    def test_not_plain(self):
        for c in self.NOT_PLAIN_ONLY:
            with self.subTest(cmd=c):
                self.not_plain(c)

    def test_empty(self):
        self.assertFalse(G.plain_read_only(""))
        self.assertFalse(G.plain_read_only(None))
        self.allowed("shell", {"command": ""})

    def test_non_string_command(self):
        self.assertFalse(G.plain_read_only(["cat", "x"]))
        self.blocked("shell", {"command": ["rm -rf", "x"]})


class WriteArgsStrict(Base):
    # found in review: uniq IN OUT writes OUT; date -s / MMDDhhmm set the clock;
    # an unquoted $NAME is split on IFS by bash, so it is never plain
    def test_not_plain(self):
        for cmd in ("uniq in out", "uniq -c in out", "uniq $X", "uniq a*", "uniq -- a b",
                    "date -s 2020-01-01", "date --set=2020-01-01", "date -s2020-01-01",
                    # found in a later review round
                    "echo data | uniq - out.txt", "uniq - out.txt", "uniq in.txt -- -out.txt",
                    "date -us 2025-01-01", "date -Rs 2025-01-01", "date 010100002025", "date -u -- 0101",
                    "date -u$IFS-s 2025-01-01", "date $u-s 2025-01-01", "date a$IFS* x",
                    "cat a$IFS* ; rm y", "ls $X", "echo $HOME"):
            with self.subTest(cmd=cmd):
                self.not_plain(cmd)

    def test_still_plain(self):
        for cmd in ("sort f | uniq -c", "uniq -c f", "uniq -d", "date", "date +%F", "date -u", "date -u +%H:%M",
                    'echo "$HOME"', 'ls "$X"'):
            with self.subTest(cmd=cmd):
                self.sh_ok(cmd)


class RunPythonStrict(Base):
    def test_run_python_not_relaxed(self):
        self.assertTrue(G.plain_read_only("echo rm x"))
        out = self.blocked("run_python", {"code": "echo rm x"})
        self.assertNotIn("strict check", out)

    def test_run_python_clean(self):
        self.allowed("run_python", {"code": "print(1)"})

    def test_shell_message(self):
        out = self.blocked("shell", {"command": "cd d && rm x"})
        self.assertIn("forbidden pattern", out)
        self.assertIn("(strict check: a command skips it only if every part is a plain read-only command like rg, grep, cat, sed -n 'N,Mp', pgrep, with no substitutions or redirections; if this is a false positive, split the command or ask whoever gave you the task)", out)


class OldRules(Base):
    def test_write_inside_allowed(self):
        self.allowed("write", {"path": os.path.join(self.root, "a.txt")})

    def test_write_outside_blocked(self):
        out = self.blocked("write", {"path": os.path.join(self.tmp.name, "elsewhere.txt")})
        self.assertIn("outside the folders you may write", out)

    def test_relative_path_from_ws(self):
        # a relative path counts from AOS_WS, which may always be written
        self.allowed("edit", {"path": "a.txt"})
        out = self.blocked("edit", {"path": "../elsewhere.txt"})
        self.assertIn("(AOS_WS=%s, AOS_WRITE_ALLOW=%s)" % (self.ws, self.root), out)

    def test_git_blocked(self):
        out = self.blocked("write", {"path": os.path.join(self.root, ".git", "config")})
        self.assertIn("inside .git", out)

    def test_move_checks_both(self):
        self.blocked("move", {"from": os.path.join(self.tmp.name, "x"), "to": os.path.join(self.root, "y")})
        self.allowed("move", {"from": os.path.join(self.root, "x"), "to": os.path.join(self.root, "y")})

    def test_json_multi_set(self):
        self.allowed("json_multi_set", {"items": [{"path": os.path.join(self.root, "a.json")}]})
        self.blocked("json_multi_set", {"items": []})

    def test_subagent_add_envs_blocked(self):
        out = self.blocked("subagent", {"op": "add", "def": self.defdir, "ws": "team", "name": "w-02", "envs": {"X": "1"}})
        self.assertIn("may not set envs", out)

    def test_subagent_add_ok(self):
        self.allowed("subagent", {"op": "add", "def": self.defdir, "ws": "team", "name": "w-02"})

    def test_subagent_bad_name_and_op(self):
        self.blocked("subagent", {"op": "add", "def": self.defdir, "ws": "team", "name": "bob"})
        self.blocked("subagent", {"op": "set_def"})
        self.blocked("subagent", {"op": "rm", "purge": True})
        self.blocked("subagent", {"op": "history", "args": {"op": "rm"}})

    def test_clock_register(self):
        self.allowed("clock_register", {})
        self.allowed("clock_register", {"box": self.box})
        out = self.blocked("clock_register", {"box": os.path.join(self.tmp.name, "other-box")})
        self.assertIn("clock_register may only wake you", out)

    def test_kernel_gate(self):
        self.allowed("kernel_gate", {"op": "pass"})
        out = self.blocked("kernel_gate", {"op": "off"})
        self.assertIn("Never switch the gate off", out)

    def test_agents_ctl_ok(self):
        self.allowed("agents_ctl", {"op": "stop", "name": "w-01", "timeout_s": 60, "no_wait": True})

    def test_agents_ctl_from_hook_cell(self):
        cell = os.path.join(self.stack, "hookeds", "guard")
        os.makedirs(cell)
        self.allowed("agents_ctl", {"op": "stop", "name": "w-01", "timeout_s": 60, "no_wait": True}, stack=cell)

    def test_agents_ctl_rules(self):
        self.blocked("agents_ctl", {"op": "start", "name": "w-01", "timeout_s": 60, "no_wait": True})
        self.blocked("agents_ctl", {"op": "stop", "name": "w-02", "timeout_s": 60, "no_wait": True})
        self.blocked("agents_ctl", {"op": "stop", "name": "w-01", "timeout_s": 0, "no_wait": True})
        self.blocked("agents_ctl", {"op": "stop", "name": "w-01", "timeout_s": 601, "no_wait": True})
        self.blocked("agents_ctl", {"op": "stop", "name": "w-01", "timeout_s": True, "no_wait": True})
        self.blocked("agents_ctl", {"op": "stop", "name": "w-01", "timeout_s": 60})
        self.blocked("agents_ctl", {"op": "stop", "name": "w-01", "timeout_s": 60, "no_wait": True, "force": True})

    def test_missing_rules_blocked(self):
        for k in ("subagent", "kernel_gate", "agents_ctl"):
            del self.cfg[k]
        self.write_cfg()
        self.blocked("subagent", {"op": "ls"})
        self.blocked("kernel_gate", {"op": "ls"})
        self.blocked("agents_ctl", {"op": "stop"})


class DenyRoots(Base):
    # deny_roots from guard.json, the agent's own stack and $AOS_CD always, deny beats the allowed folders
    def setUp(self):
        super().setUp()
        self.secret = os.path.join(self.root, "secret")
        os.makedirs(self.secret)

    def test_config_deny_root(self):
        self.cfg["deny_roots"] = [self.secret]
        self.write_cfg()
        out = self.blocked("write", {"path": os.path.join(self.secret, "a.txt")})
        self.assertIn("inside a folder no agent may write (%s, from guard.json)" % self.secret, out)
        self.assertIn("report this as BLOCKED", out)
        self.allowed("write", {"path": os.path.join(self.root, "a.txt")})

    def test_deny_beats_allowed(self):
        # the secret folder is inside AOS_WRITE_ALLOW; deny still wins, also for json_multi_set and copy targets
        self.cfg["deny_roots"] = [self.secret]
        self.write_cfg()
        self.blocked("json_multi_set", {"items": [{"path": os.path.join(self.root, "ok.json")},
                                                  {"path": os.path.join(self.secret, "x.json") + "#/a"}]})
        self.blocked("copy", {"to": os.path.join(self.secret, "c")})
        self.blocked("write", {"path": self.secret})
        self.allowed("json_multi_set", {"items": [{"path": os.path.join(self.root, "ok.json")}]})

    def test_auto_stack(self):
        # AOS_WRITE_ALLOW covers the whole tmp tree, the stack is inside it: still blocked
        self.allow = [self.tmp.name]
        out = self.blocked("write", {"path": os.path.join(self.stack, "tools", "x.json")})
        self.assertIn("no agent may write (%s, from AOS_STACK)" % self.stack, out)
        self.blocked("edit", {"path": self.stack})
        self.allowed("write", {"path": os.path.join(self.tmp.name, "procs", "other.txt")})

    def test_auto_stack_from_hook_cell(self):
        # a hook runs with AOS_STACK = <stack>/hookeds/<hook>; the whole agent stack is denied, not only the cell
        self.allow = [self.tmp.name]
        cell = os.path.join(self.stack, "hookeds", "guard")
        os.makedirs(cell)
        self.blocked("write", {"path": os.path.join(self.stack, "hookeds.json")}, stack=cell)
        self.blocked("write", {"path": os.path.join(cell, "x")}, stack=cell)
        self.allowed("write", {"path": os.path.join(self.root, "x")}, stack=cell)

    def test_auto_aos_cd(self):
        cd = os.path.join(self.root, "def")
        os.makedirs(cd)
        out = self.blocked("write", {"path": os.path.join(cd, "_entry")}, env_extra={"AOS_CD": cd})
        self.assertIn("no agent may write (%s, from AOS_CD)" % cd, out)
        self.allowed("write", {"path": os.path.join(self.root, "x")}, env_extra={"AOS_CD": cd})
        self.allowed("write", {"path": os.path.join(cd, "_entry")})   # AOS_CD not set: only the allowed folders count

    def test_config_cannot_turn_off_auto(self):
        self.allow = [self.tmp.name]
        self.cfg["deny_roots"] = []
        self.write_cfg()
        self.blocked("write", {"path": os.path.join(self.stack, "x")})

    def test_deny_root_via_symlink(self):
        # a link in an allowed folder that points into the stack is resolved first
        self.allow = [self.root]
        os.symlink(self.stack, os.path.join(self.root, "st"))
        self.blocked("write", {"path": os.path.join(self.root, "st", "x")})


class TildePaths(Base):
    def setUp(self):
        super().setUp()
        self.home = os.path.join(self.tmp.name, "home")
        os.makedirs(os.path.join(self.home, "allowed"))
        self.allow = [os.path.join(self.home, "allowed")]
        self.env = {"HOME": self.home}

    def test_tilde_tool_arg_blocked(self):
        # tools take ~ literally (<ws>/~/...), so the guard does not expand it: it blocks it
        for name, args in (("write", {"path": "~/allowed/x"}), ("json_set", {"path": "~/allowed/x.json#/a"}),
                           ("edit", {"path": "~"}), ("move", {"from": "a", "to": "~/allowed/b"}),
                           ("mailbox_send", {"box": "~/box"}), ("mailbox_read", {"keep": "~/allowed/k.jsonl"})):
            with self.subTest(tool=name):
                out = self.blocked(name, args, env_extra=self.env)
                self.assertIn("%s" % NO_TILDE, out)
        self.allowed("write", {"path": os.path.join(self.home, "allowed", "x")}, env_extra=self.env)

    def test_tilde_outside_blocked(self):
        out = self.blocked("write", {"path": "~/y"}, env_extra=self.env)
        self.assertIn("%s" % NO_TILDE, out)
        self.blocked("write", {"path": "~"}, env_extra=self.env)

    def test_tilde_not_taken_as_ws_folder(self):
        # "~/x" would land in <ws>/~/x, inside AOS_WS; it is blocked all the same (no-tilde), not allowed
        self.allow = []
        out = self.blocked("write", {"path": "~/allowed/x"}, env_extra=self.env)
        self.assertIn("%s" % NO_TILDE, out)
        self.allowed("write", {"path": "./~/allowed/x"}, env_extra=self.env)   # written out literally: inside AOS_WS

    def test_tilde_in_write_allow(self):
        self.allow = ["~/allowed"]
        self.allowed("write", {"path": os.path.join(self.home, "allowed", "x")}, env_extra=self.env)
        self.blocked("write", {"path": os.path.join(self.home, "x")}, env_extra=self.env)

    def test_tilde_clock_box(self):
        # the config entry is expanded (~ = HOME); the tool argument is not, so "~/box" is blocked
        self.cfg["clock_boxes"] = ["~/box"]
        self.write_cfg()
        out = self.blocked("clock_register", {"box": "~/box"}, env_extra=self.env)
        self.assertIn("%s" % NO_TILDE, out)
        self.allowed("clock_register", {"box": os.path.join(self.home, "box")}, env_extra=self.env)
        self.blocked("clock_register", {"box": "~/other"}, env_extra=self.env)

    def test_tilde_subagent_def(self):
        d = os.path.join(self.home, "defs", "w")
        os.makedirs(d)
        self.cfg["subagent"]["def"] = "~/defs/w"
        self.write_cfg()
        self.allowed("subagent", {"op": "add", "def": d, "ws": "team", "name": "w-02"}, env_extra=self.env)
        out = self.blocked("subagent", {"op": "add", "def": "~/defs/w", "ws": "team", "name": "w-02"}, env_extra=self.env)
        self.assertIn("%s" % NO_TILDE, out)
        self.blocked("subagent", {"op": "add", "def": "~/defs/x", "ws": "team", "name": "w-02"}, env_extra=self.env)
        self.blocked("subagent", {"op": "add", "def": d, "ws": "~/team", "name": "w-02"}, env_extra=self.env)


class Escapes(Base):
    def setUp(self):
        super().setUp()
        self.allow = []   # only AOS_WS
        self.outside = os.path.join(self.tmp.name, "outside")
        os.makedirs(self.outside)

    def test_symlink_out_of_ws_blocked(self):
        os.symlink(self.outside, os.path.join(self.ws, "link"))
        out = self.blocked("write", {"path": "link/a.txt"})
        self.assertIn("outside the folders you may write", out)
        self.blocked("move", {"from": "a", "to": "link/b"})

    def test_dotdot_out_of_ws_blocked(self):
        self.blocked("write", {"path": "../outside/a.txt"})
        self.blocked("write", {"path": "sub/../../outside/a.txt"})

    def test_inside_ws_allowed(self):
        self.allowed("write", {"path": "sub/../a.txt"})
        os.makedirs(os.path.join(self.ws, "real"))
        os.symlink(os.path.join(self.ws, "real"), os.path.join(self.ws, "inlink"))
        self.allowed("write", {"path": "inlink/a.txt"})


class Mail(Base):
    def setUp(self):
        super().setUp()
        t = self.tmp.name
        # a fake daemon stack: marker procs_state.json, its ctl mailbox, an agent with a mailbox, a kernel station
        self.daemon = os.path.join(t, "dstack")
        self.agent_box = os.path.join(self.daemon, "procs", "bob", "mailbox")
        self.station = os.path.join(self.daemon, "procs", "station")
        for d in (os.path.join(self.daemon, "ctlbox", "new"), self.agent_box, os.path.join(self.station, "requests", "new"),
                  os.path.join(self.daemon, "procs", "owner", "hookeds", "kernel_gate", "requests"),
                  os.path.join(t, "llm", "requests"), os.path.join(t, "noisy", "box")):
            os.makedirs(d)
        with open(os.path.join(self.daemon, "procs_state.json"), "w", encoding="utf-8") as f:
            json.dump({"procs_requests": "ctlbox", "procs": {"bob": {"stack": "procs/bob", "def": None},
                                                             "station": {"stack": "procs/station", "def": None}}}, f)
        self.env_base = {"AOS_DAEMON": self.daemon}   # bob is a row of the own daemon: its mailbox may be mailed

    def test_ctl_mailbox_blocked(self):
        out = self.blocked("mailbox_send", {"box": os.path.join(self.daemon, "ctlbox"), "status": "REQUEST", "title": "t", "what": "w"})
        self.assertIn("it is a control or kernel mailbox. Mail whoever gave you the task instead.", out)
        self.blocked("mailbox_send", {"box": os.path.join(self.daemon, "ctlbox", "new")})
        self.blocked("mailbox_send", {"box": os.path.join(self.tmp.name, "x", "procs_requests")})   # name alone is enough

    def test_kernel_mailbox_blocked(self):
        self.blocked("mailbox_send", {"box": os.path.join(self.station, "requests")})
        self.blocked("mailbox_send", {"box": os.path.join(self.daemon, "procs", "owner", "hookeds", "kernel_gate", "requests")})
        self.blocked("mailbox_send", {"box": os.path.join(self.tmp.name, "llm", "requests")})

    def test_kernel_env_blocked(self):
        k = os.path.join(self.tmp.name, "noisy", "box")
        self.blocked("mailbox_send", {"box": k}, env_extra={"AOS_KERNEL": k})
        self.blocked("mailbox_send", {"box": k}, env_extra={"AOS_LLM_KERNEL": os.path.join(self.tmp.name, "noisy")})
        self.assertIn("a box must be the mailbox of a proc", self.blocked("mailbox_send", {"box": k}))   # not on the table
        self.cfg["mail_allow_box"] = [os.path.join(self.tmp.name, "noisy")]
        self.write_cfg()
        self.allowed("mailbox_send", {"box": k})
        self.blocked("mailbox_send", {"box": k}, env_extra={"AOS_KERNEL": k})   # listed, but still a kernel mailbox

    def test_agent_mailbox_allowed(self):
        self.allowed("mailbox_send", {"box": self.agent_box, "in_reply_to": "l1", "status": "DONE", "title": "t", "what": "w"})
        self.allowed("mailbox_send", {"to": "bob", "status": "REQUEST", "title": "t", "what": "w"})

    def test_ctl_mailbox_via_symlink_and_relative(self):
        os.symlink(self.daemon, os.path.join(self.ws, "d"))
        self.blocked("mailbox_send", {"box": "d/ctlbox"})
        self.allowed("mailbox_send", {"box": "d/procs/bob/mailbox"})

    def test_mail_deny(self):
        self.cfg["mail_deny"] = [os.path.join(self.tmp.name, "noisy")]
        self.write_cfg()
        self.blocked("mailbox_send", {"box": os.path.join(self.tmp.name, "noisy", "box")})
        self.allowed("mailbox_send", {"box": self.agent_box})

    def test_mail_allow_to(self):
        self.cfg["mail_allow_to"] = "owner|w-[0-9]+"
        self.write_cfg()
        out = self.blocked("mailbox_send", {"to": "stranger", "status": "REQUEST", "title": "t", "what": "w"})
        self.assertIn("Mail whoever gave you the task instead.", out)
        self.blocked("mailbox_send", {"to": "owners"})            # fullmatch, not a prefix
        self.allowed("mailbox_send", {"to": "owner"})
        self.allowed("mailbox_send", {"to": "w-02"})

    def test_box_not_string(self):
        self.blocked("mailbox_send", {"box": ["x"]})


class WriteScopeOneSource(Base):
    # the write scope has one source: AOS_WS plus AOS_WRITE_ALLOW; write_roots in the config is refused
    def test_write_roots_refused(self):
        self.cfg["write_roots"] = [self.root]
        self.write_cfg()
        for name, args in (("write", {"path": os.path.join(self.root, "a")}), ("shell", {"command": "ls"}),
                           ("mailbox_send", {"to": "bob"})):
            with self.subTest(tool=name):
                code, out = self.run_guard(name, args)
                self.assertEqual(code, 1, out)
                self.assertEqual(out, "")
                self.assertIn("guard: error: CfgBad", self.last_err)
                self.assertIn("write_roots", self.last_err)
                self.assertIn("AOS_WRITE_ALLOW", self.last_err)

    def test_config_errors_are_errors(self):
        code, _ = self.run_guard("write", {"path": "a"}, env_extra={"AOS_GUARD_CFG": os.path.join(self.tmp.name, "nope.json")})
        self.assertEqual(code, 1)
        self.assertIn("CfgMissing", self.last_err)
        with open(self.cfg_path, "w", encoding="utf-8") as f:
            f.write("{not json")
        code, _ = self.run_guard("write", {"path": "a"})
        self.assertEqual(code, 1)
        self.assertIn("CfgBad", self.last_err)
        with open(self.cfg_path, "w", encoding="utf-8") as f:
            f.write("[]")
        code, _ = self.run_guard("write", {"path": "a"})
        self.assertEqual(code, 1)

    def test_bad_event_is_error(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        env.update(AOS_GUARD_CFG=self.cfg_path, AOS_WS=self.ws, AOS_STACK=self.stack)
        p = subprocess.run([sys.executable, GUARD], input="not json", capture_output=True, text=True, env=env, timeout=30)
        self.assertEqual(p.returncode, 1)
        self.assertIn("guard: error: ArgumentsBad", p.stderr)

    def test_ws_always_allowed(self):
        self.allow = []
        self.allowed("write", {"path": os.path.join(self.ws, "a.txt")})
        self.allowed("write", {"path": "sub/a.txt"})
        out = self.blocked("write", {"path": os.path.join(self.root, "a.txt")})
        self.assertIn("(AOS_WS=%s, AOS_WRITE_ALLOW not set)" % self.ws, out)

    def test_several_allow_entries_and_relative(self):
        other = os.path.join(self.tmp.name, "other")
        os.makedirs(other)
        os.makedirs(os.path.join(self.ws, "rel"))
        # a relative entry counts from AOS_WS (here "../other"); empty entries are skipped
        self.allow = [self.root, "", "../other"]
        self.allowed("write", {"path": os.path.join(self.root, "a")})
        self.allowed("write", {"path": os.path.join(other, "a")})
        self.blocked("write", {"path": os.path.join(self.tmp.name, "a")})

    def test_write_deny_env(self):
        secret = os.path.join(self.root, "secret")
        os.makedirs(secret)
        env = {"AOS_WRITE_DENY": os.pathsep.join([os.path.join(self.tmp.name, "nothing"), secret])}
        out = self.blocked("write", {"path": os.path.join(secret, "x")}, env_extra=env)
        self.assertIn("no agent may write (%s, from AOS_WRITE_DENY)" % secret, out)
        self.allowed("write", {"path": os.path.join(self.root, "x")}, env_extra=env)

    def test_no_config_defaults(self):
        # AOS_GUARD_CFG unset: no config; file tools follow the scope, the tools that need a rule are blocked
        none = {"AOS_GUARD_CFG": None}
        self.allowed("write", {"path": os.path.join(self.root, "a")}, env_extra=none)
        self.blocked("write", {"path": os.path.join(self.tmp.name, "a")}, env_extra=none)
        self.blocked("write", {"path": os.path.join(self.root, ".git", "x")}, env_extra=none)
        out = self.blocked("shell", {"command": "ls"}, env_extra=none)
        self.assertIn("no shell rules", out)
        self.blocked("run_python", {"code": "print(1)"}, env_extra=none)
        self.blocked("subagent", {"op": "ls"}, env_extra=none)
        self.blocked("kernel_gate", {"op": "ls"}, env_extra=none)
        self.blocked("agents_ctl", {"op": "stop"}, env_extra=none)
        self.allowed("mailbox_send", {"to": "bob"}, env_extra=none)
        self.allowed("clock_register", {}, env_extra=none)
        self.blocked("clock_register", {"box": self.box}, env_extra=none)

    def test_empty_shell_deny_is_a_rule(self):
        self.cfg["shell_deny"] = []
        self.write_cfg()
        self.allowed("shell", {"command": "git commit -m x"})

    def test_subagent_name_without_pattern(self):
        del self.cfg["subagent"]["name"]
        self.write_cfg()
        self.allowed("subagent", {"op": "add", "def": self.defdir, "ws": "team", "name": "anything"})

    def test_subagent_name_message(self):
        out = self.blocked("subagent", {"op": "add", "def": self.defdir, "ws": "team", "name": "bob"})
        self.assertIn("the name must match w-[0-9]+", out)


class DefinitionDeny(Base):
    # the agent's definition folder, from its row in $AOS_DAEMON/procs_state.json, may not be written
    def setUp(self):
        super().setUp()
        t = self.tmp.name
        self.daemon = os.path.join(t, "dstack")
        self.stack = os.path.join(self.daemon, "procs", "w-01")
        self.mydef = os.path.join(self.root, "defs", "mine")       # inside AOS_WRITE_ALLOW on purpose
        self.otherdef = os.path.join(self.root, "defs", "other")
        for d in (self.stack, self.mydef, self.otherdef, os.path.join(self.daemon, "procs", "w-02")):
            os.makedirs(d)
        self.table({"w-01": {"stack": "procs/w-01", "def": self.mydef, "phase": "running"},
                    "w-02": {"stack": "procs/w-02", "def": self.otherdef}})
        self.env = {"AOS_DAEMON": self.daemon}

    def table(self, procs, shard=False):
        st = {"procs_requests": "procs_requests", "procs": procs}
        if shard:
            with open(os.path.join(self.daemon, "procs.1.json"), "w", encoding="utf-8") as f:
                json.dump(procs, f)
            st["procs"] = {"$ref": ["procs.1.json"]}
        with open(os.path.join(self.daemon, "procs_state.json"), "w", encoding="utf-8") as f:
            json.dump(st, f)

    def test_own_definition_blocked(self):
        out = self.blocked("write", {"path": os.path.join(self.mydef, "system.txt")}, env_extra=self.env)
        self.assertIn("no agent may write (%s, from definition)" % self.mydef, out)
        # another row's definition: blocked too (it used to be allowed)
        out = self.blocked("write", {"path": os.path.join(self.otherdef, "system.txt")}, env_extra=self.env)
        self.assertIn("no agent may write (%s, from daemon-table)" % self.otherdef, out)
        self.allowed("write", {"path": os.path.join(self.root, "defs", "x")}, env_extra=self.env)

    def test_from_hook_cell(self):
        cell = os.path.join(self.stack, "hookeds", "guard")
        os.makedirs(cell)
        self.blocked("edit", {"path": os.path.join(self.mydef, "tools.json")}, stack=cell, env_extra=self.env)

    def test_relative_def_and_shards(self):
        rel = os.path.relpath(self.mydef, self.daemon)
        self.table({"w-01": {"stack": "procs/w-01", "def": rel}}, shard=True)
        self.blocked("write", {"path": os.path.join(self.mydef, "x")}, env_extra=self.env)

    def test_kernel_set_still_reads_table(self):
        # AOS_KERNEL set: the table file is read all the same (it used to skip the definition deny)
        p = os.path.join(self.mydef, "x")
        out = self.blocked("write", {"path": p}, env_extra=dict(self.env, AOS_KERNEL=os.path.join(self.tmp.name, "k")))
        self.assertIn("from definition", out)
        self.blocked("write", {"path": os.path.join(self.otherdef, "x")},
                     env_extra=dict(self.env, AOS_KERNEL=os.path.join(self.tmp.name, "k")))

    def test_without_table(self):
        p = os.path.join(self.mydef, "x")
        self.allowed("write", {"path": p})                                        # no AOS_DAEMON, no marker
        os.symlink(self.daemon, os.path.join(self.ws, "dstack"))
        out = self.blocked("write", {"path": p}, env_extra={"AOS_DAEMON": "dstack"})   # relative: from AOS_WS
        self.assertIn("from definition", out)
        self.table({"w-03": {"stack": "procs/w-03", "def": self.otherdef}})
        self.allowed("write", {"path": p}, env_extra=self.env)                    # no row names mydef
        self.blocked("write", {"path": os.path.join(self.otherdef, "x")}, env_extra=self.env)
        with open(os.path.join(self.daemon, "procs_state.json"), "w", encoding="utf-8") as f:
            f.write("{broken")
        out = self.blocked("write", {"path": p}, env_extra=self.env)              # unreadable table: every write blocked
        self.assertIn("the daemon table (procs_state.json of AOS_DAEMON) cannot be read", out)
        self.blocked("write", {"path": os.path.join(self.ws, "x")}, env_extra=self.env)
        os.rename(os.path.join(self.daemon, "procs_state.json"), os.path.join(self.tmp.name, "moved.json"))
        # no table file (a real definition always has interfaces.json; here it has none on purpose: both backups missing)
        self.allowed("write", {"path": p}, env_extra=self.env)
        open(os.path.join(self.mydef, "interfaces.json"), "w").close()
        out = self.blocked("write", {"path": p}, env_extra=self.env)              # the marker still applies
        self.assertIn("rule: definition-marker", out)


class QueueMail(Base):
    # a letter into another agent's queue goes straight into its conversation: blocked; the agent's own queue is fine
    def setUp(self):
        super().setUp()
        t = self.tmp.name
        self.other = os.path.join(t, "procs", "w-02")
        for d in (os.path.join(self.other, "queue", "new"), os.path.join(self.other, "mailbox"),
                  os.path.join(self.stack, "queue", "new")):
            os.makedirs(d)
        dq = os.path.join(t, "dq")   # the own daemon: both stacks are rows of its table
        os.makedirs(dq)
        with open(os.path.join(dq, "procs_state.json"), "w", encoding="utf-8") as f:
            json.dump({"procs": {"w-01": {"stack": self.stack, "def": None}, "w-02": {"stack": self.other, "def": None}}}, f)
        self.env_base = {"AOS_DAEMON": dq}

    def test_foreign_queue_blocked(self):
        out = self.blocked("mailbox_send", {"box": os.path.join(self.other, "queue")})
        self.assertIn("another agent's queue (%s)" % os.path.join(self.other, "queue"), out)
        self.blocked("mailbox_send", {"box": os.path.join(self.other, "queue", "new")})
        os.symlink(self.other, os.path.join(self.ws, "o"))
        self.blocked("mailbox_send", {"box": "o/queue"})

    def test_foreign_mailbox_allowed(self):
        self.allowed("mailbox_send", {"box": os.path.join(self.other, "mailbox")})

    def test_own_queue_allowed(self):
        self.allowed("mailbox_send", {"box": os.path.join(self.stack, "queue")})
        cell = os.path.join(self.stack, "hookeds", "guard")
        os.makedirs(cell)
        self.allowed("mailbox_send", {"box": os.path.join(self.stack, "queue")}, stack=cell)

    def test_own_queue_needs_own_stack(self):
        self.blocked("mailbox_send", {"box": os.path.join(self.stack, "queue")}, stack=self.other)

    def test_foreign_queue_default_deny(self):
        # no mail_foreign_queue key = "deny"; "deny" written out is the same
        self.assertNotIn("mail_foreign_queue", self.cfg)
        self.blocked("mailbox_send", {"box": os.path.join(self.other, "queue")})
        self.cfg["mail_foreign_queue"] = "deny"
        self.write_cfg()
        self.blocked("mailbox_send", {"box": os.path.join(self.other, "queue")})

    def test_foreign_queue_allow(self):
        self.cfg["mail_foreign_queue"] = "allow"
        self.write_cfg()
        self.allowed("mailbox_send", {"box": os.path.join(self.other, "queue")})
        self.allowed("mailbox_send", {"box": os.path.join(self.other, "queue", "new")})
        # "allow" turns off only the queue check: control and kernel mailboxes stay blocked
        self.blocked("mailbox_send", {"box": os.path.join(self.tmp.name, "k", "requests")})
        self.blocked("mailbox_send", {"box": os.path.join(self.tmp.name, "d", "procs_requests")})

    def test_foreign_queue_bad_value(self):
        for bad in ("yes", "Allow", "", True, None, 1, ["allow"]):
            with self.subTest(value=bad):
                self.cfg["mail_foreign_queue"] = bad
                self.write_cfg()
                code, out = self.run_guard("mailbox_send", {"box": os.path.join(self.stack, "queue")})
                self.assertEqual(code, 1, out)
                self.assertEqual(out, "")
                self.assertIn("guard: error: CfgBad", self.last_err)
                self.assertIn("mail_foreign_queue", self.last_err)

    def test_own_queue_always_allowed(self):
        for v in (None, "deny", "allow"):
            with self.subTest(value=v):
                self.cfg.pop("mail_foreign_queue", None)
                if v is not None:
                    self.cfg["mail_foreign_queue"] = v
                self.write_cfg()
                self.allowed("mailbox_send", {"box": os.path.join(self.stack, "queue")})
                self.allowed("mailbox_send", {"box": os.path.join(self.stack, "queue", "new")})

    def test_clock_register_foreign_queue(self):
        # clock_register is an allow-list (clock_boxes): a foreign queue is blocked unless listed,
        # whatever mail_foreign_queue says
        q = os.path.join(self.other, "queue")
        for v in ("deny", "allow"):
            with self.subTest(value=v):
                self.cfg["mail_foreign_queue"] = v
                self.cfg["clock_boxes"] = [self.box]
                self.write_cfg()
                out = self.blocked("clock_register", {"box": q})
                self.assertIn("clock_register may only wake you", out)
                self.cfg["clock_boxes"] = [self.box, q]
                self.write_cfg()
                self.allowed("clock_register", {"box": q})


class ShellEnvTrust(Base):
    # with an untrusted shell environment the relaxed check is skipped: the strict regex runs on plain commands too
    CMD = "rg -n 'rm accepted' x"

    def test_trusted_env_relaxed(self):
        self.sh_ok(self.CMD)

    def test_risky_env_strict(self):
        cases = [{"BASH_ENV": "/tmp/x"}, {"ENV": "/tmp/x"}, {"RIPGREP_CONFIG_PATH": "/tmp/rgrc"},
                 {"BASH_FUNC_cat%%": "() { rm -rf x; }"}, {"BASH_ENV": ""},
                 {"PATH": "." + os.pathsep + os.environ.get("PATH", "/usr/bin")},
                 {"PATH": os.environ.get("PATH", "/usr/bin") + os.pathsep},
                 {"PATH": "bin" + os.pathsep + "/usr/bin"}]
        for env in cases:
            with self.subTest(env=env):
                out = self.blocked("shell", {"command": self.CMD}, env_extra=env)
                self.assertIn("strict check", out)
                self.assertIn("the shell environment is not trusted", out)

    def test_untrusted_env_still_allows_clean_text(self):
        self.allowed("shell", {"command": "cat x"}, env_extra={"BASH_ENV": "/tmp/x"})

    def test_untrusted_env_function(self):
        self.assertIsNone(G.untrusted_env({"PATH": "/usr/bin:/bin"}))
        self.assertIn("BASH_ENV", G.untrusted_env({"PATH": "/usr/bin", "BASH_ENV": "/x"}))
        self.assertEqual(G.untrusted_env({"PATH": "/usr/bin:./bin"}), "PATH has a relative or empty entry")
        self.assertEqual(G.untrusted_env({"PATH": "/usr/bin:"}), "PATH has a relative or empty entry")
        self.assertIn("BASH_FUNC_ls%%", G.untrusted_env({"PATH": "/usr/bin", "BASH_FUNC_ls%%": "() { :; }"}))


class NoEnvValues(Base):
    # messages name environment variables, never print their values (except write roots in a block message)
    def test_path_entry_not_printed(self):
        env = {"PATH": "relsecret" + os.pathsep + "/usr/bin"}
        self.assertNotIn("relsecret", G.untrusted_env(env))
        code, out = self.run_guard("shell", {"command": "rg -n 'rm accepted' x"}, env_extra=env)
        self.assertEqual(code, 10, out)
        self.assertIn("PATH has a relative or empty entry", out)
        for name, args in (("shell", {"command": "cat x"}), ("shell", {"command": "$(x)"}),
                           ("run_python", {"code": "rm x"}), ("write", {"path": "/nope/x"}),
                           ("mailbox_send", {"box": os.path.join(self.tmp.name, "k", "requests")})):
            with self.subTest(tool=name, args=args):
                self.run_guard(name, args, env_extra=env)
                self.assertNotIn("relsecret", self.last_out)
                self.assertNotIn("relsecret", self.last_err)

    def test_config_path_not_printed(self):
        missing = os.path.join(self.tmp.name, "cfgsecret.json")
        code, _ = self.run_guard("write", {"path": "a"}, env_extra={"AOS_GUARD_CFG": missing})
        self.assertEqual(code, 1)
        self.assertIn("CfgMissing", self.last_err)
        self.assertNotIn("cfgsecret", self.last_err)
        for text in ("{not json", "[]", json.dumps({"write_roots": ["/x"]}), json.dumps({"mail_foreign_queue": "x"})):
            with self.subTest(text=text):
                with open(self.cfg_path, "w", encoding="utf-8") as f:
                    f.write(text)
                code, out = self.run_guard("write", {"path": "a"})
                self.assertEqual(code, 1, out)
                self.assertIn("CfgBad", self.last_err)
                self.assertNotIn(self.cfg_path, self.last_err)
                self.assertNotIn(self.tmp.name, self.last_err)

    def test_agents_ctl_name_not_printed(self):
        out = self.blocked("agents_ctl", {"op": "stop", "name": "w-02", "timeout_s": 60, "no_wait": True},
                           stack=os.path.join(self.tmp.name, "procs", "stacksecret"))
        self.assertIn("AOS_STACK", out)
        self.assertNotIn("stacksecret", out)


class ProcStackRule(Base):
    # rule proc-stack: a live daemon stack can sit inside the workspace; no proc's stack (a neighbour's, the
    # daemon's own, a .stack) may be written with the file tools, and no config lifts that
    def setUp(self):
        super().setUp()
        self.allow = []   # only AOS_WS
        self.daemon = os.path.join(self.ws, "stacks", "root")
        self.other = os.path.join(self.daemon, "procs", "other")
        self.stack = os.path.join(self.daemon, "procs", "me")   # our own stack is a row of the same daemon
        for d in (self.other, self.stack, os.path.join(self.daemon, "procs_requests"),
                  os.path.join(self.ws, "src", "procs", "x")):
            os.makedirs(d)
        with open(os.path.join(self.daemon, "procs_state.json"), "w", encoding="utf-8") as f:
            json.dump({"procs_requests": "procs_requests", "procs": {"me": {"stack": "procs/me"},
                                                                     "other": {"stack": "procs/other"}}}, f)

    def msg(self, st):
        return "is inside a proc's stack (%s, rule: proc-stack). Stop and report this as BLOCKED." % st

    def test_neighbour_stack_blocked(self):
        out = self.blocked("write", {"path": os.path.join(self.other, "tools.json")})
        self.assertIn(self.msg(self.other), out)
        self.blocked("edit", {"path": "stacks/root/procs/other/hooks.json"})            # relative to AOS_WS
        self.blocked("mkdir", {"path": os.path.join(self.other, "hooks", "new", "deep")})
        self.blocked("json_set", {"path": os.path.join(self.other, "state.json") + "#/x"})
        out = self.blocked("write", {"path": os.path.join(self.daemon, "procs", "later", "x")})   # not made yet
        self.assertIn(self.msg(os.path.join(self.daemon, "procs", "later")), out)

    def test_daemon_stack_blocked(self):
        for p in ("procs_state.json", "procs_requests/l.json", "daemon.json", "procs", ""):
            out = self.blocked("write", {"path": os.path.join(self.daemon, p)})
            self.assertIn(self.msg(self.daemon.rstrip("/")), out)

    def test_dot_stack_blocked(self):
        out = self.blocked("write", {"path": "proj/.stack/history.json"})
        self.assertIn(self.msg(os.path.join(self.ws, "proj", ".stack")), out)
        self.blocked("mkdir", {"path": ".stack"})

    def test_ordinary_procs_folder_allowed(self):
        self.allowed("write", {"path": os.path.join(self.ws, "src", "procs", "x", "a.py")})
        self.allowed("write", {"path": "procs/y/b.txt"})
        self.allowed("write", {"path": "src/.stackish/a"})

    def test_multi_set_copy_move_checked(self):
        ok = os.path.join(self.ws, "a.json")
        bad = os.path.join(self.other, "b.json")
        self.blocked("json_multi_set", {"items": [{"path": ok, "value": 1}, {"path": bad + "#/k", "value": 1}]})
        self.allowed("json_multi_set", {"items": [{"path": ok, "value": 1}]})
        self.blocked("copy", {"from": ok, "to": bad})
        self.blocked("move", {"from": ok, "to": bad})
        self.blocked("move", {"from": bad, "to": ok})
        self.allowed("copy", {"from": bad, "to": ok})   # reading from a stack is not this guard's job

    def test_symlink_into_neighbour_blocked(self):
        os.symlink(self.other, os.path.join(self.ws, "peek"))
        out = self.blocked("write", {"path": "peek/tools.json"})
        self.assertIn(self.msg(self.other), out)
        os.symlink(os.path.join(self.other, "gone.json"), os.path.join(self.ws, "dangling"))
        self.blocked("write", {"path": "dangling"})

    def test_own_ws_allowed(self):
        self.allowed("write", {"path": "notes.txt"})
        self.allowed("edit", {"path": os.path.join(self.ws, "sub", "a.md")})
        self.allowed("mkdir", {"path": os.path.join(self.ws, "stacks", "other-notes")})

    def test_own_stack_still_named_by_deny(self):
        out = self.blocked("write", {"path": os.path.join(self.stack, "x")})
        self.assertIn("from AOS_STACK", out)

    def test_config_cannot_lift(self):
        self.cfg["deny_parts"] = []
        self.cfg["deny_roots"] = []
        self.write_cfg()
        self.allow = [self.daemon, self.other]
        self.blocked("write", {"path": os.path.join(self.other, "x")})
        self.blocked("write", {"path": os.path.join(self.daemon, "procs_state.json")})


class ScopeCli(Base):
    def test_entry_scope(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        env.update(AOS_GUARD_CFG=self.cfg_path, AOS_WS=self.ws, AOS_STACK=os.path.join(self.stack, "hookeds", "guard"),
                   AOS_WRITE_ALLOW=self.root)
        p = subprocess.run([sys.executable, GUARD, "--scope"], capture_output=True, text=True, env=env, timeout=30)
        self.assertEqual(p.returncode, 0, p.stderr)
        got = json.loads(p.stdout)
        self.assertEqual(got["allow"], [{"path": self.ws, "from": "AOS_WS"}, {"path": self.root, "from": "AOS_WRITE_ALLOW"}])
        self.assertEqual(got["deny"], [{"path": self.stack, "from": "AOS_STACK"}])
        self.assertEqual([r["name"] for r in got["rules"]],
                         ["deny_parts", "proc-stack", "definition-marker", "no-hash-outside-json", "no-tilde"])
        self.assertEqual(got["rules"][0]["parts"], [".git"])
        self.assertEqual(got["rules"][3]["json_tools"], ["json_set", "json_add", "json_del", "json_multi_set"])
        self.assertEqual(got["version"], 1)
        self.assertEqual(got["deny_parts"], [".git"])
        self.assertEqual(sorted(got), ["allow", "deny", "deny_parts", "rules", "version"])

    def test_entry_scope_deny_parts_from_config(self):
        self.cfg["deny_parts"] = [".git", ".hg"]
        self.write_cfg()
        env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        env.update(AOS_GUARD_CFG=self.cfg_path, AOS_WS=self.ws)
        p = subprocess.run([sys.executable, GUARD, "--scope"], capture_output=True, text=True, env=env, timeout=30)
        self.assertEqual(p.returncode, 0, p.stderr)
        got = json.loads(p.stdout)
        self.assertEqual(got["deny_parts"], [".git", ".hg"])
        self.assertEqual(got["rules"][0], {"name": "deny_parts", "parts": [".git", ".hg"]})

    def test_entry_scope_lists_everything_denied(self):
        # the daemon table's stacks and definitions, the daemon folder and the AOS_HOME folders are listed
        d = os.path.join(self.tmp.name, "dm")
        other_stack, other_def = os.path.join(self.tmp.name, "elsewhere", "st"), os.path.join(self.tmp.name, "od")
        home = os.path.join(self.tmp.name, "home")
        for p in (d, other_stack, other_def, os.path.join(home, "lib"), os.path.join(home, "knowledge")):
            os.makedirs(p)
        with open(os.path.join(d, "procs_state.json"), "w", encoding="utf-8") as f:
            json.dump({"procs": {"o": {"stack": other_stack, "def": other_def}}}, f)
        env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        env.update(AOS_GUARD_CFG=self.cfg_path, AOS_WS=self.ws, AOS_DAEMON=d, AOS_HOME=home)
        p = subprocess.run([sys.executable, GUARD, "--scope"], capture_output=True, text=True, env=env, timeout=30)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout)["deny"], [
            {"path": other_stack, "from": "daemon-table"}, {"path": other_def, "from": "daemon-table"},
            {"path": d, "from": "AOS_DAEMON"},
            {"path": os.path.join(home, "lib"), "from": "AOS_HOME"},
            {"path": os.path.join(home, "knowledge"), "from": "AOS_HOME"}])

    def test_entry_scope_refuses_write_roots(self):
        self.cfg["write_roots"] = [self.root]
        self.write_cfg()
        env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        env.update(AOS_GUARD_CFG=self.cfg_path, AOS_WS=self.ws)
        p = subprocess.run([sys.executable, GUARD, "--scope"], capture_output=True, text=True, env=env, timeout=30)
        self.assertEqual(p.returncode, 1)
        self.assertEqual(p.stdout, "")
        self.assertIn("CfgBad", p.stderr)

    def test_entry_bad_args(self):
        p = subprocess.run([sys.executable, GUARD, "--nope"], capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 1)
        self.assertIn("guard: error: ArgumentsBad", p.stderr)


NO_HASH = "# is not allowed in paths of this tool"
NO_TILDE = "use an absolute path or one relative to AOS_WS"


class HashOutsideJson(Base):
    # item 1: only the json tools cut FILE#/POINTER; every other file tool takes # literally, so the guard blocks it
    def setUp(self):
        super().setUp()
        self.allow = []   # only AOS_WS

    def test_write_hash_blocked(self):
        for p in ("#/../x", "#/../../../x/hooks.json", "a#b", "sub/#"):
            with self.subTest(path=p):
                out = self.blocked("write", {"path": p, "content": "x"})
                self.assertIn(NO_HASH, out)

    def test_edit_mkdir_trash_remove_blocked(self):
        self.assertIn(NO_HASH, self.blocked("edit", {"path": "a#/../../x"}))
        self.assertIn(NO_HASH, self.blocked("mkdir", {"path": "d#/../../x"}))
        self.assertIn(NO_HASH, self.blocked("trash", {"path": "#/x"}))
        self.assertIn(NO_HASH, self.blocked("remove", {"path": "#/../y"}))

    def test_move_copy_blocked(self):
        self.assertIn(NO_HASH, self.blocked("move", {"from": "#/../a", "to": "b"}))
        self.assertIn(NO_HASH, self.blocked("move", {"from": "a", "to": "#/../../b"}))
        self.assertIn(NO_HASH, self.blocked("copy", {"from": "a", "to": "x#/../../b"}))
        self.assertIn(NO_HASH, self.blocked("copy", {"from": "a#/../b", "to": "b"}))   # copy.from is read: syntax rules only
        self.assertIn(NO_TILDE, self.blocked("copy", {"from": "~/a", "to": "b"}))
        self.allowed("copy", {"from": "a", "to": "b"})
        self.allowed("copy", {"from": "/etc/hostname", "to": "b"})                        # reading anywhere is not the guard's business

    def test_json_tools_still_split(self):
        self.allowed("json_set", {"path": "x.json#/a"})
        self.allowed("json_add", {"path": os.path.join(self.ws, "x.json") + "#/a/-"})
        self.allowed("json_del", {"path": "x.json#/a"})
        self.allowed("json_multi_set", {"items": [{"path": "x.json#/a", "value": 1}]})
        self.blocked("json_set", {"path": "../x.json#/a"})                  # the file part is checked
        out = self.blocked("json_set", {"path": "#/../x"})                  # no file name before #
        self.assertIn("no file name before #", out)
        self.blocked("json_multi_set", {"items": [{"path": "x.json#/a"}, {"path": "#/a"}]})


class KeepFiles(Base):
    # item 2: a keep file name is opened for append (created) by the mail tools, so it gets the write check
    def test_mailbox_read_keep(self):
        out = self.blocked("mailbox_read", {"keep": os.path.join(self.tmp.name, "elsewhere.jsonl")})
        self.assertIn("outside the folders you may write", out)
        out = self.blocked("mailbox_read", {"keep": os.path.join(self.stack, "hookeds.json")})
        self.assertIn("from AOS_STACK", out)
        self.assertIn(NO_HASH, self.blocked("mailbox_read", {"keep": "#/../../x"}))
        self.blocked("mailbox_read", {"keep": "../x.jsonl"})
        self.blocked("mailbox_read", {"keep": 3})
        os.makedirs(os.path.join(self.ws, "notes"))
        self.allowed("mailbox_read", {"keep": "notes/x.jsonl"})
        self.allowed("mailbox_read", {"keep": True})
        self.allowed("mailbox_read", {"keep": False, "all": True})
        self.allowed("mailbox_read", {})

    def test_mailbox_send_keep(self):
        base = {"to": "bob", "status": "DONE", "title": "t", "what": "w"}
        self.blocked("mailbox_send", dict(base, keep=os.path.join(self.tmp.name, "elsewhere.jsonl")))
        out = self.blocked("mailbox_send", dict(base, keep=os.path.join(self.stack, "x.jsonl")))
        self.assertIn("from AOS_STACK", out)
        self.allowed("mailbox_send", dict(base, keep="notes/x.jsonl"))
        self.allowed("mailbox_send", dict(base, keep=False))
        # true is not a mode of mailbox_send (its _entry would pass it on as --keep-to True)
        self.assertIn("keep of mailbox_send is a file name", self.blocked("mailbox_send", dict(base, keep=True)))
        self.blocked("mailbox_send", dict(base, keep=3))

    def test_keep_into_neighbour_stack(self):
        d = os.path.join(self.ws, "d")
        os.makedirs(os.path.join(d, "procs", "bo"))
        open(os.path.join(d, "procs_state.json"), "w").close()
        out = self.blocked("mailbox_read", {"keep": "d/procs/bo/history.jsonl"})
        self.assertIn("rule: proc-stack", out)


class DaemonTable(Base):
    # items 3+4: every row's stack and definition and the whole daemon folder are denied; the marker rules stay
    def setUp(self):
        super().setUp()
        self.allow = []   # only AOS_WS; everything below is inside it on purpose
        w = self.ws
        self.daemon = os.path.join(w, "dm")
        self.stack = os.path.join(self.daemon, "procs", "me")
        self.other_stack = os.path.join(w, "custom", "bo")      # not under procs/, no .stack part
        self.mydef = os.path.join(w, "defs", "me")
        self.otherdef = os.path.join(w, "defs", "bo")           # no interfaces.json
        for d in (self.stack, self.other_stack, self.mydef, self.otherdef):
            os.makedirs(d)
        with open(os.path.join(self.daemon, "procs_state.json"), "w", encoding="utf-8") as f:
            json.dump({"procs": {"me": {"stack": "procs/me", "def": self.mydef},
                                 "bo": {"stack": self.other_stack, "def": self.otherdef}}}, f)
        self.env = {"AOS_DAEMON": self.daemon}

    def test_other_rows_stack_blocked(self):
        out = self.blocked("write", {"path": "custom/bo/hooks.json"}, env_extra=self.env)
        self.assertIn("no agent may write (%s, from daemon-table)" % self.other_stack, out)
        self.blocked("mkdir", {"path": "custom/bo/queue/new/x"}, env_extra=self.env)
        self.allowed("write", {"path": "custom/notes.txt"}, env_extra=self.env)

    def test_other_rows_def_blocked(self):
        out = self.blocked("edit", {"path": "defs/bo/tools.json"}, env_extra=self.env)
        self.assertIn("no agent may write (%s, from daemon-table)" % self.otherdef, out)
        self.blocked("json_set", {"path": "defs/bo/hooks.json#/guard"}, env_extra=self.env)

    def test_daemon_stack_file_blocked(self):
        out = self.blocked("write", {"path": "dm/procs_ctl.json"}, env_extra=self.env)
        self.assertIn("no agent may write (%s, from AOS_DAEMON)" % self.daemon, out)
        # the daemon folder is denied as a whole even without its marker file
        os.rename(os.path.join(self.daemon, "procs_state.json"), os.path.join(self.ws, "moved.json"))
        out = self.blocked("write", {"path": "dm/procs_ctl.json"}, env_extra=self.env)
        self.assertIn("no agent may write (%s, from AOS_DAEMON)" % self.daemon, out)

    def test_shards(self):
        with open(os.path.join(self.daemon, "procs.1.json"), "w", encoding="utf-8") as f:
            json.dump({"bo": {"stack": self.other_stack, "def": "../defs/bo"}}, f)
        with open(os.path.join(self.daemon, "procs_state.json"), "w", encoding="utf-8") as f:
            json.dump({"procs": {"$ref": ["procs.1.json"]}}, f)
        self.blocked("write", {"path": "defs/bo/x"}, env_extra=self.env)
        self.blocked("write", {"path": "custom/bo/x"}, env_extra=self.env)

    def test_table_missing_definition_marker(self):
        # no AOS_DAEMON: the table is not read; a folder holding interfaces.json is still a definition
        lead = os.path.join(self.ws, "team", "defs", "gather")
        os.makedirs(os.path.join(lead, "screen"))
        open(os.path.join(lead, "interfaces.json"), "w").close()
        out = self.blocked("write", {"path": "team/defs/gather/tools.json"})
        self.assertIn("is inside an agent definition (%s holds interfaces.json, rule: definition-marker)" % lead, out)
        self.blocked("mkdir", {"path": "team/defs/gather/screen/new"})
        self.blocked("write", {"path": "team/defs/gather/interfaces.json"})
        self.allowed("write", {"path": "team/defs/other/tools.json"})
        self.allowed("write", {"path": "defs/bo/x"})   # no table, no marker: an ordinary folder

    def test_kernel_set_own_def_blocked(self):
        env = dict(self.env, AOS_KERNEL=os.path.join(self.tmp.name, "k"))
        out = self.blocked("write", {"path": "defs/me/system.txt"}, env_extra=env)
        self.assertIn("no agent may write (%s, from definition)" % self.mydef, out)

    def test_config_cannot_lift(self):
        self.cfg["deny_roots"] = []
        self.cfg["deny_parts"] = []
        self.write_cfg()
        self.allow = [self.otherdef, self.other_stack]
        self.blocked("write", {"path": os.path.join(self.otherdef, "x")}, env_extra=self.env)
        self.blocked("write", {"path": os.path.join(self.other_stack, "x")}, env_extra=self.env)


class HomeFolders(Base):
    # item 5: with AOS_HOME set, its product folders (those that exist) are denied
    def setUp(self):
        super().setUp()
        self.home = os.path.join(self.tmp.name, "aoshome")
        for p in ("lib", "bin", "templates", "knowledge", "ws"):
            os.makedirs(os.path.join(self.home, p))
        self.allow = [self.home]
        self.env = {"AOS_HOME": self.home}

    def test_product_folders_blocked(self):
        for p in ("lib", "bin", "templates", "knowledge"):
            with self.subTest(folder=p):
                out = self.blocked("write", {"path": os.path.join(self.home, p, "x", "y.py")}, env_extra=self.env)
                self.assertIn("no agent may write (%s, from AOS_HOME)" % os.path.join(self.home, p), out)
        self.allowed("write", {"path": os.path.join(self.home, "ws", "x")}, env_extra=self.env)
        self.allowed("write", {"path": os.path.join(self.home, "cpp", "x")}, env_extra=self.env)   # no such folder
        self.allowed("write", {"path": os.path.join(self.home, "lib", "x")})                         # AOS_HOME unset

    def test_symlinked_home(self):
        link = os.path.join(self.tmp.name, "h")
        os.symlink(self.home, link)
        self.blocked("write", {"path": os.path.join(self.home, "lib", "x")}, env_extra={"AOS_HOME": link})


class DaemonArg(Base):
    # item 6: mailbox_send / clock_register daemon only when absent or equal to realpath(AOS_DAEMON)
    def setUp(self):
        super().setUp()
        self.own = os.path.join(self.tmp.name, "own-d")
        self.foreign = os.path.join(self.tmp.name, "foreign-d")
        os.makedirs(self.own)
        os.makedirs(self.foreign)
        self.env = {"AOS_DAEMON": self.own}
        self.mail = {"to": "bob", "status": "REQUEST", "title": "t", "what": "w"}

    def test_mailbox_send_daemon(self):
        self.allowed("mailbox_send", self.mail, env_extra=self.env)
        self.allowed("mailbox_send", dict(self.mail, daemon=self.own), env_extra=self.env)
        os.symlink(self.own, os.path.join(self.ws, "d"))
        self.allowed("mailbox_send", dict(self.mail, daemon="d"), env_extra=self.env)     # relative, via a link
        out = self.blocked("mailbox_send", dict(self.mail, daemon=self.foreign), env_extra=self.env)
        self.assertIn("may only use your own daemon (AOS_DAEMON)", out)
        self.blocked("mailbox_send", dict(self.mail, daemon=self.own))                      # AOS_DAEMON unset
        self.blocked("mailbox_send", dict(self.mail, daemon=["x"]), env_extra=self.env)
        self.blocked("mailbox_send", dict(self.mail, daemon="~/own-d"), env_extra=self.env)

    def test_clock_register_daemon(self):
        self.allowed("clock_register", {"op": "ls"}, env_extra=self.env)
        self.allowed("clock_register", {"op": "ls", "daemon": self.own}, env_extra=self.env)
        out = self.blocked("clock_register", {"op": "rm", "name": "x", "daemon": self.foreign}, env_extra=self.env)
        self.assertIn("clock_register may only use your own daemon", out)
        self.blocked("clock_register", {"op": "ls", "daemon": self.own})


class UnknownTools(Base):
    # item 7: a tool name the guard has no rule for is blocked
    def test_unknown_blocked(self):
        for name in ("made_up_tool", "jsonx_set", "jsonx_multi_set", "read", "self_hook", "agent_def", None):
            with self.subTest(tool=name):
                out = self.blocked(name, {"path": "a.txt", "content": "x"})
                self.assertIn("guard has no rule for this tool", out)
                self.assertIn("remove it from the hook's condition or add a rule", out)

    def test_known_still_allowed(self):
        self.allowed("write", {"path": "a.txt"})
        self.allowed("mailbox_read", {})


class WsWrite(Base):
    # ws_write has a rule: the same check as write.path (scope, rules, no #, no leading ~)
    def setUp(self):
        super().setUp()
        self.allow = []

    def test_ws_write_checked_like_write(self):
        self.allowed("ws_write", {"path": "notes/report.md", "content": "x"})
        out = self.blocked("ws_write", {"path": os.path.join(self.tmp.name, "elsewhere.txt"), "content": "x"})
        self.assertIn("outside the folders you may write", out)
        self.assertIn(NO_HASH, self.blocked("ws_write", {"path": "#/../x", "content": "x"}))
        self.assertIn(NO_TILDE, self.blocked("ws_write", {"path": "~/x", "content": "x"}))
        self.assertIn("from AOS_STACK", self.blocked("ws_write", {"path": os.path.join(self.stack, "x"), "content": "x"}))
        self.blocked("ws_write", {"path": "../x", "content": "x"})
        self.blocked("ws_write", {"content": "x"})

    def test_known_tools_list(self):
        self.assertIn("ws_write", G.KNOWN_TOOLS)
        self.assertFalse([n for n in G.KNOWN_TOOLS if n.startswith("jsonx_")])


class PortedRepro(Base):
    # cases of an independent repro, ported; the guard is stricter on one point: any # outside the json tools is
    # blocked (the repro allowed a # inside a plain file name)
    def test_hash_is_part_of_the_path_for_file_tools(self):
        self.blocked("write", {"path": "#/../../escaped.txt"})
        self.blocked("write", {"path": "#/../escaped-1.txt", "content": "x"})
        self.blocked("edit", {"path": "a#/../../escaped.txt"})
        self.blocked("mkdir", {"path": "#/../../d"})
        self.blocked("move", {"from": "a.txt", "to": "#/../../b.txt"})
        self.assertIn(NO_HASH, self.blocked("write", {"path": "a#b.txt"}))   # stricter than the repro
        self.blocked("write", {"path": os.path.join(self.tmp.name, "outside-abs.txt"), "content": "x"})   # control

    def test_json_tools_still_split_at_hash(self):
        self.allowed("json_set", {"path": "x.json#/a/../../b"})   # right of # is a JSON pointer, not a path
        self.allowed("json_multi_set", {"items": [{"path": "x.json#/../../b"}]})
        self.blocked("json_set", {"path": "../x.json#/a"})

    def test_mail_keep_file_is_checked(self):
        out = self.blocked("mailbox_read", {"keep": os.path.join(self.tmp.name, "elsewhere.jsonl")})
        self.assertIn("outside the folders you may write", out)
        self.blocked("mailbox_read", {"all": True, "keep": "../elsewhere.jsonl"})
        self.blocked("mailbox_send", {"to": "bob", "status": "DONE", "title": "t", "what": "w", "keep": "../x.jsonl"})
        mb = os.path.join(self.stack, "mailbox")
        os.makedirs(mb)
        self.blocked("mailbox_send", {"box": mb, "status": "PROGRESS", "title": "t", "what": "w",
                                       "keep": os.path.join(self.tmp.name, "outside-keep2.jsonl")})

    def test_mail_keep_inside_or_boolean_allowed(self):
        self.allowed("mailbox_read", {})
        self.allowed("mailbox_read", {"keep": True})
        self.allowed("mailbox_read", {"keep": "mail/letters.jsonl"})
        self.allowed("mailbox_send", {"to": "bob", "status": "DONE", "title": "t", "what": "w", "keep": "mail/sent.jsonl"})


class EntryItself(Base):
    # trash, remove, copy and move act on the entry itself, not on where a final link points: both places are checked
    def test_link_inside_stack_pointing_to_ws(self):
        target = os.path.join(self.ws, "t")
        os.makedirs(target)
        link = os.path.join(self.stack, "lnk")
        os.symlink(target, link)
        self.allow = [self.tmp.name]
        out = self.blocked("remove", {"path": link})
        self.assertIn("from AOS_STACK", out)
        self.blocked("move", {"from": link, "to": os.path.join(self.ws, "u")})
        self.blocked("trash", {"path": link + "/"})
        self.allowed("remove", {"path": target})


def mailbox(path):
    for sub in ("tmp", "new", "cur"):
        os.makedirs(os.path.join(path, sub))
    return path


class BoxOwnTree(Base):
    # review r2, new 1: a mailbox_send box only on the own tree: a row's mailbox on the own daemon table, the agent
    # itself, the workspace, or mail_allow_box; another tree's mailbox and the user zone are blocked by default
    def setUp(self):
        super().setUp()
        t = self.tmp.name
        self.daemon = os.path.join(t, "dm")
        self.stack = os.path.join(self.daemon, "procs", "crew-1")
        self.lead = os.path.join(t, "lead-stack")                     # a lead with a stack outside procs/
        self.lead_box = mailbox(os.path.join(self.lead, "mailbox"))
        self.own_box = mailbox(os.path.join(self.stack, "mailbox"))
        with open(os.path.join(self.daemon, "procs_state.json"), "w", encoding="utf-8") as f:
            json.dump({"procs": {"crew-1": {"stack": "procs/crew-1", "def": None},
                                 "lead": {"stack": self.lead, "def": os.path.join(t, "defs", "lead")}}}, f)
        self.foreign_d = os.path.join(t, "other-tree", "dm")             # another tree's daemon and agent
        self.foreign_box = mailbox(os.path.join(self.foreign_d, "procs", "x", "mailbox"))
        with open(os.path.join(self.foreign_d, "procs_state.json"), "w", encoding="utf-8") as f:
            json.dump({"procs": {"x": {"stack": "procs/x", "def": None}}}, f)
        self.user_zone = mailbox(os.path.join(t, "home", ".aos", "user", "inbox"))
        self.env_base = {"AOS_DAEMON": self.daemon}
        self.mail = {"status": "DONE", "title": "t", "what": "w"}

    def to_box(self, box, **kw):
        return dict(self.mail, box=box, **kw)

    def test_crew_reports_to_lead(self):
        # the reply_to of the lead's letter: <lead stack>/mailbox, absolute (aos-mailbox joins it to the receiving box)
        self.allowed("mailbox_send", self.to_box(self.lead_box, in_reply_to="l1"))
        reply_to = os.path.normpath(os.path.join(self.own_box, os.path.relpath(self.lead_box, self.own_box)))
        self.allowed("mailbox_send", self.to_box(reply_to))
        self.allowed("mailbox_send", self.to_box(self.lead_box + "/"))
        self.allowed("mailbox_send", dict(self.mail, to="lead"))     # by name: always the own daemon

    def test_own_mailbox_and_workspace(self):
        self.allowed("mailbox_send", self.to_box(self.own_box))
        self.allowed("mailbox_send", self.to_box(self.own_box), stack=os.path.join(self.stack, "hookeds", "guard"))
        mailbox(os.path.join(self.ws, "outbox"))
        self.allowed("mailbox_send", self.to_box("outbox"))

    def test_other_tree_blocked(self):
        out = self.blocked("mailbox_send", self.to_box(self.foreign_box))
        self.assertIn("you may not mail %s: a box must be the mailbox of a proc on your own daemon's table" % self.foreign_box, out)
        os.symlink(self.foreign_box, os.path.join(self.ws, "fb"))     # a link in the workspace is judged by its target
        self.blocked("mailbox_send", self.to_box("fb"))
        self.blocked("mailbox_send", self.to_box(os.path.join(self.ws, "..", "other-tree", "dm", "procs", "x", "mailbox")))
        # a row's stack itself, or a folder in it other than the mailbox, is no mailbox
        self.blocked("mailbox_send", self.to_box(self.lead))
        self.blocked("mailbox_send", self.to_box(os.path.join(self.lead, "notes")))
        self.blocked("mailbox_send", self.to_box(os.path.join(self.lead, "mailbox-x")))

    def test_user_zone_only_when_listed(self):
        out = self.blocked("mailbox_send", self.to_box(self.user_zone))
        self.assertIn("mail_allow_box", out)
        self.cfg["mail_allow_box"] = ["~/.aos/user"]                   # config entries expand ~ (HOME)
        self.write_cfg()
        self.allowed("mailbox_send", self.to_box(self.user_zone), env_extra={"HOME": os.path.join(self.tmp.name, "home")})
        self.cfg["mail_allow_box"] = [os.path.join(self.tmp.name, "home", ".aos", "user")]
        self.write_cfg()
        self.allowed("mailbox_send", self.to_box(self.user_zone))
        self.blocked("mailbox_send", self.to_box(self.foreign_box))      # the list does not open other places

    def test_without_daemon(self):
        # no AOS_DAEMON: no table rows; only the agent itself, the workspace and mail_allow_box
        none = {"AOS_DAEMON": None}
        self.blocked("mailbox_send", self.to_box(self.lead_box), env_extra=none)
        self.allowed("mailbox_send", self.to_box(self.own_box), env_extra=none)
        os.rename(os.path.join(self.daemon, "procs_state.json"), os.path.join(self.tmp.name, "moved.json"))
        self.blocked("mailbox_send", self.to_box(self.lead_box))           # no table file: no rows
        self.allowed("mailbox_send", self.to_box(self.own_box))

    def test_foreign_daemon_rows_do_not_count(self):
        # the other daemon's rows count only for an agent of that daemon
        self.allowed("mailbox_send", self.to_box(self.foreign_box), env_extra={"AOS_DAEMON": self.foreign_d})
        self.blocked("mailbox_send", self.to_box(self.lead_box), env_extra={"AOS_DAEMON": self.foreign_d})

    def test_bad_config(self):
        for bad in ("/x", [3], [""], {"a": 1}):
            with self.subTest(value=bad):
                self.cfg["mail_allow_box"] = bad
                self.write_cfg()
                code, out = self.run_guard("mailbox_send", self.to_box(self.lead_box))
                self.assertEqual(code, 1, out)
                self.assertIn("guard: error: CfgBad mail_allow_box", self.last_err)

    def test_event_stack_mailbox(self):
        # the stack field of the hook event names the agent itself too
        ev_stack = os.path.join(self.tmp.name, "ev-stack")
        box = mailbox(os.path.join(ev_stack, "mailbox"))
        self.blocked("mailbox_send", self.to_box(box))
        self.allowed("mailbox_send", self.to_box(box), event={"stack": ev_stack})


class TableBad(Base):
    # review r2, new 3+4: a daemon table file that exists but cannot be read, or has a row without a stack string,
    # blocks every call that needs it (exit 10, not exit 1: the agent is not stopped); no table file = no rows
    def setUp(self):
        super().setUp()
        self.daemon = os.path.join(self.tmp.name, "dm")
        self.stack = os.path.join(self.daemon, "procs", "me")
        os.makedirs(self.stack)
        self.env_base = {"AOS_DAEMON": self.daemon}

    def table(self, text):
        with open(os.path.join(self.daemon, "procs_state.json"), "w", encoding="utf-8") as f:
            f.write(text if isinstance(text, str) else json.dumps(text))

    def test_broken_shapes_block(self):
        good = {"stack": "procs/me", "def": None}
        for bad in ("{broken", "", "[]", {"procs": []}, {"x": 1},
                    {"procs": {"me": good, "x": "junk"}},
                    {"procs": {"me": good, "bo": {"stack": {"$env": "AOS_X", "$path": "/bo"}, "def": None}}},
                    {"procs": {"me": good, "bo": {"def": None}}},
                    {"procs": {"me": good, "bo": {"stack": "", "def": None}}},
                    {"procs": {"me": good, "bo": {"stack": "procs/bo", "def": {"$env": "AOS_X"}}}},
                    {"procs": {"$ref": ["missing-shard.json"]}}):
            with self.subTest(table=bad):
                self.table(bad)
                out = self.blocked("write", {"path": "notes.md"})
                self.assertIn("the daemon table (procs_state.json of AOS_DAEMON) cannot be read", out)
                self.assertIn("Try once more", out)
                self.blocked("mailbox_send", {"box": os.path.join(self.stack, "mailbox")})

    def test_good_table_and_no_table(self):
        self.table({"procs": {"me": {"stack": "procs/me", "def": None}, "bo": {"stack": "procs/bo"}}})
        self.allowed("write", {"path": "notes.md"})
        self.blocked("write", {"path": os.path.join(self.daemon, "procs", "bo", "x")})
        os.rename(os.path.join(self.daemon, "procs_state.json"), os.path.join(self.tmp.name, "moved.json"))
        self.allowed("write", {"path": "notes.md"})                    # no file = no table (procs_state off)

    def test_scope_cli_refuses(self):
        self.table("{broken")
        env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        env.update(AOS_GUARD_CFG=self.cfg_path, AOS_WS=self.ws, AOS_DAEMON=self.daemon)
        p = subprocess.run([sys.executable, GUARD, "--scope"], capture_output=True, text=True, env=env, timeout=30)
        self.assertEqual(p.returncode, 1)
        self.assertEqual(p.stdout, "")
        self.assertIn("scope: error: TableBad", p.stderr)


class ArgTypes(Base):
    # review r2, new 6: an argument of a wrong type blocks (exit 10) instead of an error (exit 1), which with
    # on_error "stop" would stop the whole agent; a config of a wrong type is still CfgBad (exit 1)
    def test_wrong_argument_types_block(self):
        cases = [("json_multi_set", {"items": 5}), ("json_multi_set", {"items": True}),
                 ("json_multi_set", {"items": "ab"}), ("write", {"path": "a\u0000b"}),
                 ("mailbox_send", {"box": "a\u0000b"}), ("move", {"from": "a", "to": "b\u0000"}),
                 ("subagent", {"op": "history", "args": "x"}), ("subagent", {"op": ["add"]}),
                 ("kernel_gate", {"op": {"a": 1}}), ("agents_ctl", {"op": ["stop"]})]
        for name, args in cases:
            with self.subTest(tool=name, args=args):
                code, out = self.run_guard(name, args)
                self.assertEqual(code, 10, "expected blocked, got %d: %s %s" % (code, out, self.last_err))
                self.assertTrue(out.startswith("[aos] guard: blocked:"), out)

    def test_wrong_config_types_error(self):
        for key, bad in (("subagent", ["add"]), ("subagent", {"ops": ["ls"]}), ("kernel_gate", "on"),
                         ("agents_ctl", {"ops": "stop"}), ("agents_ctl", {"ops": ["stop"], "max_timeout_s": "9"}),
                         ("clock_boxes", [3]), ("mail_deny", "/x"), ("mail_allow_to", "("), ("mail_allow_to", 3),
                         ("shell_deny", ["("]), ("shell_deny", "rm")):
            with self.subTest(key=key, value=bad):
                self.cfg[key] = bad
                self.write_cfg()
                code, out = self.run_guard("write", {"path": "a.txt"})
                self.assertEqual(code, 1, out)
                self.assertIn("guard: error: CfgBad %s" % key, self.last_err)
                self.cfg = {}
                self.write_cfg()


class EventStack(Base):
    # review r2, new 7: the stack field of the hook event (written by the hook runner) is denied like AOS_STACK
    def test_event_stack_denied(self):
        ev = os.path.join(self.root, "tool-form", "agent")   # inside AOS_WRITE_ALLOW on purpose
        os.makedirs(ev)
        self.allowed("write", {"path": os.path.join(ev, "x")})
        out = self.blocked("write", {"path": os.path.join(ev, "x")}, event={"stack": ev})
        self.assertIn("no agent may write (%s, from event)" % ev, out)
        out = self.blocked("write", {"path": os.path.join(ev, "x")}, event={"stack": os.path.join(ev, "hookeds", "guard")})
        self.assertIn("from event", out)                       # a cell is cut as for AOS_STACK
        self.allowed("write", {"path": os.path.join(self.root, "y")}, event={"stack": ev})
        for bad in (3, ["x"], "a\u0000b"):
            with self.subTest(stack=bad):
                self.assertIn("stack field of the hook event", self.blocked("write", {"path": "a"}, event={"stack": bad}))


if __name__ == "__main__":
    unittest.main()
