# test_guard - unittest for fsm-guard: runs guard as a subprocess with a temp guard.json (relaxed shell check, bypasses, old rules), and mounted in hookeds.json on the real agent-fsm act cell.
import importlib.machinery, importlib.util, json, os, subprocess, sys, tempfile, unittest

sys.dont_write_bytecode = True   # loading guard (a file without .py) must not leave __pycache__ next to it

HERE = os.path.dirname(os.path.abspath(__file__))
GUARD = os.path.join(os.path.dirname(HERE), "guard")

# worker shell_deny, verbatim from facts-B.md section 4
WORKER_DENY = [
    "\\bgit\\s+(commit|push|reset|checkout|restore|stash|clean|rebase|merge|switch|branch|tag|am|apply|cherry-pick|revert|rm|mv|add|config|worktree|remote|fetch|pull|gc|update-ref|update-index)\\b",
    "\\b(sudo|su|curl|wget|ssh|scp|nc|pkill|killall|kill)\\b",
    "\\baos-[a-z-]+",
    "\\brm\\s",
]

def load_guard():
    loader = importlib.machinery.SourceFileLoader("fsm_guard", GUARD)
    spec = importlib.util.spec_from_loader("fsm_guard", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod

G = load_guard()

# recorded false positives, exact text from facts-B.md section 5
T11 = "cd /home/lorkhan/code/misc-1114/src && cat proto8/cmd/aos-agent/aos_agent/ctl/set_def.py && cat proto8/cmd/aos-agent/aos_agent/ctl/rm.py && sed -n '135,205p' proto8/cmd/aos-agent/aos_agent/ctl/add.py && sed -n '90,180p' proto8/cmd/aos-agent/aos_agent/ctl/shared.py && rg -n 'def test_|set-def|rm accepted|set_def' proto8/cmd/aos-agent/tests/test_kernel* && sed -n '17,24p' proto8/cmd/aos-agent/README.md"
T14 = "cd /home/lorkhan/code/misc-1114/src && rg -n 'import process_group|from process_group|import cmd_call|from cmd_call' proto8/lib && rg -n 'ModuleMissing|tool_io.py|isolat|kill|signal' proto8/lib/agent/agent_def/tests proto8/lib/agent/self_ctl/tests proto8/lib/agent/mailbox_send/tests && ls -la proto8/lib/agent/tests && rg --files /home/lorkhan/code/misc-1114 | rg 'clean|check|\\.sh$'"
T15 = "cd /home/lorkhan/code/misc-1114/src && rg -n 'from daemon_ctl import|import daemon_ctl|\\bdaemon_ctl\\.[A-Za-z_]+|getattr\\(dc|patch.object\\(dc' proto8 -g '!*.html' -g '!*.md' -g '!*.csv' -g '!*.json' -g '!proto8/py/daemon_ctl/**' && printf '\\nAll package attribute names used outside package:\\n' && rg -o --no-filename '\\b(dc|daemon_ctl)\\.[A-Za-z_]+' proto8 -g '!proto8/py/daemon_ctl/**' -g '!*.html' -g '!*.md' -g '!*.csv' -g '!*.json' | sort -u && printf '\\nInitial daemon process list:\\n' && pgrep -u \"$USER\" -af aos-daemon"
CPP_RG = "rg -n -A 75 -B 18 'def sender_key_warnings|relative keys count from|test_missing_sender_folder_warns_once' proto8/lib/aos/kernel_llm/budget.py proto8/cpp/aos-llm-kernel/src/budget/budget.cpp proto8/lib/aos/kernel_llm/tests/test_two_machines.py proto8/cpp/aos-llm-kernel/tests/test_two_machines.py"
CPP = "cd /home/lorkhan/code/misc-1114/src && git --no-optional-locks status --short && " + CPP_RG


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = self.tmp.name
        self.ws = os.path.join(t, "ws")
        self.root = os.path.join(t, "root")
        self.box = os.path.join(t, "lead-box")
        self.defdir = os.path.join(t, "defs", "gpt-worker")
        self.stack = os.path.join(t, "procs", "sol-T01")
        for d in (self.ws, self.root, self.box, self.defdir, self.stack):
            os.makedirs(d)
        os.makedirs(os.path.join(self.root, ".git"))
        self.cfg = {
            "write_roots": [self.root],
            "deny_parts": [".git"],
            "shell_deny": WORKER_DENY,
            "subagent": {"ops": ["add", "ls", "rm", "history"], "def": self.defdir, "ws": "team", "name": "sol-[A-Za-z0-9-]+"},
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

    def run_guard(self, name, arguments, stack=None, event_stack=None):
        """stack = AOS_STACK the guard sees; event_stack = the event's "stack" field (left out when None)."""
        env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        env.update(AOS_GUARD_CFG=self.cfg_path, AOS_WS=self.ws, AOS_STACK=stack or self.stack)
        event = {"name": name, "arguments": arguments, "event": "before_tool", "hook": "guard"}
        if event_stack is not None:
            event["stack"] = event_stack
        p = subprocess.run([sys.executable, GUARD], input=json.dumps(event),
                           capture_output=True, text=True, env=env, timeout=30)
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
        """Not plain read-only (strict path). The worker regex itself may not catch it: that is today's regex, unchanged."""
        self.assertFalse(G.plain_read_only(cmd), "expected NOT plain read-only: %r" % cmd)


class RecordedFalsePositives(Base):
    def test_t11(self):
        self.sh_ok(T11)

    def test_t14(self):
        self.sh_ok(T14)

    def test_t15(self):
        self.sh_ok(T15)

    def test_cpp_path_rg_part_alone(self):
        self.sh_ok("cd /home/lorkhan/code/misc-1114/src && " + CPP_RG)

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
        "rg -n '\u4e2d\u6587 kill' .",
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
        # "ls | xargs rm": xargs is not plain; the worker regex \brm\s needs a blank after rm, so the
        # unchanged strict path lets this exact text through (known regex limit, the sandbox bounds it).
        self.not_plain("ls | xargs rm")


class ArgonBypasses(Base):
    # both Argon rounds (argon-1.txt, argon-2.txt, plan.md tables) and the plan's extra cases
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
        "caté rm x",
        "echo x; é kill 1",
    ]
    # bypasses where today's worker regex finds no denied word at all: only check the relaxed path refuses
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
    # ideas tried after the tests passed (ok-astra worker, 2026-11-14); every one must stay off the relaxed path
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
        "cat x; rm y",
        "cat x\x0b; rm y",
        "cat x\x00; rm y",
        "cat 'x\r'; rm y",
        "cat x; 　rm y",
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
    # found in lead review and Argon round 3 (ok-astra, 2026-11-14): uniq IN OUT writes OUT; date -s / MMDDhhmm set the clock;
    # an unquoted $NAME is split on IFS by bash, so it is never plain
    def test_not_plain(self):
        for cmd in ("uniq in out", "uniq -c in out", "uniq $X", "uniq a*", "uniq -- a b",
                    "date -s 2020-01-01", "date --set=2020-01-01", "date -s2020-01-01",
                    # Argon round 3
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
        self.assertIn("(strict check: a command skips it only if every part is a plain read-only command like rg, grep, cat, sed -n 'N,Mp', pgrep, with no substitutions or redirections; if this is a false positive, split the command or ask your lead)", out)


class OldRules(Base):
    def test_write_inside_allowed(self):
        self.allowed("write", {"path": os.path.join(self.root, "a.txt")})

    def test_write_outside_blocked(self):
        out = self.blocked("write", {"path": os.path.join(self.tmp.name, "elsewhere.txt")})
        self.assertIn("outside the folders you may write", out)

    def test_relative_path_from_ws_blocked(self):
        self.blocked("edit", {"path": "a.txt"})

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
        out = self.blocked("subagent", {"op": "add", "def": self.defdir, "ws": "team", "name": "sol-T02", "envs": {"X": "1"}})
        self.assertIn("may not set envs", out)

    def test_subagent_add_ok(self):
        self.allowed("subagent", {"op": "add", "def": self.defdir, "ws": "team", "name": "sol-T02"})

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
        self.allowed("agents_ctl", {"op": "stop", "name": "sol-T01", "timeout_s": 60, "no_wait": True})

    def test_agents_ctl_from_hook_cell(self):
        # what the hook engine gives: AOS_STACK = the hook's cell <stack>/hookeds/guard, event "stack" = the agent's stack
        cell = os.path.join(self.stack, "hookeds", "guard")
        os.makedirs(cell)
        stop = {"op": "stop", "name": "sol-T01", "timeout_s": 60, "no_wait": True}
        self.allowed("agents_ctl", stop, stack=cell, event_stack=self.stack)
        self.allowed("agents_ctl", stop, stack=cell)                  # no "stack" field: AOS_STACK cut by one cell
        self.blocked("agents_ctl", dict(stop, name="guard"), stack=cell, event_stack=self.stack)
        other = os.path.join(os.path.dirname(self.stack), "sol-T02")
        self.blocked("agents_ctl", stop, stack=cell, event_stack=other)   # the event's stack wins over AOS_STACK

    def test_agents_ctl_rules(self):
        self.blocked("agents_ctl", {"op": "start", "name": "sol-T01", "timeout_s": 60, "no_wait": True})
        self.blocked("agents_ctl", {"op": "stop", "name": "sol-T02", "timeout_s": 60, "no_wait": True})
        self.blocked("agents_ctl", {"op": "stop", "name": "sol-T01", "timeout_s": 0, "no_wait": True})
        self.blocked("agents_ctl", {"op": "stop", "name": "sol-T01", "timeout_s": 601, "no_wait": True})
        self.blocked("agents_ctl", {"op": "stop", "name": "sol-T01", "timeout_s": True, "no_wait": True})
        self.blocked("agents_ctl", {"op": "stop", "name": "sol-T01", "timeout_s": 60})
        self.blocked("agents_ctl", {"op": "stop", "name": "sol-T01", "timeout_s": 60, "no_wait": True, "force": True})

    def test_missing_rules_blocked(self):
        for k in ("subagent", "kernel_gate", "agents_ctl"):
            del self.cfg[k]
        self.write_cfg()
        self.blocked("subagent", {"op": "ls"})
        self.blocked("kernel_gate", {"op": "ls"})
        self.blocked("agents_ctl", {"op": "stop"})


PROTO = os.path.normpath(os.path.join(HERE, "..", "..", "..", "..", "..", "proto8"))   # this repo's proto8 (installed: lib/ bin/)


@unittest.skipUnless(os.path.isfile(os.path.join(PROTO, "templates", "agent-fsm", "act.py"))
                     and os.path.isdir(os.path.join(PROTO, "lib", "aos")), "needs an installed proto8 next to wf/")
class Mounted(unittest.TestCase):
    """Mount the guard as the README says (hookeds.json of a definition, wrapper + defs/shared/guard) and run the real act cell."""

    def setUp(self):
        import shutil
        self.tmp = tempfile.TemporaryDirectory()
        t = self.tmp.name
        self.ws, self.stack, fake = os.path.join(t, "ws"), os.path.join(t, "procs", "sol-T01"), os.path.join(t, "bin")
        self.defn = os.path.join(t, "defs", "worker")
        shutil.copytree(os.path.join(PROTO, "templates", "agent-fsm"), self.defn)
        os.makedirs(os.path.join(t, "defs", "shared"))
        shutil.copy(GUARD, os.path.join(t, "defs", "shared", "guard"))
        for d in (self.ws, self.stack, fake):
            os.makedirs(d)
        with open(os.path.join(self.defn, "guard"), "w") as f:
            f.write('#!/bin/sh\n# guard wrapper\nd=$(dirname "$0")\nAOS_GUARD_CFG="$d/guard.json" exec python3 "$d/../shared/guard"\n')
        os.chmod(os.path.join(self.defn, "guard"), 0o755)
        self.tools = ["write", "agents_ctl"]
        with open(os.path.join(self.defn, "hookeds.json"), "w") as f:   # only the guard: the shipped on_clock hooks need a daemon tree
            json.dump({"guard": {"event": "before_tool", "condition": self.tools, "handler": "guard", "timeout_ms": 10000}}, f)
        self.write_cfg({"write_roots": [self.ws], "agents_ctl": {"ops": ["stop"], "self_only": True, "max_timeout_s": 600}})
        listed = [{"name": n, "path": "/fake/" + n, "tooldef": {}} for n in self.tools]
        with open(os.path.join(fake, "aos-tools"), "w") as f:
            f.write("#!%s\nimport json, sys\nif 'ls' in sys.argv: print(json.dumps(%r))\n"
                    "else: sys.stdin.read(); print('TOOL RAN')\n" % (sys.executable, listed))
        os.chmod(os.path.join(fake, "aos-tools"), 0o755)
        env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        env.update(AOS_HOME=PROTO, AOS_STACK=self.stack, AOS_CD=self.defn, AOS_WS=self.ws,
                   PATH=os.pathsep.join([fake, os.path.join(PROTO, "bin"), env.get("PATH", "")]))
        self.env = env

    def tearDown(self):
        self.tmp.cleanup()

    def write_cfg(self, cfg):
        with open(os.path.join(self.defn, "guard.json"), "w") as f:
            json.dump(cfg, f)

    def act(self, tool, args, code=0):
        """Put one tool call at the end of history, run act.py; return (tool result or None, stderr)."""
        call = {"id": "c1", "type": "function", "function": {"name": tool, "arguments": json.dumps(args)}}
        hist = os.path.join(self.stack, "history.jsonl")
        with open(hist, "w") as f:
            f.write(json.dumps({"role": "user", "content": "hi"}) + "\n" + json.dumps({"role": "assistant", "tool_calls": [call]}) + "\n")
        p = subprocess.run([sys.executable, os.path.join(self.defn, "act.py")], env=self.env, capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, code, p.stderr)
        with open(hist) as f:
            last = [json.loads(l) for l in f if l.strip()][-1]
        return (last.get("content") if last.get("role") == "tool" else None), p.stderr

    def test_blocks_and_allows(self):
        out, _ = self.act("write", {"path": "/etc/fsm-guard-test", "content": "x"})
        self.assertTrue(out.startswith("[aos] guard: blocked: /etc/fsm-guard-test is outside"), out)
        out, _ = self.act("write", {"path": os.path.join(self.ws, "ok.txt"), "content": "x"})
        self.assertEqual(out.strip(), "TOOL RAN")
        self.assertTrue(os.path.isdir(os.path.join(self.stack, "hookeds", "guard")))

    def test_stop_yourself(self):
        out, _ = self.act("agents_ctl", {"op": "stop", "name": "sol-T01", "timeout_s": 60, "no_wait": True})
        self.assertEqual(out.strip(), "TOOL RAN")
        out, _ = self.act("agents_ctl", {"op": "stop", "name": "sol-T02", "timeout_s": 60, "no_wait": True})
        self.assertIn("agents_ctl may only stop yourself", out)

    def test_missing_config_stops_the_agent(self):
        os.remove(os.path.join(self.defn, "guard.json"))
        out, err = self.act("write", {"path": os.path.join(self.ws, "ok.txt"), "content": "x"}, code=1)
        self.assertIsNone(out)                                   # the tool did not run
        self.assertIn("HookFailed hook guard (event before_tool)", err)


if __name__ == "__main__":
    unittest.main()
