"""test_agent_spec_loop_live - defs.loop for real: two agents compiled with the installed aos, one with loop=defs.loop(interval_ms=1000) and one without, each with a one-state machine that writes the time of every tick; mounted on a copy of start-api's root daemon (no brain), the measured pause between ticks is about 1000 ms and about 300 ms."""
import json
import os
from pathlib import Path
import shutil
import signal
import statistics
import subprocess
import sys
import tempfile
import time
import unittest

PROTO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROTO / "lib"))          # the installed copy (the same as the commands in bin/)
from aos.py import agent, daemon_ctl, Failed  # noqa: E402

ENV = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
ENV.update(AOS_HOME=str(PROTO), PATH=str(PROTO / "bin") + os.pathsep + ENV["PATH"], PYTHONDONTWRITEBYTECODE="1")
BODY = '''
agent = defs.Agent(
    "Write the time of every tick.",
    system="",
    tools=[],
    llm={},
    fsm=defs.fsm("tick", [defs.state("tick", ["sh", "-c", "date +%%s%%N >> %s"], "tick")]),%s
)
defs.main(agent)
'''


def until(cond, timeout=30, every=0.1):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        v = cond()
        if v:
            return v
        time.sleep(every)
    raise AssertionError("timed out")


@unittest.skipUnless((PROTO / "bin" / "aos-exec").exists(), "needs an installed tree (bin/aos-exec)")
class Live(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(os.path.realpath(tempfile.mkdtemp(prefix="loop-live-")))
        cls.tree = cls.tmp / "tree"
        shutil.copytree(PROTO / "templates" / "start-api", cls.tree, symlinks=True)
        head = (PROTO / "templates" / "agent-python" / "agent.py").read_text().split("# ---- your agent")[0]
        cls.compiled = {}
        for name, loop in (("slow", "\n    loop=defs.loop(interval_ms=1000),"), ("plain", "")):
            d = cls.tree / "agents" / name
            d.mkdir(parents=True)
            (d / "agent.py").write_text(head + BODY % (cls.tmp / ("%s.ticks" % name), loop))
            cls.compiled[name] = subprocess.run([sys.executable, str(d / "agent.py"), "--compile"], env=ENV, text=True,
                                                capture_output=True, timeout=60)
        cls.procs, cls.log = [], open(cls.tmp / "root.log", "w")
        cls.daemon = str(cls.tree / ".stack")
        try:
            cls.procs.append(subprocess.Popen(["aos-exec", "root"], cwd=cls.tree, env=ENV, stdin=subprocess.DEVNULL,
                                              stdout=cls.log, stderr=subprocess.STDOUT, start_new_session=True))
            until(lambda: (cls.tree / ".stack" / "state.json").exists())
            os.environ.update(AOS_HOME=str(PROTO), PATH=ENV["PATH"])
            for k in [k for k in os.environ if k.startswith("AOS_") and k != "AOS_HOME"]:
                del os.environ[k]
            for name, r in cls.compiled.items():
                if r.returncode == 0:
                    agent.ctl.add(str(cls.tree / "agents" / name), daemon=cls.daemon, w=str(cls.tree))
            time.sleep(6)                                   # about 6 ticks of the slow one, 20 of the plain one (they go on until shutdown)
        except Exception:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        try:
            try:
                daemon_ctl.shutdown(daemon=cls.daemon)
            except Failed:
                pass
            for p in cls.procs:
                try:
                    p.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    os.killpg(p.pid, signal.SIGKILL)          # only the group this test started
                    p.wait()
        finally:
            cls.log.close()
            shutil.rmtree(cls.tmp, ignore_errors=True)

    def pauses(self, name):
        self.assertEqual(self.compiled[name].returncode, 0, self.compiled[name].stderr)
        ticks = [int(x) / 1e6 for x in (self.tmp / ("%s.ticks" % name)).read_text().split()]
        self.assertGreaterEqual(len(ticks), 4, ticks)
        return [b - a for a, b in zip(ticks, ticks[1:])]

    def test_loop_json(self):
        for name, ms in (("slow", 1000), ("plain", 300)):
            self.assertEqual(json.loads((self.tree / "agents" / name / "loop.json").read_text())["interval_ms"], ms)

    def test_measured_pause(self):
        slow, plain = statistics.median(self.pauses("slow")), statistics.median(self.pauses("plain"))
        print("\nmeasured median pause between ticks: slow %.0f ms, plain %.0f ms" % (slow, plain))
        self.assertTrue(950 <= slow <= 1500, slow)          # 1000 ms pause + the time the tick itself takes
        self.assertTrue(280 <= plain <= 700, plain)


if __name__ == "__main__":
    unittest.main()
