"""aos-daemon 第三段驗收（plan m3-daemon-core.md）。真的開 bin/aos-daemon 子程序。

都用暫存資料夾、短週期、假 inst；不要 root、systemd、網路。
daemon 不殺子程序（步驟 5），所以會留下來的任務一律把自己的 pid 寫進 `pids`，測試收尾時連同
它的 process group 一起殺掉（任務被 aos-exec 開在自己的 session，pid 就是 group id）。
"""
import json
import os
import re
import signal
import subprocess
import threading
import time
import unittest

from _util import Base, PY

import aos_daemon

HERE = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.join(os.path.dirname(HERE), "bin")
DAEMON = os.path.join(BIN, "aos-daemon")
TICK = os.path.join(BIN, "aos-tick")

CLEAN_ENV = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}

TS = r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d"
LINE = re.compile(r"^(%s) inst=(\S+) (?:exit=(\d+) ms=(\d+)|(stopped))$" % TS)
HEAD = re.compile(r"^== %s (stdout|stderr) index=(\d+) inst=(\S+) ==$" % TS)


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


class Step1Config(DaemonCase):

    def test_inst_is_literal(self):
        self.inst({"argv": ["true"]}, "a/inst.json")
        abs_inst = os.path.join(self.d, "a", "inst.json")
        cfg = self.config({"interval_ms": 100, "insts": {"a": {}, "./a": {},
                                                         abs_inst: {}}})
        _, out, _ = self.start(cfg)
        for inst in ("a", "./a", abs_inst):
            self.wait_for(lambda: self.results(out, inst) and True)
            self.assertEqual(self.results(out, inst)[0], 0)

    def test_start_dir(self):
        self.inst({"argv": ["true"]}, "sub/x.json")
        self.inst({"argv": ["true"]}, "other/y.json")
        os.makedirs(os.path.join(self.d, "run"))
        # 相對的 cwd 以 daemon 啟動時的工作目錄為起點
        cfg = self.config({"cwd": "../sub", "interval_ms": 100, "insts": {"x.json": {}}})
        _, out, _ = self.start(cfg, cwd=os.path.join(self.d, "run"))
        # 絕對的 cwd
        cfg2 = self.config({"cwd": os.path.join(self.d, "other"), "interval_ms": 100,
                            "insts": {"y.json": {}}}, "c2.json")
        _, out2, _ = self.start(cfg2)
        # 沒寫 cwd：daemon 啟動時的工作目錄
        cfg3 = self.config({"interval_ms": 100, "insts": {"sub/x.json": {}}}, "c3.json")
        _, out3, _ = self.start(cfg3)
        self.wait_for(lambda: self.results(out, "x.json") and self.results(out2, "y.json")
                      and self.results(out3, "sub/x.json"))
        self.assertEqual(self.results(out, "x.json")[0], 0)
        self.assertEqual(self.results(out2, "y.json")[0], 0)
        self.assertEqual(self.results(out3, "sub/x.json")[0], 0)

    def test_defaults_and_override(self):
        cfg = self.config({"cwd": "/base", "interval_ms": 7, "stop_on_nonzero": True,
                           "exec_err_path": "<inst>/err.log", "insts": {
                               "a": {}, "b": {"interval_ms": 9, "stop_on_nonzero": False}}})
        start, items = aos_daemon.load_config(cfg)
        self.assertEqual(start, "/base")
        self.assertEqual([(i.index, i.inst, i.interval_ms, i.stop_on_nonzero) for i in items],
                         [(0, "a", 7, True), (1, "b", 9, False)])
        # index 照物件鍵的順序（不是字母序）
        cfg = self.config({"interval_ms": 5, "insts": {"z": {}, "a": {}, "m": {}}}, "order.json")
        self.assertEqual([(i.index, i.inst) for i in aos_daemon.load_config(cfg)[1]],
                         [(0, "z"), (1, "a"), (2, "m")])
        cfg = self.config({"insts": {"a": {"interval_ms": 5}}})
        start, items = aos_daemon.load_config(cfg)
        self.assertEqual(start, os.getcwd())
        self.assertFalse(items[0].stop_on_nonzero)
        self.assertIsNone(items[0].err_path)       # 沒寫＝丟掉（/dev/null，使用者 2026-10-01）
        self.assertIsNone(items[0].out_path)

    def test_err_path(self):
        os.makedirs(os.path.join(self.d, "dir"))
        f = aos_daemon.err_path_for
        self.assertEqual(f("<inst>/err.log", "j/x.json", "/s"), "/s/j/err.log")
        self.assertEqual(f("<inst>/err.log", "x.json", "/s"), "/s/./err.log")
        self.assertEqual(f("<inst>/err.log", "dir", self.d), os.path.join(self.d, "dir/err.log"))
        self.assertEqual(f("/abs/<inst>.err", "/n/a/inst.json", "/s"), "/abs//n/a.err")
        self.assertEqual(f("logs/all.err", "dir", "/s"), "/s/logs/all.err")
        self.assertIsNone(f(None, "dir", "/s"))

    def test_no_interval(self):
        r = self.run_cfg(self.config({"insts": {"a": {"interval_ms": 5}, "b": {}}}))
        self.assertEqual(r.returncode, 1)
        self.assertIn('insts 的 "b"', r.stderr)

    def test_usage(self):
        self.assertEqual(self.run_cfg([]).returncode, 1)
        cfg = self.config({"interval_ms": 5, "insts": {}})
        self.assertEqual(self.run_cfg(["--config", cfg, "--what"]).returncode, 1)

    def test_bad_file(self):
        self.assertEqual(self.run_cfg(os.path.join(self.d, "nope.json")).returncode, 1)
        self.assertEqual(self.run_cfg(self.write("bad.json", "{")).returncode, 1)



class Step1Directives(DaemonCase):
    """整份設定檔先經 aos 指示詞展開再讀（使用者 2026-10-01）：`$ref` 以設定檔所在資料夾為準，
    展開完才套 `cwd` 規則（daemon 啟動時的工作目錄）；頂層 `modules` 認得，只讀 `control`（m3n）。"""

    def test_ref_split_insts_and_defaults(self):
        # 設定檔放在 conf/，daemon 從 self.d 開：$ref 照 conf/ 找，inst 照 daemon 的工作目錄找
        self.inst({"argv": ["true"]}, "x.json")
        self.write("conf/list.json", json.dumps({"x.json": {}, "y": {"interval_ms": 9}}))
        self.write("conf/defaults.json", json.dumps({"interval_ms": 100, "stop_on_nonzero": True}))
        cfg = self.config({"interval_ms": {"$ref": "defaults.json#/interval_ms"},
                           "stop_on_nonzero": {"$ref": "defaults.json", "$at": "/stop_on_nonzero"},
                           "insts": {"$ref": "list.json"}}, "conf/daemon.json")
        start, items = aos_daemon.load_config(cfg)
        self.assertEqual([(i.index, i.inst, i.interval_ms, i.stop_on_nonzero) for i in items],
                         [(0, "x.json", 100, True), (1, "y", 9, True)])
        # 單一項的設定也能引：list.json 裡 x.json 那項
        cfg2 = self.config({"interval_ms": {"$ref": "defaults.json#/interval_ms"},
                            "insts": {"x.json": {"$ref": "list.json", "$at": "/x.json"}}}, "conf/one.json")
        _, out, _ = self.start(cfg2)
        self.wait_for(lambda: len(self.results(out, "x.json")) >= 2)
        self.assertEqual(set(self.results(out, "x.json")), {0})

    def test_cwd_from_ref(self):
        # cwd 的值從別檔引進；引進來的相對值照樣以 daemon 啟動時的工作目錄為起點，不是設定檔的資料夾
        self.inst({"argv": ["true"]}, "nodes/x.json")
        self.write("conf/where.json", json.dumps({"cwd": "nodes"}))
        cfg = self.config({"cwd": {"$ref": "where.json#/cwd"}, "interval_ms": 100,
                           "insts": {"x.json": {}}}, "conf/daemon.json")
        _, out, _ = self.start(cfg)
        self.wait_for(lambda: self.results(out, "x.json"))
        self.assertEqual(self.results(out, "x.json")[0], 0)

    def test_modules_ignored(self):
        self.inst({"argv": ["true"]}, "x.json")
        cfg = self.config({"interval_ms": 100, "insts": {"x.json": {}},
                           # m3n 起 control 有寫就掛控制模組（見 test_ctl.py），這裡改用不認得的模組名（m3n 改）
                           "modules": {"later": {"socket": "./aos.sock", "whatever": [1, {"$opt": "x"}]},
                                       "other": 3}})
        _, out, err = self.start(cfg)
        self.wait_for(lambda: self.results(out, "x.json"))
        self.assertEqual(self.results(out, "x.json")[0], 0)
        self.assertFalse(self.exists("aos.sock"))
        r = self.run_cfg(self.config({"interval_ms": 5, "insts": {}, "modules": []}, "bad.json"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("modules", r.stderr)

    def test_directive_error(self):
        r = self.run_cfg(self.config({"interval_ms": {"$ref": "nope.json"}, "insts": {}}))
        self.assertEqual(r.returncode, 1)
        self.assertIn("ReferenceReadFailed", r.stderr)
        r = self.run_cfg(self.config({"interval_ms": 5, "insts": {"$ref": "", "$at": ".."}}, "c.json"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("ReferenceCycle", r.stderr)

class Step2Once(DaemonCase):

    def test_exit_codes_and_line(self):
        self.inst(sh("exit 3"), "three.json")
        self.inst({"argv": ["true"]}, "ok.json")
        cfg = self.config({"interval_ms": 100, "insts": {"three.json": {}, "ok.json": {}}})
        _, out, _ = self.start(cfg)
        self.wait_for(lambda: self.results(out, "three.json") and self.results(out, "ok.json"))
        self.assertEqual(self.results(out, "three.json")[0], 3)
        self.assertEqual(self.results(out, "ok.json")[0], 0)
        for line in list(out):
            self.assertRegex(line, LINE)

    def test_own_session(self):
        # 任務的父程序就是 aos-exec；它自成 session＝sid 等於自己的 pid
        self.inst({"argv": [PY, "-c", "import os; p=os.getppid(); print(p, os.getsid(p))"],
                   "stdout": "sid.txt"}, "s.json")
        p, out, _ = self.start(self.config({"interval_ms": 10000, "insts": {"s.json": {}}}))
        self.wait_for(lambda: self.results(out, "s.json"))
        ppid, sid = self.read("sid.txt").split()
        self.assertEqual(ppid, sid)
        self.assertNotEqual(int(sid), os.getsid(p.pid))

    def test_default_discard(self):
        # exec_out_path／exec_err_path 沒寫＝丟到 /dev/null：daemon 的 stdout 只有自己那幾行、stderr 空
        self.inst(sh("echo said; echo oops >&2", stdout=INHERIT, stderr=INHERIT), "loud.json")
        p, out, err = self.start(self.config({"interval_ms": 50, "insts": {"loud.json": {}, "nope": {}}}))
        self.wait_for(lambda: len(self.results(out, "loud.json")) >= 3 and self.results(out, "nope"))
        for line in list(out):
            self.assertRegex(line, LINE)
        self.assertEqual(err, [])
        self.assertIsNone(p.poll())

    def test_to_daemon_streams(self):
        # 寫成 /dev/stderr、/dev/stdout 就接回 daemon 自己的 stderr／stdout，照樣帶標頭
        self.inst(sh("echo oops >&2; echo two >&2; echo said", stdout=INHERIT, stderr=INHERIT),
                  "loud.json")
        self.inst(sh("echo hidden >&2"), "quiet.json")
        cfg = self.config({"interval_ms": 10000, "exec_err_path": "/dev/stderr",
                           "exec_out_path": "/dev/stdout",
                           "insts": {"quiet.json": {}, "loud.json": {}}})
        _, out, err = self.start(cfg)
        self.wait_for(lambda: self.results(out, "loud.json") and self.results(out, "quiet.json"))
        self.wait_for(lambda: len(err) >= 3)
        m = HEAD.match(err[0])
        self.assertTrue(m, err)
        self.assertEqual(m.groups(), ("stderr", "1", "loud.json"))
        self.assertEqual(err[1:], ["oops", "two"])
        i = next(k for k, l in enumerate(list(out)) if HEAD.match(l))
        self.assertEqual(HEAD.match(out[i]).groups(), ("stdout", "1", "loud.json"))
        self.assertEqual(out[i + 1], "said")

    def test_exec_own_stderr(self):
        # aos-exec 自己的錯（目標不存在＝用法錯 1）也在它的 stderr 裡
        _, out, err = self.start(self.config({"interval_ms": 10000, "exec_err_path": "/dev/stderr",
                                              "insts": {"nope": {}}}))
        self.wait_for(lambda: self.results(out, "nope"))
        self.assertEqual(self.results(out, "nope"), [1])
        self.wait_for(lambda: len(err) >= 2)
        self.assertEqual(HEAD.match(err[0]).groups(), ("stderr", "0", "nope"))

    def test_err_file_per_inst(self):
        self.inst(sh("echo from-j >&2", stderr=INHERIT), "j/x.json")
        self.inst(sh("echo from-a >&2", stderr=INHERIT), "a/inst.json")
        cfg = self.config({"interval_ms": 100, "exec_err_path": "<inst>/logs/err.log",
                           "insts": {"j/x.json": {}, "a": {}}})
        _, out, err = self.start(cfg)
        self.wait_for(lambda: len(self.results(out, "j/x.json")) >= 2 and len(self.results(out, "a")) >= 2)
        for rel, idx, inst, text in (("j/logs/err.log", "0", "j/x.json", "from-j"),
                                     ("a/logs/err.log", "1", "a", "from-a")):
            lines = self.read(rel).splitlines()
            self.assertGreaterEqual(len(lines), 4)          # 接在檔尾：至少兩次
            self.assertEqual(HEAD.match(lines[0]).groups(), ("stderr", idx, inst))
            self.assertEqual(lines[1], text)
        self.assertEqual(err, [])

    def test_out_file_per_inst_and_shared(self):
        # exec_out_path 同一套規則：<inst> 替換、接檔尾、父資料夾自動建；跟 err 寫同一個檔時用標頭分
        self.inst(sh("echo out-j; echo err-j >&2", stdout=INHERIT, stderr=INHERIT), "j/x.json")
        cfg = self.config({"interval_ms": 100, "exec_out_path": "<inst>/logs/out.log",
                           "exec_err_path": "logs/e1.log", "insts": {"j/x.json": {}}})
        _, out, err = self.start(cfg)
        self.wait_for(lambda: len(self.results(out, "j/x.json")) >= 2)
        lines = self.read("j/logs/out.log").splitlines()
        self.assertGreaterEqual(len(lines), 4)
        self.assertEqual(HEAD.match(lines[0]).groups(), ("stdout", "0", "j/x.json"))
        self.assertEqual(lines[1], "out-j")
        cfg2 = self.config({"interval_ms": 100, "exec_out_path": "logs/both.log",
                            "exec_err_path": "logs/both.log", "insts": {"j/x.json": {}}}, "c2.json")
        _, out2, _ = self.start(cfg2)
        self.wait_for(lambda: len(self.results(out2, "j/x.json")) >= 2)
        lines = self.read("logs/both.log").splitlines()
        self.assertEqual([HEAD.match(l).group(1) for l in lines[0:4:2]], ["stdout", "stderr"])
        self.assertEqual(lines[1:4:2], ["out-j", "err-j"])
        self.assertEqual(err, [])

    def test_err_file_shared_no_interleave(self):
        burst = "i=0; while [ $i -lt 300 ]; do echo %s$i >&2; i=$((i+1)); done"
        self.inst(sh(burst % "A", stderr=INHERIT), "a.json")
        self.inst(sh(burst % "B", stderr=INHERIT), "b.json")
        cfg = self.config({"interval_ms": 20, "exec_err_path": "logs/all.err",
                           "insts": {"a.json": {}, "b.json": {}}})
        _, out, _ = self.start(cfg)
        self.wait_for(lambda: len(self.results(out, "a.json")) >= 3 and len(self.results(out, "b.json")) >= 3)
        letter = None
        heads = 0
        for line in self.read("logs/all.err").splitlines():
            m = HEAD.match(line)
            if m:
                heads += 1
                letter = {"a.json": "A", "b.json": "B"}[m.group(3)]
                self.assertEqual(m.group(2), {"A": "0", "B": "1"}[letter])
            else:
                self.assertEqual(line[0], letter, line)
        self.assertGreaterEqual(heads, 6)


class Step3Period(DaemonCase):

    def test_first_run_and_repeat(self):
        self.inst(sh("echo x >> runs"), "r.json")
        _, out, _ = self.start(self.config({"interval_ms": 100, "insts": {"r.json": {}}}))
        self.wait_for(lambda: self.exists("runs"), timeout=2)
        self.wait_for(lambda: len(self.results(out, "r.json")) >= 4, timeout=3)

    def test_no_overlap(self):
        self.inst(sh("echo start >> log; sleep 0.3; echo end >> log"), "s.json")
        _, out, _ = self.start(self.config({"interval_ms": 50, "insts": {"s.json": {}}}))
        self.wait_for(lambda: len(self.results(out, "s.json")) >= 3)
        log = self.read("log").split()
        self.assertEqual(log[:6], ["start", "end"] * 3)
        ms = [int(LINE.match(l).group(4)) for l in list(out) if LINE.match(l)]
        self.assertTrue(all(m >= 300 for m in ms), ms)

    def test_stuck_does_not_block_others(self):
        self.inst(sh("echo $$ >> pids; exec sleep 30"), "stuck.json")
        self.inst({"argv": ["true"]}, "ok.json")
        cfg = self.config({"interval_ms": 50, "insts": {"stuck.json": {}, "ok.json": {}}})
        _, out, _ = self.start(cfg)
        self.wait_for(lambda: len(self.results(out, "ok.json")) >= 4)
        self.assertEqual(self.results(out, "stuck.json"), [])


class Step4Stop(DaemonCase):

    def test_stop(self):
        self.inst({"argv": ["false"]}, "f.json")
        self.inst({"argv": ["true"]}, "ok.json")
        cfg = self.config({"interval_ms": 50, "insts": {
            "f.json": {"stop_on_nonzero": True}, "ok.json": {}}})
        p, out, _ = self.start(cfg)
        self.wait_for(lambda: any(l.endswith(" inst=f.json stopped") for l in list(out)))
        n_ok = len(self.results(out, "ok.json"))
        time.sleep(0.6)
        self.assertEqual(self.results(out, "f.json"), [1])
        self.assertEqual(sum(1 for l in list(out) if l.endswith("stopped")), 1)
        self.assertGreater(len(self.results(out, "ok.json")), n_ok)
        self.assertIsNone(p.poll())

    def test_all_stopped_stays_open(self):
        p, out, _ = self.start(self.config({"interval_ms": 50, "stop_on_nonzero": True,
                                            "insts": {"nope": {}}}))
        self.wait_for(lambda: any(l.endswith("stopped") for l in list(out)))
        self.assertEqual(self.results(out, "nope"), [1])     # 目標不存在：aos-exec 用法錯 1
        time.sleep(0.4)
        self.assertIsNone(p.poll())                         # 全停了 daemon 照樣開著

    def test_no_stop(self):
        self.inst({"argv": ["false"]}, "f.json")
        _, out, _ = self.start(self.config({"interval_ms": 50, "insts": {"f.json": {}}}))
        self.wait_for(lambda: len(self.results(out, "f.json")) >= 3)
        self.assertEqual(set(self.results(out, "f.json")), {1})
        self.assertFalse(any(l.endswith("stopped") for l in list(out)))

    def test_zero_never_stops(self):
        self.inst({"argv": ["true"]}, "t.json")
        _, out, _ = self.start(self.config({"interval_ms": 50, "stop_on_nonzero": True,
                                            "insts": {"t.json": {}}}))
        self.wait_for(lambda: len(self.results(out, "t.json")) >= 3)
        self.assertFalse(any(l.endswith("stopped") for l in list(out)))


class Step5Signals(DaemonCase):

    def check(self, sig):
        self.inst({"argv": ["true"]}, "t.json")
        p, out, _ = self.start(self.config({"interval_ms": 50, "insts": {"t.json": {}}}))
        self.wait_for(lambda: out)
        os.kill(p.pid, sig)
        self.assertEqual(p.wait(timeout=1), 0)

    def test_sigint(self):
        self.check(signal.SIGINT)

    def test_sigterm(self):
        self.check(signal.SIGTERM)

    def test_children_survive(self):
        self.inst(sh("echo $$ >> pids; touch began; sleep 0.5; touch done"), "s.json")
        p, out, _ = self.start(self.config({"interval_ms": 10000, "insts": {"s.json": {}}}))
        self.wait_for(lambda: self.exists("began"))
        os.kill(p.pid, signal.SIGTERM)
        self.assertEqual(p.wait(timeout=1), 0)
        self.assertFalse(self.exists("done"))
        self.wait_for(lambda: self.exists("done"), timeout=3)


def tasks_json(*tasks):
    return json.dumps({"_metainfo": {"_type": "aos-tasks", "_version": 1}, "tasks": list(tasks)})


class Step6Tick(DaemonCase):
    """node 當模組：daemon 不認得 node，只叫 aos-exec 跑一份 argv 是 aos-tick 的 inst。"""

    def setUp(self):
        super().setUp()
        self.node = os.path.join(self.d, "n", "a")
        self.inst({"argv": [TICK], "stderr": INHERIT}, "n/a/inst.json")
        self.write("n/a/.aos/tasks.json", tasks_json({"id": "t", "argv": ["true"]}))

    def seq(self):
        p = os.path.join(self.node, ".aos", "tick", "current.json")
        if not os.path.exists(p):
            return 0
        with open(p, encoding="utf-8") as f:
            return json.load(f)["seq"]

    def test_inst_path(self):
        inst = os.path.join(self.node, "inst.json")
        _, out, _ = self.start(self.config({"interval_ms": 100, "insts": {inst: {}}}))
        self.wait_for(lambda: self.seq() >= 3)
        self.wait_for(lambda: len(self.results(out, inst)) >= 3)
        self.assertEqual(set(self.results(out, inst)), {0})

    def test_dir_path(self):
        _, out, _ = self.start(self.config({"interval_ms": 100, "insts": {self.node: {}}}))
        self.wait_for(lambda: len(self.results(out, self.node)) >= 2)
        self.assertEqual(set(self.results(out, self.node)), {0})
        self.assertGreaterEqual(self.seq(), 2)

    def test_blocked(self):
        self.write("n/a/.aos/tick-blocked", "人手暫停")
        _, out, err = self.start(self.config({"interval_ms": 50, "exec_err_path": "/dev/stderr",
                                              "insts": {"n/a": {}}}))
        self.wait_for(lambda: len(self.results(out, "n/a")) >= 3)
        self.assertEqual(set(self.results(out, "n/a")), {0})
        self.assertEqual(self.seq(), 0)
        self.assertTrue(any(l.startswith("blocked:") for l in list(err)), err)
        os.remove(os.path.join(self.node, ".aos", "tick-blocked"))
        self.wait_for(lambda: self.seq() >= 2)

    def test_bad_table(self):
        self.write("n/a/.aos/tasks.json", "{")
        _, out, _ = self.start(self.config({"interval_ms": 50, "stop_on_nonzero": True,
                                            "insts": {"n/a": {}}}))
        self.wait_for(lambda: any(l.endswith(" inst=n/a stopped") for l in list(out)))
        self.assertEqual(self.results(out, "n/a"), [1])

    def test_two_daemons(self):
        cfg = self.config({"interval_ms": 10, "insts": {"n/a": {}}})
        _, out1, _ = self.start(cfg)
        _, out2, _ = self.start(cfg)
        self.wait_for(lambda: len(self.results(out1, "n/a")) >= 5 and len(self.results(out2, "n/a")) >= 5)
        self.assertEqual(set(self.results(out1, "n/a") + self.results(out2, "n/a")), {0})
        self.assertGreaterEqual(self.seq(), 1)


if __name__ == "__main__":
    unittest.main()
