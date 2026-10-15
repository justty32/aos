"""proto8/lib 的自動測試：loop（aos_loop）；起真的 loop 行程、走檔案。只用標準庫：

    python3 -m unittest discover -s proto8/lib/tests

共用的 `Tmp`、路徑在 helpers.py。
"""
import json
import os
import signal
import subprocess
import sys
import time
import unittest
from unittest import mock

from helpers import LOOP, Tmp, alive
import aos_ctl_state  # noqa: E402
import aos_loop  # noqa: E402


class LoopTest(Tmp):
    def loop(self, name="l", sh="true", **outer):
        """寫 NAME.loop.json（inst 內嵌：在暫存資料夾用 sh 跑 SH；窗 NAME.ctl.json、NAME.state.json），回路徑。"""
        inst = outer.pop("inst", {"argv": ["sh", "-c", sh], "cwd": self.tmp})
        return self.write(name + ".loop.json", dict({"inst": inst, "ctl": name + ".ctl.json",
                                                     "state": name + ".state.json"}, **outer))

    def err(self, r):
        """stderr 最後一份錯誤的代號（N-12：{"error": {"code", "msg"}}）。"""
        return json.loads(r.stderr.splitlines()[-1])["error"]["code"]

    def cli(self, path, timeout=10):
        return subprocess.run([sys.executable, LOOP, path], capture_output=True, text=True, cwd=self.tmp, timeout=timeout)

    def start(self, path):
        proc = subprocess.Popen([sys.executable, LOOP, path], cwd=self.tmp, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                text=True)
        self.addCleanup(lambda: proc.poll() is None and proc.kill() or proc.stderr.close())
        return proc

    def state(self, name="l.state.json"):
        try:
            return json.loads(self.read(name))
        except (OSError, ValueError):
            return None

    def ctl(self, doc, name="l.ctl.json"):
        self.write("." + name, doc)
        os.replace(self.p("." + name), self.p(name))

    def test_times_and_last_code(self):
        path = self.loop(sh="echo x >> l.out; exit 3", times=3, state="l.state.json")
        r = self.cli(path)
        self.assertEqual(r.returncode, 0, r.stderr)     # 子程式回 3 不算 loop 出錯
        self.assertEqual(self.read("l.out"), "x\nx\nx\n")
        self.assertEqual([json.loads(x)["code"] for x in r.stdout.splitlines()[:3]], [3, 3, 3])
        st = self.state()
        self.assertEqual((st["id"], st["state"], st["runs"], st["last_code"]),
                         (os.path.realpath(path), "done", 3, 3))
        self.assertEqual(list(st)[:2], ["id", "state"])

    def test_stop_on_end(self):
        # 包的 fsm 走到 end（那行帶 "end": true、from、to）＝loop 正常結束，不靠 ctl；沒寫 stop_on_end 就照 times 跑
        line = '{"from": "a", "to": "a", "end": true}'
        sh = 'echo x >> l.out; n=$(wc -l < l.out); if [ "$n" -ge 2 ]; then echo \'%s\'; echo \'{"next": "z", "end": true}\'; else echo \'{"from": "a", "to": "b"}\'; fi' % line
        r = self.cli(self.loop(sh=sh, times=5, stop_on_end=True))              # 沒寫 stdout：loop 接暫存檔讀
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.read("l.out"), self.state()["state"]), ("x\nx\n", "done"))
        self.assertEqual(json.loads(r.stdout.splitlines()[-1])["end"], "done")
        os.remove(self.p("l.out"))
        inst = {"argv": ["sh", "-c", sh], "cwd": self.tmp, "stdout": "steps.jsonl", "stdout_append": True}
        self.write("steps.jsonl", line + "\n")                                # 以前留下的那行不算
        self.cli(self.loop(inst=inst, times=5, stop_on_end=True))
        self.assertEqual(self.read("l.out"), "x\nx\n")
        os.remove(self.p("l.out"))
        self.cli(self.loop(sh='echo x >> l.out; echo \'{"next": "z", "end": true}\'', times=3, stop_on_end=True))
        self.assertEqual(self.read("l.out"), "x\nx\nx\n")                    # 格的結果帶 end 不算（要是 fsm 那行）
        os.remove(self.p("l.out"))
        self.cli(self.loop(sh=sh, times=4))
        self.assertEqual(self.read("l.out"), "x\nx\nx\nx\n")

    def test_run_api_and_ref(self):
        self.inst("job", "echo y >> j.out")
        path = self.loop(inst={"$ref": "job/inst.json"}, times=2)
        cwd = os.getcwd()
        os.chdir(self.tmp)                  # 相對路徑從呼叫者的 cwd 算
        self.addCleanup(os.chdir, cwd)
        self.assertIsNone(aos_loop.run(path))
        self.assertEqual(self.read("j.out"), "y\ny\n")

    def test_read_once_at_start(self):
        # loop.json（含 inst）只在起來時解一次：跑到一半改檔不影響；要改只能走 ctl.json
        self.inst("job", "echo a >> j.out")
        path = self.loop(inst={"$ref": "job/inst.json"}, times=None, interval_ms=50, ctl="l.ctl.json")
        self.ctl({})
        proc = self.start(path)
        self.until(lambda: os.path.exists(self.p("j.out")))
        self.inst("job2", "echo b >> j.out")
        os.replace(self.p("job2/inst.json"), self.p("job/inst.json"))
        self.write("l.loop.json", {"inst": {"argv": ["false"]}})
        time.sleep(0.3)
        self.ctl({"stop": True})
        self.assertEqual(proc.wait(5), 0)
        self.assertEqual(set(self.read("j.out").split()), {"a"})

    def test_bad_inst_fails_start(self):
        r = self.cli(self.loop(inst={"argv": [{"$env": "AOS_TEST_NOPE"}]}))
        self.assertEqual(r.returncode, 1)                       # loop 只退 0／1（盤點第 1 條），代號在 stderr
        self.assertIn("DirectiveBad", r.stderr)
        self.assertEqual(self.cli(self.loop(inst={"argv": []})).returncode, 1)

    def test_target_pointer(self):
        # loop.json 的一格當 loop 本體；inst 裡的 ../ 照整份檔算；id＝realpath#/位置
        self.write("cmd.json", {"cmd": "echo z >> n.out"})
        path = self.write("node.json", {"job": {"inst": {"argv": ["sh", "-c", {"$ref": "cmd.json#/cmd"}], "cwd": self.tmp},
                                                "times": 2, "state": "n.state.json", "ctl": "n.ctl.json"},
                                        "x": [1]})
        r = self.cli(path + "#/job")
        self.assertEqual((r.returncode, self.read("n.out")), (0, "z\nz\n"), r.stderr)
        self.assertEqual(self.state("n.state.json")["id"], os.path.realpath(path) + "#/job")
        r = self.cli(path + "#/x")                                      # 指到的不是物件
        self.assertEqual((r.returncode, self.err(r)), (1, "FieldType"))
        self.assertIn(os.path.realpath(path) + "#/x", r.stderr)
        r = self.cli(path + "#job")
        self.assertEqual((r.returncode, self.err(r)), (1, "PointerBad"))

    def test_last_code_from_inst_stdout(self):
        # 沒寫 exit 也拿得到碼：aos_inst 的 stdout 結果（N-12）
        self.loop(inst={"argv": ["sh", "-c", "exit 4"]})
        self.assertEqual(self.cli(self.p("l.loop.json")).returncode, 0)
        self.assertEqual(self.state()["last_code"], 4)

    def test_windows_required(self):
        # N-19：ctl／state 缺 key 或 null＝WindowMissing、不執行
        for outer in ({"ctl": None}, {"state": None}):
            with self.subTest(outer=outer):
                path = self.loop(sh="echo x >> w.out", **outer)
                r = self.cli(path)
                self.assertEqual((r.returncode, self.err(r)), (1, "WindowMissing"))
        self.assertFalse(os.path.exists(self.p("w.out")))

    def test_stdout_stream_stdin_flags(self):
        # stdout：每次一份 {run, code, ms}＋總結；設定從 stdin、旗標蓋過；id
        doc = {"inst": {"argv": ["sh", "-c", "exit 3"]}, "times": 5, "ctl": "s.ctl.json", "state": "s.state.json", "id": "me"}
        r = subprocess.run([sys.executable, LOOP, "--times", "2", "-"], input=json.dumps(doc), capture_output=True,
                           text=True, cwd=self.tmp, timeout=10)
        out = [json.loads(x) for x in r.stdout.splitlines()]
        self.assertEqual([(o["run"], o["code"]) for o in out[:2]], [(1, 3), (2, 3)])
        self.assertEqual(out[2], {"end": "done", "runs": 2, "last_code": 3, "signal": None})
        self.assertEqual(self.state("s.state.json")["id"], "me")

    def test_inst_error_not_inherited(self):
        # 最後一次 aos_inst 自己出錯：loop 退 1（不沿用 aos_inst 的 127）、stderr 只有 loop 自己那一份錯誤（aos_inst 的不轉，S2）
        path = self.loop(inst={"argv": ["/no/such/prog"]}, times=2)
        r = self.cli(path)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(len(r.stderr.splitlines()), 1, r.stderr)
        self.assertEqual(self.err(r), "CommandNotFound")
        self.assertTrue(self.state()["last_error"].startswith("CommandNotFound"))
        # 中途出錯後來好了不算：最後一次正常＝0
        self.loop("m", inst={"argv": ["sh", "-c", "[ -e flag ] || { touch flag; exec /no/such; }"], "cwd": self.tmp},
                  times=2)
        self.assertEqual(self.cli(self.p("m.loop.json")).returncode, 0)

    def test_state_write_failed_is_error(self):
        # state 窗寫不了＝窗壞了（同 N-19 窗缺）：收工、stderr 一份 StateWriteFailed、退 1（原本警告一次照跑，10-15「都按照推薦。」）
        path = self.loop(sh="sleep 30", times=None, state="l.loop.json/s.json")     # 上層是個檔，建不了
        r = self.cli(path)
        self.assertEqual((r.returncode, self.err(r)), (1, "StateWriteFailed"))

    def test_bad_loop_json(self):
        w = {"ctl": "c.json", "state": "s.json"}
        for doc in (dict(w, times=1), dict(w, inst={"argv": ["true"]}, times=-1),
                    dict(w, inst={}, interval_ms="x"), "{"):
            with self.subTest(doc=doc):
                r = self.cli(self.write("bad.json", doc))
                self.assertEqual(r.returncode, 1)
        self.assertEqual(self.cli(self.p("nope.json")).returncode, 1)

    def test_want_reverts_to_initial(self):
        init = {"paused": False, "times": 3}
        self.assertEqual(aos_ctl_state.want(init, {"times": 5})["times"], 5)
        self.assertEqual(aos_ctl_state.want(init, {})["times"], 3)
        self.assertEqual(aos_ctl_state.parse_ctl({"stop": True, "paused": True, "x": 1}), {"stop": True, "paused": True})
        for bad in ([], {"stop": "yes"}, {"paused": {"val": True, "now": True}}, {"times": "5"}):    # 旗子只收布林
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                aos_ctl_state.parse_ctl(bad)

    def test_ctl_same_stat_change_detected(self):
        """4 ms 內等長改名蓋過：ino／mtime／size 全撞（ext4 實測會發生），第二次仍要讀到；壞檔維持上一次。"""
        ctl = aos_ctl_state.CtlFile(self.p("c.json"))
        aos_ctl_state.write_json(self.p("c.json"), {"times": 5})
        fixed = os.stat(self.p("c.json"))
        with mock.patch("os.stat", return_value=fixed), mock.patch("os.fstat", return_value=fixed):
            ctl.poll()
            self.assertEqual(ctl.good, {"times": 5})
            aos_ctl_state.write_json(self.p("c.json"), {"times": 6})     # 等長
            ctl.poll()
            self.assertEqual(ctl.good, {"times": 6})
            aos_ctl_state.write_json(self.p("c.json"), {"paused": True})
            ctl.poll()
            self.assertEqual(ctl.good, {"paused": True})
            with open(self.p("c.json"), "w") as f:                    # 壞檔：維持上一次
                f.write("{")
            ctl.poll()
            self.assertEqual(ctl.good, {"paused": True})

    def test_ctl_seq_and_heartbeat(self):
        """ctl 帶流水號 seq，回報 ctl_seq（不進 good）；state 帶心跳欄位，內容沒變也每 beat_ms 碰一次。"""
        ctl = aos_ctl_state.CtlFile(self.p("c.json"))
        aos_ctl_state.write_json(self.p("c.json"), {"times": 5, "seq": 7})
        ctl.poll()
        self.assertEqual((ctl.good, ctl.seq), ({"times": 5}, 7))
        with self.assertRaises(ValueError):
            aos_ctl_state.parse_ctl({"seq": "7"})
        w = {"times": 1, "interval_ms": 0}
        st = aos_ctl_state.state_doc("x", "waiting", w, ctl, 0, None)
        self.assertEqual((st["ctl_seq"], st["pid"]), (7, os.getpid()))
        self.assertTrue(isinstance(st["started"], int) and st["boot_id"])
        sf = aos_ctl_state.StateFile(self.p("s.json"), "t", beat_ms=50)
        sf.write(st)
        b1 = self.state("s.json")["beat"]
        sf.write(st)
        self.assertEqual(self.state("s.json")["beat"], b1)       # 沒到時間、內容沒變：不寫
        time.sleep(0.06)
        sf.write(st)
        self.assertGreater(self.state("s.json")["beat"], b1)     # 心跳

    def test_ctl_pause_then_times_exits_when_done(self):
        self.ctl({"paused": True})
        path = self.loop(sh="echo x >> l.out", times=None, interval_ms=20, ctl="l.ctl.json", state="l.state.json")
        proc = self.start(path)
        self.until(lambda: (self.state() or {}).get("state") == "paused")
        time.sleep(0.2)
        self.assertFalse(os.path.exists(self.p("l.out")))
        self.ctl({"times": 2, "seq": 3})                # paused 沒寫＝回到初始值（false）
        self.assertEqual(proc.wait(5), 0)               # 次數跑完就退出，有 ctl 也一樣
        self.assertEqual(self.read("l.out"), "x\nx\n")
        st = self.state()
        self.assertEqual((st["state"], st["runs"]), ("done", 2))
        self.assertEqual(st["ctl_seq"], 3)

    def test_bad_ctl_then_stop(self):
        self.ctl({})
        path = self.loop(sh="sleep 0.1", times=None, ctl="l.ctl.json")
        proc = self.start(path)
        self.until(lambda: self.state())
        self.ctl("{")                                   # 壞檔：整份不採用、記進 state 的 last_warning、照跑（N-08）
        self.until(lambda: ((self.state() or {}).get("last_warning") or "").startswith("CtlBad"))
        os.remove(self.p("l.ctl.json"))                 # 不見了：維持上一次
        self.until(lambda: ((self.state() or {}).get("last_warning") or "").startswith("CtlMissing"))
        self.assertIsNone(proc.poll())
        self.ctl({"stop": True})                        # stop 只收布林；這次跑完就結束（當場收掉＝送訊號）
        self.assertEqual(proc.wait(5), 0)
        self.assertIsNone(self.state()["last_warning"])  # 讀到好的就清掉
        self.assertEqual(proc.stderr.read(), "")         # 不寫 stderr（N-43）

    def test_sigterm_clears_group(self):
        path = self.loop(sh="sleep 30 & echo $! > l.pid; wait", times=None)
        proc = self.start(path)
        self.until(lambda: os.path.exists(self.p("l.pid")) and self.read("l.pid").strip())
        pid = int(self.read("l.pid"))
        proc.send_signal(signal.SIGTERM)
        self.assertEqual(proc.wait(5), 1)                 # 被訊號停＝1（原 128＋N），哪個訊號記在 state 窗
        self.assertEqual(self.state()["signal"], signal.SIGTERM)
        self.until(lambda: not alive(pid))

    def test_grandchildren_cleared_after_run(self):
        self.cli(self.loop(sh="sleep 30 & echo $! > l.pid"))
        pid = int(self.read("l.pid"))
        self.until(lambda: not alive(pid))


if __name__ == "__main__":
    unittest.main()
