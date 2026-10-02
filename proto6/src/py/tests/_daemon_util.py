"""aos-daemon 系列測試共用：路徑、正規式、sh()／tasks_json() 與 DaemonCase 基底。"""
import json
import os
import re
import signal
import subprocess
import threading
import time

from _util import Base, PY


HERE = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.join(os.path.dirname(HERE), "bin")
DAEMON = os.path.join(BIN, "aos-daemon")
TICK = os.path.join(BIN, "aos-tick")

CLEAN_ENV = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}

TS = r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d"
LINE = re.compile(r"^(%s) inst=(\S+) (?:exit=(\d+) ms=(\d+)|(stopped))$" % TS)


def sh(script, **extra):
    return dict({"argv": ["sh", "-c", script]}, **extra)


INHERIT = {"$opt": "inherit"}


class DaemonCase(Base):

    def setUp(self):
        super().setUp()
        self.addCleanup(self._kill_leftovers)

    def _kill_leftovers(self):
        if not self.exists("pids"):
            return
        for pid in self.read("pids").split():
            try:
                os.killpg(int(pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass

    def config(self, obj, rel="config.json"):
        return self.write(rel, json.dumps(obj, ensure_ascii=False))

    def start(self, cfg, cwd=None):
        """開一個 daemon；stdout／stderr 各一條執行緒收成行。回 (Popen, out 行串列, err 行串列)。"""
        p = subprocess.Popen([PY, DAEMON, "--config", cfg], cwd=cwd or self.d, env=CLEAN_ENV,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                             start_new_session=True)
        out, err = [], []
        for stream, sink in ((p.stdout, out), (p.stderr, err)):
            threading.Thread(target=lambda s=stream, k=sink: [k.append(x.rstrip("\n")) for x in s],
                             daemon=True).start()
        self.addCleanup(self._stop, p)
        return p, out, err

    def _stop(self, p):
        if p.poll() is None:
            p.kill()
        p.wait()
        # 留下的 aos-exec 還拿著 daemon 的 stdout；先殺掉任務讓它結束，關 pipe 才不會卡住
        self._kill_leftovers()
        p.stdout.close()
        p.stderr.close()

    def wait_for(self, pred, timeout=5.0):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if pred():
                return
            time.sleep(0.02)
        self.fail("等不到條件成立")

    def run_cfg(self, cfg, cwd=None):
        """會馬上結束的 daemon（設定錯、用法錯）：回 CompletedProcess。"""
        args = [PY, DAEMON] + (["--config", cfg] if isinstance(cfg, str) else list(cfg))
        return subprocess.run(args, cwd=cwd or self.d, env=CLEAN_ENV, capture_output=True,
                              text=True, timeout=10)

    @staticmethod
    def results(out, inst):
        """某 inst（字面值）的結束碼串列（照印出的順序）。"""
        r = []
        for line in list(out):
            m = LINE.match(line)
            if m and m.group(2) == inst and m.group(3) is not None:
                r.append(int(m.group(3)))
        return r


def tasks_json(*tasks):
    return json.dumps({"_metainfo": {"_type": "aos-tasks", "_version": 1}, "tasks": list(tasks)})
