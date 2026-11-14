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
CPP_RG = "rg -n -A 75 -B 18 'def sender_key_warnings|relative keys count from|test_missing_sender_folder_warns_once' src/a.py impls/aos-x/src/b.cpp tests/test_a.py impls/aos-x/tests/test_b.py"
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

    def run_guard(self, name, arguments, stack=None, env_extra=None):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("AOS_", "BASH_FUNC_")) and k not in G.RISKY_ENV}
        env.update(AOS_GUARD_CFG=self.cfg_path, AOS_WS=self.ws, AOS_STACK=stack or self.stack)
        if self.allow:
            env["AOS_WRITE_ALLOW"] = os.pathsep.join(self.allow)
        env.update(env_extra or {})
        env = {k: v for k, v in env.items() if v is not None}   # None = drop that variable
        p = subprocess.run([sys.executable, GUARD], input=json.dumps({"name": name, "arguments": arguments}),
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
        cell = os.path.join(self.stack, "hooks", "guard")
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
        # a hook runs with AOS_STACK = <stack>/hooks/<hook>; the whole agent stack is denied, not only the cell
        self.allow = [self.tmp.name]
        cell = os.path.join(self.stack, "hooks", "guard")
        os.makedirs(cell)
        self.blocked("write", {"path": os.path.join(self.stack, "hooks.json")}, stack=cell)
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

    def test_tilde_inside_allowed(self):
        self.allowed("write", {"path": "~/allowed/x"}, env_extra=self.env)
        self.allowed("json_set", {"path": "~/allowed/x.json#/a"}, env_extra=self.env)

    def test_tilde_outside_blocked(self):
        out = self.blocked("write", {"path": "~/y"}, env_extra=self.env)
        self.assertIn("outside the folders you may write", out)
        self.blocked("write", {"path": "~"}, env_extra=self.env)

    def test_tilde_not_taken_as_ws_folder(self):
        # without expansion "~/allowed/x" would be <ws>/~/allowed/x, inside AOS_WS; only <home>/allowed is
        # not allowed here, so a block proves the expansion
        self.allow = []
        self.blocked("write", {"path": "~/allowed/x"}, env_extra=self.env)

    def test_tilde_in_write_allow(self):
        self.allow = ["~/allowed"]
        self.allowed("write", {"path": os.path.join(self.home, "allowed", "x")}, env_extra=self.env)
        self.blocked("write", {"path": os.path.join(self.home, "x")}, env_extra=self.env)

    def test_tilde_clock_box(self):
        self.cfg["clock_boxes"] = ["~/box"]
        self.write_cfg()
        self.allowed("clock_register", {"box": "~/box"}, env_extra=self.env)
        self.allowed("clock_register", {"box": os.path.join(self.home, "box")}, env_extra=self.env)
        self.blocked("clock_register", {"box": "~/other"}, env_extra=self.env)

    def test_tilde_subagent_def(self):
        d = os.path.join(self.home, "defs", "w")
        os.makedirs(d)
        self.cfg["subagent"]["def"] = "~/defs/w"
        self.write_cfg()
        self.allowed("subagent", {"op": "add", "def": d, "ws": "team", "name": "w-02"}, env_extra=self.env)
        self.allowed("subagent", {"op": "add", "def": "~/defs/w", "ws": "team", "name": "w-02"}, env_extra=self.env)
        self.blocked("subagent", {"op": "add", "def": "~/defs/x", "ws": "team", "name": "w-02"}, env_extra=self.env)


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
                  os.path.join(self.daemon, "procs", "owner", "hooks", "kernel_gate", "requests"),
                  os.path.join(t, "llm", "requests"), os.path.join(t, "noisy", "box")):
            os.makedirs(d)
        with open(os.path.join(self.daemon, "procs_state.json"), "w", encoding="utf-8") as f:
            json.dump({"procs_requests": "ctlbox", "procs": {}}, f)

    def test_ctl_mailbox_blocked(self):
        out = self.blocked("mailbox_send", {"box": os.path.join(self.daemon, "ctlbox"), "status": "REQUEST", "title": "t", "what": "w"})
        self.assertIn("it is a control or kernel mailbox. Mail whoever gave you the task instead.", out)
        self.blocked("mailbox_send", {"box": os.path.join(self.daemon, "ctlbox", "new")})
        self.blocked("mailbox_send", {"box": os.path.join(self.tmp.name, "x", "procs_requests")})   # name alone is enough

    def test_kernel_mailbox_blocked(self):
        self.blocked("mailbox_send", {"box": os.path.join(self.station, "requests")})
        self.blocked("mailbox_send", {"box": os.path.join(self.daemon, "procs", "owner", "hooks", "kernel_gate", "requests")})
        self.blocked("mailbox_send", {"box": os.path.join(self.tmp.name, "llm", "requests")})

    def test_kernel_env_blocked(self):
        k = os.path.join(self.tmp.name, "noisy", "box")
        self.blocked("mailbox_send", {"box": k}, env_extra={"AOS_KERNEL": k})
        self.blocked("mailbox_send", {"box": k}, env_extra={"AOS_LLM_KERNEL": os.path.join(self.tmp.name, "noisy")})
        self.allowed("mailbox_send", {"box": k})

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
        self.allowed("write", {"path": os.path.join(self.otherdef, "system.txt")}, env_extra=self.env)

    def test_from_hook_cell(self):
        cell = os.path.join(self.stack, "hooks", "guard")
        os.makedirs(cell)
        self.blocked("edit", {"path": os.path.join(self.mydef, "tools.json")}, stack=cell, env_extra=self.env)

    def test_relative_def_and_shards(self):
        rel = os.path.relpath(self.mydef, self.daemon)
        self.table({"w-01": {"stack": "procs/w-01", "def": rel}}, shard=True)
        self.blocked("write", {"path": os.path.join(self.mydef, "x")}, env_extra=self.env)

    def test_skipped_without_reliable_table(self):
        p = os.path.join(self.mydef, "x")
        self.allowed("write", {"path": p})                                        # no AOS_DAEMON
        self.allowed("write", {"path": p}, env_extra=dict(self.env, AOS_KERNEL=os.path.join(self.tmp.name, "k")))
        self.allowed("write", {"path": p}, env_extra={"AOS_DAEMON": "dstack"})    # not absolute
        self.table({"w-03": {"stack": "procs/w-03", "def": self.mydef}})
        self.allowed("write", {"path": p}, env_extra=self.env)                    # not on the table
        with open(os.path.join(self.daemon, "procs_state.json"), "w", encoding="utf-8") as f:
            f.write("{broken")
        self.allowed("write", {"path": p}, env_extra=self.env)


class QueueMail(Base):
    # a letter into another agent's queue goes straight into its conversation: blocked; the agent's own queue is fine
    def setUp(self):
        super().setUp()
        t = self.tmp.name
        self.other = os.path.join(t, "procs", "w-02")
        for d in (os.path.join(self.other, "queue", "new"), os.path.join(self.other, "mailbox"),
                  os.path.join(self.stack, "queue", "new")):
            os.makedirs(d)

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
        cell = os.path.join(self.stack, "hooks", "guard")
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


class ScopeCli(Base):
    def test_entry_scope(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        env.update(AOS_GUARD_CFG=self.cfg_path, AOS_WS=self.ws, AOS_STACK=os.path.join(self.stack, "hooks", "guard"),
                   AOS_WRITE_ALLOW=self.root)
        p = subprocess.run([sys.executable, GUARD, "--scope"], capture_output=True, text=True, env=env, timeout=30)
        self.assertEqual(p.returncode, 0, p.stderr)
        got = json.loads(p.stdout)
        self.assertEqual(got["allow"], [{"path": self.ws, "from": "AOS_WS"}, {"path": self.root, "from": "AOS_WRITE_ALLOW"}])
        self.assertEqual(got["deny"], [{"path": self.stack, "from": "AOS_STACK"}])

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


if __name__ == "__main__":
    unittest.main()
