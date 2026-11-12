"""Acceptance (/tmp, fake brain, fake claude): the user's daily routine across two machines - git clone/pull, one aos-exec line, work, aos-daemon-ctl shutdown, git commit/push - with three side-by-side project repos."""
# 劇本（使用者 11-10 午原話）：三個並排的專案 repo（llms＝llm kernel、another＝被引用的格、something＝根 daemon＋fsm＋eca），
#   各自 git init、有自己的檔與歷史、各一個 bare 當 GitHub。
#   A 機：起 llms → 一行起 something → ctl add fsm／eca → 各問一題 → 再寄一封（在答完前停：留在信箱）→ shutdown → 各 repo 普通 commit、push。
#   B 機（另一個 HOME、proto8 複本在不同深度、專案在不同前綴）：全新 clone、刪掉整個 A（含它的 proto8 複本）、只設環境變數
#   → 起 llms → 一行起 something → 不下其他指令：留在信箱的那封被答、fsm／eca 接著答（eca 新對話、開場白）、history 接續
#   → shutdown → git status 只有 carry 類變動、專案檔與歷史沒動 → commit、push（不 force）。主劇本再從 B 回 A 一輪。
# 變體：名字改掉、stack 在專案外、defs 在專案外、同一台改指環境變數、llms 沒起（含下班時有一題在途）、
#   shutdown 打斷 fsm／eca 的一輪、/mnt/c（AOS_TEST_MNTC=1 或 --mntc）。AOS_TEST_BEATS=FILE 把每拍延遲寫成 JSON。
# 跑法：python3 -W ignore test_daily.py [-v] [--mntc]；KEEP=1 留下試驗資料夾。用 ~/.local/bin 的 aos 指令，不碰 ~/code、/mnt/c/code。
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest


sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[2]            # 這份 proto8（複本從它抄）
BIN = Path.home() / ".local" / "bin"
FAKE_CLAUDE = REPO / "cmd" / "aos-eca" / "tests" / "fake_claude"
GITIGNORE = REPO / "cmd" / "aos-agent" / "stack.gitignore"
CLASSES = REPO / "thinking" / "2026-11" / "10" / "two-machines" / "gitignore_classes.json"
PARTS = ("lib", "py", "templates", "kernel", "knowledge")
MNTC_BASE = Path("/mnt/c/Users/WG-Guanyu/AppData/Local/Temp")
if "--mntc" in sys.argv:
    sys.argv.remove("--mntc")
    os.environ["AOS_TEST_MNTC"] = "1"
MNTC = os.environ.get("AOS_TEST_MNTC") == "1"
OPENER = "[aos] session: this conversation continues in a new session"
LOGS = (".log", "/ledger.jsonl", "/observed.jsonl")   # 只給人看的歷史紀錄（記當時路徑，不拿來解路徑）
GIT_ID = {"GIT_AUTHOR_NAME": "Daily User", "GIT_AUTHOR_EMAIL": "user@example.invalid",
          "GIT_COMMITTER_NAME": "Daily User", "GIT_COMMITTER_EMAIL": "user@example.invalid",
          "GIT_CONFIG_NOSYSTEM": "1"}
T0 = time.monotonic()
BEATS = []                                             # (test, label, seconds)：每拍延遲


def log(msg):
    print("[%6.1fs] %s" % (time.monotonic() - T0, msg), flush=True)


def until(label, pred, timeout=60, what=lambda: "", tick=None):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if tick:
            tick()
        v = pred()
        if v:
            return v
        time.sleep(0.25)
    raise AssertionError("timed out (%ss): %s %s" % (timeout, label, what()))


def copy_proto(dest):
    dest.mkdir(parents=True)
    for n in PARTS:
        shutil.copytree(REPO / n, dest / n, symlinks=True, ignore=shutil.ignore_patterns("__pycache__", "tests"))
    return dest


def matches(pattern, name):
    """gitignore_classes.json 的 pattern（**/ 也配零層）配一條 posix 路徑；照 extras/gitignore-check/check.py。"""
    out, i = "", 0
    while i < len(pattern):
        if pattern[i:i + 3] == "**/":
            out += "(?:.*/)?"; i += 3
        elif pattern[i:i + 2] == "**":
            out += ".*"; i += 2
        elif pattern[i] == "*":
            out += "[^/]*"; i += 1
        elif pattern[i] == "[" and "]" in pattern[i + 1:]:
            end = pattern.index("]", i + 1)
            out += pattern[i:end + 1]; i = end + 1
        elif pattern[i] == "?":
            out += "[^/]"; i += 1
        else:
            out += re.escape(pattern[i]); i += 1
    return re.fullmatch(out, name) is not None


ROWS = json.loads(CLASSES.read_text())["rows"]


def classify(path):
    """回 (class, id)；排除類先贏（同 check.py）；沒有一列配得上＝(None, None)。"""
    found = [r for r in ROWS if matches(r["pattern"], path)]
    blocked = [r for r in found if r["in_git"] == "不進"]
    row = (blocked or found or [None])[0]
    return (row["class"], row["id"]) if row else (None, None)


def ident(pid):
    """(ppid, starttime, state, sid)；不在＝None。"""
    try:
        f = Path("/proc/%d/stat" % pid).read_text().rsplit(")", 1)[1].split()
        return int(f[1]), f[19], f[0], int(f[3])
    except (OSError, ValueError, IndexError):
        return None



def drop_as_written(v):
    """拿掉每一層的 as_written（daemon 表上原樣存的路徑），其餘照留。"""
    if isinstance(v, dict):
        return {k: drop_as_written(x) for k, x in v.items() if k != "as_written"}
    if isinstance(v, list):
        return [drop_as_written(x) for x in v]
    return v

class Tracker:
    """只認自己起的：根 aos-exec 的 pid＋起始時間，往下走 ppid／session 收進來；殺也只殺這些（起始時間對得上才算同一個）。"""

    def __init__(self):
        self.owned, self.sids = {}, set()

    def root(self, pid):
        i = ident(pid)
        if i:
            self.owned[pid] = i[1]
            self.sids.add(i[3])

    def remember(self):
        parents = {p for p, st in self.owned.items() if (i := ident(p)) and i[1] == st}
        changed = True
        while changed:
            changed = False
            for f in Path("/proc").iterdir():
                if not f.name.isdigit():
                    continue
                pid = int(f.name)
                if pid in parents:
                    continue
                i = ident(pid)
                if i and (i[0] in parents or i[3] in self.sids):
                    self.owned[pid] = i[1]
                    parents.add(pid)
                    changed = True

    def live(self):
        return [p for p, st in self.owned.items() if (i := ident(p)) and i[1] == st and i[2] != "Z"]

    def kill_all(self):
        self.remember()
        for sig in (signal.SIGTERM, signal.SIGKILL):
            for p in self.live():
                try:
                    os.kill(p, sig)
                except OSError:
                    pass
            end = time.monotonic() + 8
            while self.live() and time.monotonic() < end:
                time.sleep(0.2)
        return self.live()


class Machine:
    """一台：HOME、這台的 proto8 複本、環境變數（只有這些是這台準備的）、起過的根行程。"""

    def __init__(self, case, name, home, proto, extra=None):
        self.case, self.name, self.home, self.proto, self.procs = case, name, home, proto, []
        home.mkdir(parents=True, exist_ok=True)
        fake = home / "bin"
        fake.mkdir(exist_ok=True)
        (fake / "claude").symlink_to(FAKE_CLAUDE)          # PATH 最前面：假的 claude
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith(("AOS_", "CLAUDE_", "GIT_", "FAKE_CLI_", "PYTHONDONTWRITEBYTECODE"))}
        self.env.update(PATH=os.pathsep.join([str(fake), str(BIN), os.environ["PATH"]]), HOME=str(home),
                        FAKE_CLI_LOG=str(home / "fake-cli.jsonl"), **GIT_ID)
        self.use_proto(proto)
        self.env.update(extra or {})

    def use_proto(self, proto):
        """換了 HOME 就沒有 user site 的 aos-proto8.pth：照 py/README 的退路改給 PYTHONPATH，指這台那份 proto8。"""
        self.proto = proto
        self.env["AOS_HOME"] = str(proto)
        self.env["PYTHONPATH"] = os.pathsep.join([str(proto / "py"), str(proto / "lib")])

    def run(self, *args, cwd, check=True, timeout=120):
        r = subprocess.run([str(a) for a in args], cwd=cwd, env=self.env, text=True, capture_output=True,
                           timeout=timeout, stdin=subprocess.DEVNULL)
        with open(self.case.work / "commands.log", "a") as f:
            f.write("%s$ %r (cwd %s)\nexit=%d\n%s%s\n" % (self.name, args, cwd, r.returncode, r.stdout, r.stderr))
        if check and r.returncode:
            raise AssertionError("failed %r (cwd %s): rc=%d\n%s%s" % (args, cwd, r.returncode, r.stdout, r.stderr))
        return r

    def cp_template(self, name, dest, cwd):
        """照 README 的用法：cp -r $AOS_HOME/templates/名（kernel/名＝$AOS_HOME/kernel/名）目的地。"""
        src = self.proto / name if name.startswith("kernel/") else self.proto / "templates" / name
        return self.run("cp", "-r", src, dest, cwd=cwd)

    def start(self, stack, defs, cwd, label):
        """使用者那一行：aos-exec --stack <根 stack> <defs>（前景；這裡放背景、輸出進 log）。"""
        logname = self.case.work / ("%s-%s-%d.log" % (self.name, label, time.monotonic_ns()))
        with open(logname, "w") as logf:
            p = subprocess.Popen(["aos-exec", "--stack", str(stack), str(defs)], cwd=cwd, env=self.env, stdout=logf,
                                 stderr=logf, stdin=subprocess.DEVNULL, start_new_session=True)
        self.case.tracker.root(p.pid)
        self.procs.append(p)
        until("%s up" % label, lambda: p.poll() is None and
              self.run("aos-daemon-ctl", "-d", stack, "ping", "--timeout-s", "2", cwd=cwd, check=False,
                       timeout=20).returncode == 0,
              what=lambda: "exit=%r log=%s" % (p.poll(), logname.read_text()[-2000:]), tick=self.case.tracker.remember)
        return p

    def shutdown(self, stack, cwd):
        self.case.tracker.remember()
        self.run("aos-daemon-ctl", "-d", stack, "shutdown", "--timeout-s", "30", cwd=cwd)

    def wait_down(self):
        for p in self.procs:
            try:
                p.wait(timeout=30)
            except subprocess.TimeoutExpired:
                raise AssertionError("aos-exec pid %d did not exit after shutdown" % p.pid)
        self.procs = []
        until("owned processes gone", lambda: not self.case.tracker.live(), timeout=30,
              what=lambda: str(self.case.tracker.live()), tick=self.case.tracker.remember)


class Hop:
    """這一輪（一台）上的位置。"""

    def __init__(self, machine, code, outside):
        self.m, self.code, self.outside = machine, code, outside
        self.llms, self.another, self.something = code / "llms", code / "another", code / "something"


class Daily(unittest.TestCase):
    # 每個 test 的佈局（子類／參數改）
    root_def = "defs"                  # aos-exec 的 defs（相對 something；defs_out＝True 時在外面的 defs repo）
    agent_dir = "defs"                 # fsm／eca 的定義放哪個夾
    stack_rel = "stacks/root"          # 根 stack（相對 something；stack_out＝True 時在外面的 stacks repo 裡的 root）
    stack_out = False
    defs_out = False
    another_ref = "relative"           # fsm 的 tools.json 怎麼指 another：relative／env
    gitignore_at = "parent"            # parent＝只裝 stack 的父夾；root＝stack 根
    outside_layout = "other"           # 專案外的夾：other＝每台放不同位置；same＝跟三個專案並排（相對位置兩台一樣）

    # ---- 試驗場 ----

    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix="aos-daily-"))
        self.proj_base = self.work
        self.out_base = self.work
        self.tracker = Tracker()
        self.machines = []
        self.pushed = {}               # repo -> 已 push 的 commit（之後都要還在）
        self.originals = {}            # repo -> {檔名: 內容}（專案自己的檔）
        self.mnt = None

    def use_mntc(self, split=False):
        """專案（與 HOME、bare）放到 /mnt/c 的 Temp 子夾；split＝stack 留在 /tmp。"""
        self.mnt = Path(tempfile.mkdtemp(prefix="aos-daily-", dir=MNTC_BASE))
        assert not str(self.mnt).startswith("/mnt/c/code"), self.mnt
        self.proj_base = self.mnt
        self.out_base = self.work if split else self.mnt

    def tearDown(self):
        survivors = self.tracker.kill_all()
        time.sleep(0.3)
        left = ""
        for d in filter(None, (self.work, self.mnt)):
            left += subprocess.run(["pgrep", "-af", str(d)], text=True, capture_output=True).stdout.strip()
        log("leftover processes: %s" % (left or survivors or "none"))
        for d in filter(None, (self.work, self.mnt)):
            if os.environ.get("KEEP"):
                log("kept %s" % d)
            else:
                shutil.rmtree(d, ignore_errors=True)
        self.assertEqual((left, survivors), ("", []), "processes left behind")

    def beat(self, label, fn, *a, **kw):
        t = time.monotonic()
        try:
            return fn(*a, **kw)
        finally:
            BEATS.append((self.id().rsplit(".", 1)[-1], label, time.monotonic() - t))

    def machine(self, name, home, proto, extra=None):
        m = Machine(self, name, home, proto, extra)
        self.machines.append(m)
        return m

    # ---- 路徑 ----

    def repos(self):
        r = ["llms", "another", "something"]
        if self.stack_out:
            r.append("stacks")
        if self.defs_out:
            r.append("defs")
        return r

    def repo_dir(self, h, name):
        return {"llms": h.llms, "another": h.another, "something": h.something,
                "stacks": h.outside / "stacks", "defs": h.outside / "defs"}[name]

    def stack(self, h):
        """根 stack：stack_out＝外面 stacks repo 的 root（絕對）；否則相對 something。"""
        return (h.outside / "stacks" / "root") if self.stack_out else Path(self.stack_rel)

    def stack_abs(self, h):
        s = self.stack(h)
        return s if s.is_absolute() else h.something / s

    def defs_arg(self, h):
        return (h.outside / "defs") if self.defs_out else Path(self.root_def)

    def agent_def(self, h, name):
        return (h.outside / "defs" / name) if self.defs_out else Path(self.agent_dir) / name

    def roles(self, name):
        """git 路徑 → gitignore_classes.json 的角色前綴（defs/、stacks/ 只是表上的代號）。"""
        if name == "llms":
            return [("def/", "defs/"), ("stacks/", "stacks/")]
        if name == "stacks":
            return [("", "stacks/")]
        if name == "defs":
            return [("", "defs/")]
        if name == "another":
            return [("tools/", "defs/tools/")]
        top = {p.split("/")[0] + "/" for p in (self.root_def, self.agent_dir) if not self.defs_out}
        out = [(p, "defs/") for p in sorted(top)]
        if not self.stack_out:
            out.append((self.stack_rel.split("/")[0] + "/", "stacks/"))
        return out

    def normalize(self, name, path):
        for pre, role in self.roles(name):
            if path.startswith(pre):
                return role + path[len(pre):]
        return path

    # ---- 一次性：使用者在 A 機建三個（或更多）專案 ----

    def bare(self, name):
        return self.proj_base / "github" / (name + ".git")

    def git(self, m, repo, *args, check=True):
        return m.run("git", "-C", repo, *args, cwd=repo.parent, check=check)

    def new_project(self, m, path, name):
        path.mkdir(parents=True, exist_ok=True)
        files = {"README.txt": "The user's own %s project.\n" % name, "app.txt": "Project code of %s.\n" % name}
        for k, v in files.items():
            (path / k).write_text(v)
        self.originals[name] = files
        m.run("git", "init", "-q", "--bare", "-b", "main", self.bare(name), cwd=self.proj_base)
        m.run("git", "init", "-q", "-b", "main", path, cwd=path.parent)
        self.git(m, path, "remote", "add", "origin", self.bare(name))
        self.git(m, path, "add", "README.txt", "app.txt")
        self.git(m, path, "commit", "-qm", "Existing %s history" % name)
        self.git(m, path, "push", "-q", "-u", "origin", "main")
        self.pushed[name] = [self.git(m, path, "rev-parse", "HEAD").stdout.strip()]

    def build(self, m, h):
        """A 機第一次：專案已有自己的歷史；照 README 的用法 cp -r 範本、手動 cp gitignore 樣板。"""
        for n in self.repos():
            if n != "defs":
                self.new_project(m, self.repo_dir(h, n), n)
        # another：一個被引用的格（工具）
        tool = h.another / "tools" / "greet"
        tool.mkdir(parents=True)
        (tool / "_entry").write_text("#!/bin/sh\n# greet - a tool kept in the another project\ncat >/dev/null\n"
                                     "echo 'greet from another'\n")
        (tool / "_entry").chmod(0o755)
        (tool / "_tooldef.json").write_text('{"description": "Say hello from the another project. No arguments.",'
                                            ' "parameters": {"type": "object", "properties": {}}, "errors": []}\n')
        (tool / "_metainfo.json").write_text('{"summary": "Say hello", "resource": "cpu", "side_effect": false,'
                                             ' "idempotent": true, "deterministic": true, "interrupt": "safe",'
                                             ' "parallel": true, "cost": {"time_ms": 10}, "timeout_ms": 5000}\n')
        # llms：llm kernel，端點只留假腦（fake＝先叫 peek_now_time；fake-greet＝先叫 another 的 greet）
        m.cp_template("kernel/llm-kernel", "def", cwd=h.llms)
        kj = h.llms / "def" / "kernel.json"
        k = json.loads(kj.read_text())
        fake = k["endpoints"]["fake"]
        k["endpoints"] = {"fake": fake, "fake-greet": dict(fake, tool="greet")}
        k["endpoint"] = "fake"
        kj.write_text(json.dumps(k, indent=1) + "\n")
        (h.llms / "stacks").mkdir()
        shutil.copyfile(GITIGNORE, h.llms / "stacks" / ".gitignore")
        # something：根定義＋fsm＋eca（defs 在外面時：先 cp -r，再把那個夾做成使用者自己的 repo）
        defs_cwd = h.outside if self.defs_out else h.something
        root_def = "defs" if self.defs_out else self.root_def
        adir = "defs" if self.defs_out else self.agent_dir
        m.cp_template("daemon-root", root_def, cwd=defs_cwd)
        (defs_cwd / adir).mkdir(exist_ok=True)
        m.cp_template("agent-fsm", adir + "/fsm", cwd=defs_cwd)
        m.cp_template("eca-claude", adir + "/eca", cwd=defs_cwd)
        if self.defs_out:
            self.new_project(m, h.outside / "defs", "defs")
        fsm = defs_cwd / adir / "fsm"
        (fsm / "llm.json").write_text('{"model": "fake-greet"}\n')
        tj = json.loads((fsm / "tools.json").read_text())
        tj.setdefault("tools", {})                 # 11-12 範本 tools.json 只剩 $override（knowledge 那格拿掉）
        if self.another_ref == "relative":
            tj["tools"]["greet"] = {"path": os.path.relpath(h.another / "tools" / "greet", fsm)}
        else:
            tj["tools"]["greet"] = {"path": {"$env": "AOS_ANOTHER", "$path": "tools/greet"}}
        (fsm / "tools.json").write_text(json.dumps(tj, indent=1) + "\n")
        # gitignore：指南 A 做法，手動 cp 樣板
        sa = self.stack_abs(h)
        target = sa if self.gitignore_at == "root" else sa.parent
        target.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(GITIGNORE, target / ".gitignore")
        log("built under %s (stack %s, defs %s, another %s)" % (h.code, self.stack(h), self.defs_arg(h), self.another_ref))

    # ---- 日常動作 ----

    def env_for(self, m, h):
        m.env["AOS_LLM_KERNEL"] = str(h.llms / "stacks" / "kernel")
        if self.another_ref == "env":
            m.env["AOS_ANOTHER"] = str(h.another)
        m.env["AOS_TEST_PROJ"] = str(h.something)              # 11-10 B01：ws 用 --ws-json 的 $env 寫法時，每台各設自己的值

    def start_llms(self, m, h):
        self.beat("start llms", m.start, "stacks/kernel", "def", h.llms, "llms")

    def start_something(self, m, h):
        self.beat("start something", m.start, self.stack(h), self.defs_arg(h), h.something, "something")

    ws_env = False                                             # True＝ws 寫成 --ws-json '{"$env": "AOS_TEST_PROJ"}'（11-10 B01）

    def ctl_add(self, m, h):
        ws = ["--ws-json", '{"$env": "AOS_TEST_PROJ"}'] if self.ws_env else ["-w", "."]
        for n in ("fsm", "eca"):
            target = [self.agent_def(h, n)]
            if self.ws_env:                                 # 定義也經 $env 記（11-10 B01）：--path-json 代替 XXX
                rel = os.path.relpath(os.path.join(str(h.something), str(self.agent_def(h, n))), str(h.something))
                target = ["--path-json", json.dumps({"$env": "AOS_TEST_PROJ", "$path": "/" + rel})]
            self.beat("ctl add " + n, m.run, "aos-agent", "-d", self.stack(h), "ctl", "add", "--auto-restart",
                      *ws, *target, cwd=h.something)

    def table(self, m, h):
        r = m.run("aos-daemon-ctl", "-d", self.stack(h), "ls", "--json", cwd=h.something, check=False)
        try:
            return json.loads(r.stdout)["procs"] if r.returncode == 0 else {}
        except ValueError:
            return {}

    def wait_running(self, m, h, names=("fsm", "eca")):
        until("%s running" % (names,), lambda: all(self.table(m, h).get(n, {}).get("phase") == "running" for n in names),
              what=lambda: m.run("aos-daemon-ctl", "-d", self.stack(h), "ls", cwd=h.something, check=False).stdout,
              tick=self.tracker.remember)

    def expect(self, name, text):
        return ("FAKE ANSWER to: %s" % text) if name == "fsm" else ("FAKE: %s" % text)

    def ask(self, m, h, name, text, timeout=60):
        def go():
            m.run("aos-agent", "-d", self.stack(h), "-t", name, "say", text, cwd=h.something)
            return m.run("aos-agent", "-d", self.stack(h), "-t", name, "listen", "--timeout-s", str(timeout),
                         cwd=h.something, timeout=timeout + 30).stdout
        ans = self.beat("ask " + name, go)
        self.assertIn(self.expect(name, text), ans)
        if name == "fsm":
            self.assertIn("greet from another", ans)     # 腦叫了 another 的格：../another 或 $env 解得開
        log("  %s answered: %s" % (name, ans.strip()[:110]))
        return ans

    def history(self, h, name):
        p = self.stack_abs(h) / "procs" / name / "history.jsonl"
        if not p.exists():
            return []
        return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]

    def answered(self, h, name, text):
        want = self.expect(name, text)
        return any(r.get("role") == "assistant" and want in str(r.get("content")) for r in self.history(h, name))

    def queued(self, h, name, text):
        q = self.stack_abs(h) / "procs" / name / "queue"
        return [str(p.relative_to(q)) for p in q.rglob("letter.json") if text in p.read_text()] if q.exists() else []

    def letter_state(self, h, name, text):
        if self.answered(h, name, text):
            return "answered"
        q = self.queued(h, name, text)
        return ("queue:" + ",".join(q)) if q else "taken"

    def leave_letter(self, m, h, text):
        """一封沒答完就下班：信留在 agent 的信箱（queue/）裡帶走。
        先 shutdown 再 say（agent 睡著照樣收信），保證信在信箱裡；「say 之後馬上 shutdown」會跟 agent 搶，
        搶輸的 eca 那封會掉（見 test_eca_turn_cut_by_shutdown），不放在主劇本裡碰運氣。"""
        self.beat("shutdown something", m.shutdown, self.stack(h), h.something)
        for n in ("fsm", "eca"):
            m.run("aos-agent", "-d", self.stack(h), "-t", n, "say", text, cwd=h.something)
        state = {n: self.letter_state(h, n, text) for n in ("fsm", "eca")}
        log("  letter %r left at shutdown: %s" % (text, state))
        for n in ("fsm", "eca"):
            self.assertTrue(state[n].startswith("queue:"), "%s letter not in its mailbox: %s" % (n, state[n]))
        return state

    def shutdown_all(self, m, h, left=None):
        if left is None:
            self.beat("shutdown something", m.shutdown, self.stack(h), h.something)
        self.beat("shutdown llms", m.shutdown, "stacks/kernel", h.llms)
        m.wait_down()

    def commit_push(self, m, h, msg):
        for n in self.repos():
            r = self.repo_dir(h, n)
            self.git(m, r, "add", "-A")
            if self.git(m, r, "status", "--porcelain").stdout.strip():
                self.beat("git commit", self.git, m, r, "commit", "-qm", msg)
            self.beat("git push", self.git, m, r, "push", "-q", "origin", "main")   # 普通 push：非快轉就失敗
            self.pushed[n].append(self.git(m, r, "rev-parse", "HEAD").stdout.strip())

    def clone_all(self, m, h):
        for n in self.repos():
            d = self.repo_dir(h, n)
            d.parent.mkdir(parents=True, exist_ok=True)
            self.beat("git clone", m.run, "git", "clone", "-q", self.bare(n), d, cwd=d.parent)

    # ---- 檢查 ----

    def check_git(self, m, h, old_roots):
        """shutdown 後：每個 repo 的 git status 只有 carry 類；定義與 another 沒被動；專案檔與歷史都在。"""
        problems = []
        for n in self.repos():
            r = self.repo_dir(h, n)
            st = self.git(m, r, "status", "--porcelain", "--untracked-files=all", "-z").stdout.split("\0")
            changes = []
            for item in filter(None, st):
                path = item[3:]
                role = self.normalize(n, path)
                cls, rid = classify(role)
                changes.append("%s %s [%s %s]" % (item[:2].strip(), path, cls, rid))
                if cls != "carry":
                    problems.append("%s: %s is %s (%s)" % (n, path, cls, rid))
                elif role.startswith("defs/") and n != "another":
                    problems.append("%s: definition changed by running: %s" % (n, path))
                elif n == "another":
                    problems.append("another changed: %s" % path)
            log("  %s status: %s" % (n, "; ".join(changes) or "clean"))
            for f, text in self.originals[n].items():
                self.assertEqual((r / f).read_text(), text, "%s/%s touched" % (n, f))
            for c in self.pushed[n]:
                if self.git(m, r, "merge-base", "--is-ancestor", c, "HEAD", check=False).returncode:
                    problems.append("%s: old commit %s missing from history" % (n, c[:10]))
            tracked = self.git(m, r, "ls-files", "-z").stdout.split("\0")
            for f in filter(None, tracked):
                p = r / f
                if f.endswith(LOGS) or p.is_symlink() or not p.is_file():
                    continue
                txt = p.read_text(errors="ignore")
                if f.endswith("procs_state.json"):   # 11-10 晚 B01：as_written＝使用者在命令列打的絕對路徑、照原樣存（設計如此，B06 口徑）；只看其餘
                    txt = json.dumps(drop_as_written(json.loads(txt)))
                for old in old_roots:
                    if str(old) in txt:
                        problems.append("%s: %s still names %s" % (n, f, old))
        self.assertEqual(problems, [], "git state after shutdown")

    def check_resumed(self, m, h, letter, prev):
        """不下其他指令：留在信箱的那封被答；history 接續上一台的問答。"""
        for n in ("fsm", "eca"):
            until("%s answers the letter left in its mailbox" % n, lambda: self.answered(h, n, letter) or
                  self.not_stopped(m, h, n), timeout=90, what=lambda: str(self.history(h, n)[-4:]),
                  tick=self.tracker.remember)
            contents = [str(r.get("content")) for r in self.history(h, n)]
            for q in prev:
                self.assertTrue(any(q in c for c in contents), "%s history lost %r" % (n, q))
            self.assertEqual(self.queued(h, n, letter), [], "%s letter still queued" % n)
        log("  letter %r answered on %s, history continues" % (letter, m.name))

    def stage(self, h, name="fsm"):
        p = self.stack_abs(h) / "procs" / name / "stage.txt"
        return p.read_text().strip() if p.exists() else None

    def stderr_of(self, h, name):
        p = self.stack_abs(h) / "procs" / name / "stderr.txt"
        return ("\nstderr: " + p.read_text()[-1500:]) if p.exists() else ""

    def not_stopped(self, m, h, name):
        """表上已經 stopped（daemon 放棄重起）＝不用再等，直接帶 reason 失敗；否則回 False 繼續等。"""
        row = self.table(m, h).get(name, {})
        if row.get("phase") == "stopped":
            raise AssertionError("%s stopped on %s: %s" % (name, m.name, row.get("reason")))
        return False

    def check_eca_new_session(self, m, first_q):
        calls = [json.loads(x) for x in (m.home / "fake-cli.jsonl").read_text().splitlines() if x.strip()]
        self.assertTrue(calls, "fake claude never called on " + m.name)
        first = calls[0]
        self.assertIn("--session-id", first["argv"])
        self.assertNotIn("--resume", first["argv"])
        self.assertTrue(first["stdin"].startswith(OPENER), first["stdin"][:300])
        self.assertIn(first_q, first["stdin"])                 # 開場白帶著上一台的紀錄
        log("  eca on %s: new session, stdin opens with the reseed note (%d bytes)" % (m.name, len(first["stdin"])))

    # ---- 劇本 ----

    def hop_spec(self, tag):
        """三種位置：A、B（不同 HOME、proto8 不同深度、專案不同前綴、外部夾不同位置）、A2（回 A 的新位置）。"""
        pb, ob = self.proj_base, self.out_base
        return {"A": (pb / "homeA", "repo/proto8", "code", ob / "outA" / "elsewhere"),
                "B": (pb / "homeB", "opt/x/y/repo2/proto8", "work/deep/projects", ob / "outB" / "var" / "lib" / "aos"),
                "A2": (pb / "homeA", "repo/proto8", "new/place", ob / "outA2" / "other")}[tag]

    def make_hop(self, tag):
        home, proto_rel, code_rel, outside = self.hop_spec(tag)
        if self.outside_layout == "same":              # 外部夾跟三個專案並排：兩台相對位置一樣
            outside = home / code_rel / "elsewhere"
        proto = copy_proto(home / proto_rel)
        m = self.machine(tag, home, proto)
        outside.mkdir(parents=True, exist_ok=True)
        return Hop(m, home / code_rel, outside)

    def drop_hop(self, h):
        """這台整個資料夾（HOME＝含它的 proto8 複本與專案）連同外部夾刪掉。"""
        shutil.rmtree(h.m.home)
        shutil.rmtree(h.outside, ignore_errors=True)

    def first_day(self):
        h = self.make_hop("A")
        self.build(h.m, h)
        self.env_for(h.m, h)
        self.start_llms(h.m, h)
        self.start_something(h.m, h)
        self.ctl_add(h.m, h)
        self.wait_running(h.m, h)
        for n in ("fsm", "eca"):
            self.ask(h.m, h, n, "A question one")
        left = self.leave_letter(h.m, h, "A letter left")
        self.shutdown_all(h.m, h, left)
        self.commit_push(h.m, h, "End of day on A")
        return h

    def next_day(self, prev, tag, letter_in, prev_qs):
        """換台：全新 clone、刪掉上一台整個資料夾、只設環境變數、起 llms、一行起 something，不下其他指令。"""
        h = self.make_hop(tag)
        self.clone_all(h.m, h)
        old_roots = [prev.m.home, prev.outside, prev.code]
        self.drop_hop(prev)
        self.env_for(h.m, h)
        log("  %s: AOS_HOME=%s AOS_LLM_KERNEL=%s" % (tag, h.m.env["AOS_HOME"], h.m.env["AOS_LLM_KERNEL"]))
        self.start_llms(h.m, h)
        self.start_something(h.m, h)
        self.check_resumed(h.m, h, letter_in, prev_qs)
        self.check_eca_new_session(h.m, prev_qs[0])
        q = "%s question" % tag
        for n in ("fsm", "eca"):
            self.ask(h.m, h, n, q)
        letter = "%s letter left" % tag
        left = self.leave_letter(h.m, h, letter)
        self.shutdown_all(h.m, h, left)
        self.check_git(h.m, h, old_roots)
        self.commit_push(h.m, h, "End of day on " + tag)
        return h, letter, prev_qs + [letter_in, q]

    def two_machines(self, back=False):
        a = self.first_day()
        b, letter, qs = self.next_day(a, "B", "A letter left", ["A question one"])
        if back:
            self.next_day(b, "A2", letter, qs)


class T1Main(Daily):
    def test_1_main_relative_a_b_a(self):
        """主劇本：A → B → A，something 用相對 ../another 引用。"""
        self.two_machines(back=True)

    def test_2_main_env_another(self):
        """主劇本另一輪：something 用 {"$env": "AOS_ANOTHER"} 引用 another。"""
        self.another_ref = "env"
        self.two_machines()


class T2Renamed(Daily):
    root_def, agent_dir, stack_rel, gitignore_at = "d1", "d2", "state/root", "root"

    def test_renamed_d1_d2_state_root(self):
        """① 名字改掉：根定義 d1/、agent 定義 d2/、根 stack state/root（gitignore 放 stack 根）。"""
        self.two_machines()


TABLE_RELATIVE = ("daemon 把表上每列的 ws／def／exec 存成相對根 stack（procs_state.json），使用者指定的絕對路徑或環境變數"
                  "不留；外部夾在 B 機換了相對位置，就解到不存在的地方：aos-exec: error: WsMissing workspace does not exist"
                  "（或定義不在），重起 3 次後 stopped，信留在信箱裡沒掉但沒人答。見 TA-report.md。")


class T3StackOutside(Daily):
    stack_out = True
    another_ref = "env"

    def test_stack_outside_same_layout(self):
        """② stack 在專案外（另一個 stacks repo，絕對路徑指），外部夾跟專案並排、兩台相對位置一樣。"""
        self.outside_layout = "same"
        self.two_machines()

    def test_stack_outside_other_layout_ws_env(self):
        """② stack 在專案外、B 機放到另一個相對位置，ws 用 --ws-json 的 $env 寫法、兩台各設自己的 AOS_TEST_PROJ：
        表上存指示詞原形（as_written）、每次起照當下環境再解＝不用 rm 再 add 就起得來（11-10 B01）。"""
        self.ws_env = True
        self.two_machines()

    @unittest.expectedFailure
    def test_stack_outside_other_layout(self):
        """② stack 在專案外，B 機把 stacks repo 放到另一個位置（相對專案的位置不同）。expectedFailure：TABLE_RELATIVE。"""
        self.two_machines()


class T4DefsOutside(Daily):
    defs_out = True
    another_ref = "env"

    def test_defs_outside_same_layout(self):
        """③ defs 在專案外（另一個 defs repo，絕對路徑給 aos-exec 與 ctl add），跟專案並排、兩台相對位置一樣。"""
        self.outside_layout = "same"
        self.two_machines()

    @unittest.expectedFailure
    def test_defs_outside_other_layout(self):
        """③ defs 在專案外，B 機把 defs repo 放到另一個位置。expectedFailure：TABLE_RELATIVE（表上的 def 相對根 stack）。"""
        self.two_machines()


class T5Repoint(Daily):
    def test_same_machine_repoint_env(self):
        """④ 同一台：跑通 → 停 → AOS_LLM_KERNEL、AOS_HOME 改指另一份（舊的刪掉）→ 再起照樣答、不殘留舊值。"""
        h = self.make_hop("A")
        m = h.m
        self.build(m, h)
        self.env_for(m, h)
        self.start_llms(m, h)
        self.start_something(m, h)
        self.ctl_add(m, h)
        self.wait_running(m, h)
        for n in ("fsm", "eca"):
            self.ask(m, h, n, "question one")
        self.shutdown_all(m, h)
        self.commit_push(m, h, "day one")
        old_llms, old_proto = h.llms, m.proto
        llms2 = h.code / "llms-second"
        m.run("git", "clone", "-q", self.bare("llms"), llms2, cwd=h.code)
        ledger2 = llms2 / "stacks" / "kernel" / "ledger.jsonl"
        before = len(ledger2.read_text().splitlines()) if ledger2.exists() else 0
        p2 = copy_proto(m.home / "other" / "proto8-second")
        shutil.rmtree(old_proto)
        shutil.rmtree(old_llms)
        h.llms = llms2                                   # 之後的停與 git 檢查看第二份
        m.use_proto(p2)
        m.env["AOS_LLM_KERNEL"] = str(llms2 / "stacks" / "kernel")
        log("  AOS_HOME -> %s, AOS_LLM_KERNEL -> %s (old ones deleted)" % (p2, m.env["AOS_LLM_KERNEL"]))
        self.beat("start llms", m.start, "stacks/kernel", "def", llms2, "llms2")
        self.start_something(m, h)
        for n in ("fsm", "eca"):
            self.ask(m, h, n, "question two")
        self.assertGreater(len(ledger2.read_text().splitlines()) if ledger2.exists() else 0, before,
                           "the second llm kernel did not take the request")
        self.shutdown_all(m, h)
        self.check_git(m, h, [old_llms, old_proto])


class T6LlmsDown(Daily):
    def wait_not_broken(self, m, h, seconds=8):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.tracker.remember()
            row = self.table(m, h).get("fsm", {})
            self.assertEqual(row.get("phase"), "running", "fsm left running while llms is down: %r" % row)
            time.sleep(0.5)
        log("  fsm still running after %ds with llms down (stage %s)" % (seconds, self.stage(h)))

    def test_llms_down_question_in_flight_moves(self):
        """⑤c 下班時 llms 沒開、fsm 有一題在途（已收進 history、寄給 kernel 還沒回）→ shutdown、push → B 機接著答。"""
        h = self.make_hop("A")
        m = h.m
        self.build(m, h)
        self.env_for(m, h)
        self.start_llms(m, h)
        self.start_something(m, h)
        self.ctl_add(m, h)
        self.wait_running(m, h)
        self.ask(m, h, "fsm", "A question one")
        self.beat("shutdown llms", m.shutdown, "stacks/kernel", h.llms)
        m.run("aos-agent", "-d", self.stack(h), "-t", "fsm", "say", "in flight", cwd=h.something)
        pending = self.stack_abs(h) / "procs" / "fsm" / "think" / "pending.txt"
        until("fsm waiting on the kernel", lambda: pending.exists() and not self.queued(h, "fsm", "in flight"),
              tick=self.tracker.remember, what=lambda: str(self.stage(h)))
        self.wait_not_broken(m, h, 3)
        self.beat("shutdown something", m.shutdown, self.stack(h), h.something)
        m.wait_down()
        self.commit_push(m, h, "End of day on A, llms was off")
        b = self.make_hop("B")
        self.clone_all(b.m, b)
        self.drop_hop(h)
        self.env_for(b.m, b)
        self.start_llms(b.m, b)
        self.start_something(b.m, b)
        until("in-flight question answered on B", lambda: self.answered(b, "fsm", "in flight") or
              self.not_stopped(b.m, b, "fsm"), timeout=90, tick=self.tracker.remember,
              what=lambda: str(self.history(b, "fsm")[-3:]) + self.stderr_of(b, "fsm"))
        self.ask(b.m, b, "fsm", "B question")
        self.shutdown_all(b.m, b)
        self.check_git(b.m, b, [h.m.home])

    def test_llms_stopped(self):
        """⑤a llms 停著時 fsm 問一題：不停（phase 仍 running）、llms 起來後答得出來。"""
        h = self.make_hop("A")
        m = h.m
        self.build(m, h)
        self.env_for(m, h)
        self.start_llms(m, h)
        self.start_something(m, h)
        self.ctl_add(m, h)
        self.wait_running(m, h)
        self.ask(m, h, "fsm", "while up")
        self.beat("shutdown llms", m.shutdown, "stacks/kernel", h.llms)
        m.run("aos-agent", "-d", self.stack(h), "-t", "fsm", "say", "while llms is down", cwd=h.something)
        self.wait_not_broken(m, h)
        self.assertFalse(self.answered(h, "fsm", "while llms is down"), "answered with llms down?")
        self.start_llms(m, h)
        until("answer after llms is back", lambda: self.answered(h, "fsm", "while llms is down"), timeout=90,
              what=lambda: str(self.history(h, "fsm")[-3:]) + self.stderr_of(h, "fsm"), tick=self.tracker.remember)
        self.shutdown_all(m, h)

    def test_llms_never_started(self):
        """⑤b llms 從沒起過（AOS_LLM_KERNEL 指的 stack 還不在）：fsm 問一題不停、llms 第一次起來後答得出來。"""
        h = self.make_hop("A")
        m = h.m
        self.build(m, h)
        self.env_for(m, h)
        self.start_something(m, h)
        self.ctl_add(m, h)
        self.wait_running(m, h)
        m.run("aos-agent", "-d", self.stack(h), "-t", "fsm", "say", "before llms ever ran", cwd=h.something)
        self.wait_not_broken(m, h)
        self.assertFalse(self.answered(h, "fsm", "before llms ever ran"), "answered before llms ran?")
        self.start_llms(m, h)
        until("answer after llms first starts", lambda: self.answered(h, "fsm", "before llms ever ran"), timeout=90,
              what=lambda: str(self.history(h, "fsm")[-3:]) + self.stderr_of(h, "fsm"), tick=self.tracker.remember)
        self.shutdown_all(m, h)


ECA_CUT = ("eca 一輪做到一半被 shutdown（SIGTERM）：那封已收進 history（只有 user、沒有 assistant），再起後不重答、"
           "也沒有任何提醒，使用者下班前最後問的那句就這樣沒了。設計 05 裁定 5 只講「開了新對話之後 CLI 失敗」掉那封；"
           "收工打斷的這條沒寫，要隊長／使用者裁。見 TA-report.md。")


class T8ShutdownMidTurn(Daily):
    """「say 之後馬上 shutdown」搶輸的兩種：信已被 agent 收走、還沒答完。同一台再起（隔天）看有沒有接著答。"""

    def day(self):
        h = self.make_hop("A")
        self.build(h.m, h)
        self.env_for(h.m, h)
        self.start_llms(h.m, h)
        self.start_something(h.m, h)
        self.ctl_add(h.m, h)
        self.wait_running(h.m, h)
        return h

    def restart(self, h):
        self.start_something(h.m, h)

    def test_fsm_turn_cut_by_shutdown(self):
        """fsm 已收信、還在想（腦的往返中）就 shutdown → 再起後從 stage 接著答。"""
        h = self.day()
        m = h.m
        m.run("aos-agent", "-d", self.stack(h), "-t", "fsm", "say", "cut short", cwd=h.something)
        until("fsm took the letter", lambda: not self.queued(h, "fsm", "cut short") and
              any(r.get("content") == "cut short" for r in self.history(h, "fsm")), tick=self.tracker.remember)
        self.assertFalse(self.answered(h, "fsm", "cut short"))
        self.beat("shutdown something", m.shutdown, self.stack(h), h.something)
        log("  fsm cut at stage %s" % self.stage(h))
        self.restart(h)
        until("fsm answers after restart", lambda: self.answered(h, "fsm", "cut short") or self.not_stopped(m, h, "fsm"),
              timeout=60, tick=self.tracker.remember, what=lambda: str(self.history(h, "fsm")[-3:]))
        self.shutdown_all(m, h)

    def test_eca_turn_cut_by_shutdown(self):
        """eca 已把信交給 claude、claude 還沒回就 shutdown → 那封照裁定 5 不重答（history 只有 user），
        但下一封不可白掉：claude 沒存下那段對話＝cli_session.stored_here 認出來、開新對話帶紀錄（11-10 修 ECA_CUT）。"""
        h = self.make_hop("A")
        m = h.m
        slow = m.home / "bin" / "claude"                # 這一條換成慢一點的假 claude（先留記號、睡 4 秒、再交給 fake_claude）
        slow.unlink()
        slow.write_text('#!/bin/sh\ntouch "$HOME/claude-started"\nsleep 4\nexec "%s" "$@"\n' % FAKE_CLAUDE)
        slow.chmod(0o755)
        self.build(m, h)
        self.env_for(m, h)
        self.start_llms(m, h)
        self.start_something(m, h)
        self.ctl_add(m, h)
        self.wait_running(m, h)
        m.run("aos-agent", "-d", self.stack(h), "-t", "eca", "say", "cut short", cwd=h.something)
        until("claude started", lambda: (m.home / "claude-started").exists(), tick=self.tracker.remember)
        self.beat("shutdown something", m.shutdown, self.stack(h), h.something)
        log("  eca cut: history tail %s" % self.history(h, "eca")[-2:])
        self.restart(h)
        self.wait_running(m, h, ("eca",))
        slow.unlink()
        slow.symlink_to(FAKE_CLAUDE)                     # 之後照常快
        try:
            m.run("aos-agent", "-d", self.stack(h), "-t", "eca", "say", "after the cut", cwd=h.something)
            nxt = m.run("aos-agent", "-d", self.stack(h), "-t", "eca", "listen", "--timeout-s", "20",
                        cwd=h.something, check=False, timeout=60)
            time.sleep(1)
            got = {q: self.answered(h, "eca", q) for q in ("cut short", "after the cut")}
            log("  eca after restart: answered %s; listen rc=%d %s%s" % (got, nxt.returncode, nxt.stdout.strip(),
                                                                       nxt.stderr.strip()))
            self.assertEqual(got, {"cut short": False, "after the cut": True},
                             "history %s%s" % (self.history(h, "eca"), self.stderr_of(h, "eca")))
        finally:
            self.shutdown_all(m, h)


@unittest.skipUnless(MNTC, "set AOS_TEST_MNTC=1 or pass --mntc to run on /mnt/c")
class T7Mntc(Daily):
    def test_mntc_main(self):
        """⑥ 主劇本（A → B）整套在 /mnt/c 的 Temp 子夾：專案、HOME、proto8 複本、bare 都在 /mnt/c。"""
        self.use_mntc()
        self.two_machines()

    def test_mntc_split_stack_in_tmp(self):
        """⑥ 分散版：專案在 /mnt/c、根 stack 在 /tmp（專案外的 stacks repo，絕對路徑指）。
        同一台跑兩天（停 → 隔天再起、留在信箱的那封被答）；換台會撞 TABLE_RELATIVE（② other_layout 已涵蓋），這裡不重測。"""
        self.use_mntc(split=True)
        self.stack_out = True
        self.another_ref = "env"
        h = self.first_day()
        m = h.m
        self.env_for(m, h)
        self.start_llms(m, h)
        self.start_something(m, h)
        self.check_resumed(m, h, "A letter left", ["A question one"])
        for n in ("fsm", "eca"):
            self.ask(m, h, n, "day two question")
        self.shutdown_all(m, h)
        self.check_git(m, h, [])
        self.commit_push(m, h, "End of day two")


def report_beats():
    if not BEATS:
        return
    agg = {}
    for test, label, s in BEATS:
        agg.setdefault((test, label), []).append(s)
    print("\nper-beat latency (seconds: count / mean / max):", flush=True)
    for (test, label), v in sorted(agg.items()):
        print("  %-36s %-20s %2d / %6.2f / %6.2f" % (test, label, len(v), sum(v) / len(v), max(v)), flush=True)
    out = os.environ.get("AOS_TEST_BEATS")
    if out:
        Path(out).write_text(json.dumps([{"test": t, "beat": b, "s": round(s, 3)} for t, b, s in BEATS], indent=1) + "\n")


if __name__ == "__main__":
    try:
        unittest.main()
    finally:
        report_beats()
