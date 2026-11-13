"""Integration (/tmp, fake brain): a project (defs/ from daemon-root + one agent-fsm, copied with cp -r) and an llm kernel project move by git to another HOME and prefix with AOS_HOME given three ways, and keep answering."""
# 範本照 README 用 cp -r 抄出（檔裡一律 {"$env": "AOS_HOME", ...}）；AOS_HOME 三種給法各一輪：
#   env＝殼裡 export；absolute＝兩份 .env 寫絕對路徑（兩台同一個絕對位置）；relative＝兩份 .env 寫 ${AOS_WS}/..（兩台同相對擺法）。各跑
#   A 起 → 問一題 → aos-daemon-ctl -d stacks/root shutdown → git 搬到另一個 HOME、另一個前綴（A 的 proto8 複本與整個 A 刪掉）
#   → B aos-exec --stack stacks/root defs → 不用其他指令就接著答；
# 加一輪同一台：env 跑通 → 停 → AOS_HOME 改指另一份 proto8 複本（舊的刪掉）→ 再起 → 照樣答、檔裡沒殘留舊值。
# 跑法：python3 test_paths_move.py [-v]（每輪約 20～40 秒）；KEEP=1 留下試驗資料夾。用 ~/.local/bin 的 aos 指令，不碰 ~/code。
import json
import os
from pathlib import Path
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
PARTS = ("lib", "py", "templates", "kernel", "knowledge")
T0 = time.monotonic()
# 只給人看的歷史紀錄（記當時的路徑，不拿來解路徑）：log、llm kernel 的帳 ledger.jsonl、觀測帳 observed.jsonl
LOGS = (".log", "/ledger.jsonl", "/observed.jsonl")
COMMENTED = "# AOS_HOME=${HOME}/repo/aos/proto8"      # 範本 .env 裡示範寫法的那行註解


def log(msg):
    print("[%6.1fs] %s" % (time.monotonic() - T0, msg), flush=True)


def copy_proto(dest):
    dest.mkdir(parents=True)
    for n in PARTS:
        shutil.copytree(REPO / n, dest / n, symlinks=True, ignore=shutil.ignore_patterns("__pycache__", "tests"))
    return dest


class Machine:
    """一台：HOME、環境、起過的行程。"""

    def __init__(self, work, home, proto, extra=None):
        self.work, self.proto, self.procs = work, proto, []
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        self.env.update(PATH=str(BIN) + os.pathsep + os.environ["PATH"], HOME=str(home), PYTHONDONTWRITEBYTECODE="1")
        self.use_proto(proto)
        self.env.update(extra or {})
        home.mkdir(parents=True, exist_ok=True)

    def use_proto(self, proto):
        """換了 HOME 就沒有 user site 的 aos-proto8.pth：照 py/README 的退路改給 PYTHONPATH，指這台那份 proto8。"""
        self.proto = proto
        self.env["PYTHONPATH"] = os.pathsep.join([str(proto / "py"), str(proto / "lib")])

    def run(self, *args, cwd, check=True, timeout=90):
        r = subprocess.run([str(a) for a in args], cwd=cwd, env=self.env, text=True, capture_output=True,
                           timeout=timeout, stdin=subprocess.DEVNULL)
        if check and r.returncode:
            raise AssertionError("failed %r (cwd %s): rc=%d\n%s%s" % (args, cwd, r.returncode, r.stdout, r.stderr))
        return r

    def cp_template(self, src, dest, cwd):
        """照 README：cp -r $AOS_HOME/templates/名 目的地（src 是 proto8 底下的相對路徑）。"""
        return self.run("cp", "-r", self.proto / src, dest, cwd=cwd)

    def start(self, stack, defs, cwd, label):
        logname = self.work / ("%s-%d-%d.log" % (label, len(self.procs), time.monotonic_ns()))
        with open(logname, "w") as logf:
            p = subprocess.Popen(["aos-exec", "--stack", str(stack), str(defs)], cwd=cwd, env=self.env, stdout=logf,
                                 stderr=logf, stdin=subprocess.DEVNULL, start_new_session=True)
        self.procs.append(p)
        until("%s up" % label, lambda: p.poll() is None and
              self.run("aos-daemon-ctl", "-d", stack, "ping", cwd=cwd, check=False, timeout=20).returncode == 0,
              what=lambda: "exit=%r log=%s" % (p.poll(), logname.read_text()[-2000:]))
        return p

    def shutdown(self, stack, cwd):
        self.run("aos-daemon-ctl", "-d", stack, "shutdown", cwd=cwd)

    def wait_down(self):
        for p in self.procs:
            try:
                p.wait(timeout=30)
            except subprocess.TimeoutExpired:
                raise AssertionError("aos-exec pid %d did not exit after shutdown" % p.pid)
        self.procs = []

    def kill_all(self):
        for p in self.procs:
            if p.poll() is None:
                try:
                    os.killpg(p.pid, signal.SIGINT)
                    p.wait(timeout=20)
                except (OSError, subprocess.TimeoutExpired):
                    try:
                        os.killpg(p.pid, signal.SIGKILL)
                    except OSError:
                        pass
        self.procs = []


def until(label, pred, timeout=60, what=lambda: ""):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        v = pred()
        if v:
            return v
        time.sleep(0.3)
    raise AssertionError("timed out: %s %s" % (label, what()))


def grep_tree(root, needle):
    """root 底下（不跟捷徑、不含 .git 與 log）哪些檔含 needle。"""
    hits = []
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x != ".git" and not os.path.islink(os.path.join(d, x))]
        for f in files:
            p = os.path.join(d, f)
            if os.path.islink(p):
                if needle in os.readlink(p):
                    hits.append(p + " (symlink)")
                continue
            try:
                if needle in open(p, encoding="utf-8", errors="ignore").read():
                    hits.append(p)
            except OSError:
                pass
    return hits


class PathsMove(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix="tc-move-"))
        self.machines = []

    def tearDown(self):
        for m in self.machines:
            m.kill_all()
        time.sleep(0.5)
        left = subprocess.run(["pgrep", "-af", str(self.work)], text=True, capture_output=True).stdout.strip()
        log("leftover processes: %s" % (left or "none"))
        if os.environ.get("KEEP"):
            log("kept %s" % self.work)
        else:
            shutil.rmtree(self.work, ignore_errors=True)
        self.assertEqual(left, "", "processes left behind")

    def machine(self, name, proto, extra=None):
        m = Machine(self.work, self.work / name / "home", proto, extra)
        self.machines.append(m)
        return m

    # ---- 一台上的動作 ----

    def build(self, m, base, mode):
        """在 base 底下建 proj（defs＝daemon-root＋ann，stacks/）與 llms（llm kernel 專案）。"""
        proj, llms = base / "proj", base / "llms"
        proj.mkdir(parents=True)
        llms.mkdir(parents=True)
        m.cp_template("templates/daemon-root", "defs", cwd=proj)
        m.cp_template("templates/agent-fsm", "defs/ann", cwd=proj)
        (proj / "defs" / "ann" / "llm.json").write_text('{"model": "fake"}\n')
        m.cp_template("kernel/llm-kernel", "def", cwd=llms)
        if mode != "env":                              # 不 export：把範本 .env 那行註解換成自己的值（README 教的寫法）
            value = {"absolute": str(m.proto),
                     "relative": "${AOS_WS}/" + os.path.relpath(m.proto, proj)}[mode]
            for env in (proj / "defs" / ".env", llms / "def" / ".env"):
                text = env.read_text()
                self.assertIn(COMMENTED, text)
                env.write_text(text.replace(COMMENTED, "AOS_HOME=" + value))
        out = "AOS_HOME %s" % {"env": "exported"}.get(mode, "in .env: " + (proj / "defs" / ".env").read_text().split("AOS_HOME=", 1)[1].split("\n", 1)[0])
        for stacks in (proj / "stacks", llms / "stacks"):
            stacks.mkdir()
            shutil.copyfile(REPO / "cmd" / "aos-agent" / "stack.gitignore", stacks / ".gitignore")
        log("built %s (%s):\n    %s" % (base, mode, out.strip().replace("\n", "\n    ")))
        return proj, llms

    def start_both(self, m, proj, llms):
        m.env["AOS_LLM_KERNEL"] = str(llms / "stacks" / "llm")
        m.start(llms / "stacks" / "llm", "def", llms, "llm")
        m.start("stacks/root", "defs", proj, "root")

    def wait_ann(self, m, proj):
        def row():
            r = m.run("aos-daemon-ctl", "-d", "stacks/root", "ls", "--json", cwd=proj, check=False)
            return r.returncode == 0 and json.loads(r.stdout)["procs"].get("ann", {}).get("phase") == "running"
        until("ann running", row, what=lambda: m.run("aos-daemon-ctl", "-d", "stacks/root", "ls", cwd=proj, check=False).stdout)

    def ask(self, m, proj, text):
        m.run("aos-agent", "-d", "stacks/root", "-t", "ann", "say", text, cwd=proj)
        ans = m.run("aos-agent", "-d", "stacks/root", "-t", "ann", "listen", "--timeout-s", "60", cwd=proj).stdout
        self.assertIn("FAKE ANSWER to: %s" % text, ans)
        self.assertIn("tool said:", ans)              # 腦叫了 peek_now_time：登記檔的路徑解得開
        log("  ann answered: %s" % ans.strip()[:100])
        return ans

    def stop_both(self, m, proj, llms):
        m.shutdown("stacks/root", proj)
        m.shutdown(llms / "stacks" / "llm", llms)
        m.wait_down()

    def commit(self, m, repo):
        m.run("git", "init", "-q", cwd=repo)
        m.run("git", "add", "-A", cwd=repo)
        m.run("git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-qm", "save", cwd=repo)

    # ---- 一輪 ----

    def move_round(self, mode):
        log("==== round %s ====" % mode)
        base_a = self.work / "A" / "pre-a"
        base_b = self.work / "B" / "pre-b" / "deeper"
        fixed = self.work / "fixed" / "proto8"
        proto_a = {"env": base_a / "repo" / "proto8", "absolute": fixed, "relative": base_a / "repo" / "proto8"}[mode]
        proto_b = {"env": base_b / "elsewhere" / "p8", "absolute": base_b / "repo" / "proto8",
                   "relative": base_b / "repo" / "proto8"}[mode]
        copy_proto(proto_a)
        a = self.machine("A", proto_a, {"AOS_HOME": str(proto_a)} if mode == "env" else None)
        proj_a, llms_a = self.build(a, base_a, mode)
        self.start_both(a, proj_a, llms_a)
        a.run("aos-agent", "-d", "stacks/root", "ctl", "add", "--auto-restart", "-w", ".", "defs/ann", cwd=proj_a)
        self.wait_ann(a, proj_a)
        self.ask(a, proj_a, "question one")
        self.stop_both(a, proj_a, llms_a)
        self.commit(a, proj_a)
        self.commit(a, llms_a)
        # 搬：B 另一個 HOME、另一個前綴；clone 完把整個 A（含它的 proto8 複本）刪掉
        base_b.mkdir(parents=True)
        a.run("git", "clone", "-q", proj_a, base_b / "proj", cwd=base_b)
        a.run("git", "clone", "-q", llms_a, base_b / "llms", cwd=base_b)
        shutil.rmtree(self.work / "A")
        shutil.rmtree(self.work / "fixed", ignore_errors=True)
        copy_proto(proto_b)
        if mode == "absolute":                         # 兩台同一個絕對位置：B 在那裡放一個捷徑指到自己的複本
            fixed.parent.mkdir(parents=True)
            os.symlink(proto_b, fixed)
        b = self.machine("B", proto_b, {"AOS_HOME": str(proto_b)} if mode == "env" else None)
        proj_b, llms_b = base_b / "proj", base_b / "llms"
        self.start_both(b, proj_b, llms_b)
        self.wait_ann(b, proj_b)
        ans = self.ask(b, proj_b, "question two")
        hist = (proj_b / "stacks" / "root" / "procs" / "ann" / "history.jsonl")
        self.assertIn("question one", hist.read_text())   # 接著同一段歷史
        self.stop_both(b, proj_b, llms_b)
        stale = grep_tree(base_b, str(self.work / "A"))
        stale = [h for h in stale if not h.endswith(LOGS)]
        self.assertEqual(stale, [], "files still naming machine A")
        log("round %s PASS" % mode)
        return ans

    def test_1_env(self):
        self.move_round("env")

    def test_2_absolute(self):
        self.move_round("absolute")

    def test_3_relative(self):
        self.move_round("relative")

    def test_4_env_repoint_same_machine(self):
        log("==== round env-repoint (same machine) ====")
        base = self.work / "S" / "pre"
        p1, p2 = copy_proto(base / "p1" / "proto8"), base / "p2" / "proto8"
        m = self.machine("S", p1, {"AOS_HOME": str(p1)})
        proj, llms = self.build(m, base, "env")
        self.start_both(m, proj, llms)
        m.run("aos-agent", "-d", "stacks/root", "ctl", "add", "--auto-restart", "-w", ".", "defs/ann", cwd=proj)
        self.wait_ann(m, proj)
        self.ask(m, proj, "question one")
        self.stop_both(m, proj, llms)
        copy_proto(p2)
        shutil.rmtree(base / "p1")
        m.env["AOS_HOME"] = str(p2)
        m.use_proto(p2)
        log("  AOS_HOME -> %s (old copy deleted)" % p2)
        self.start_both(m, proj, llms)
        self.wait_ann(m, proj)
        self.ask(m, proj, "question two")
        self.stop_both(m, proj, llms)
        stale = [h for h in grep_tree(base, str(base / "p1")) if not h.endswith(LOGS)]
        self.assertEqual(stale, [], "files still naming the old proto8")
        log("round env-repoint PASS")


if __name__ == "__main__":
    unittest.main()
