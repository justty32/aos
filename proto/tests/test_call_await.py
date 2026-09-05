"""aosp/execute.py 的 call(sync) / await：三態、呼叫記錄、子指令的環境變數。"""
import json
import os
import sys

PROTO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROTO not in sys.path:
    sys.path.insert(0, PROTO)

from aosp import execute, fsutil, layout, series as S, status  # noqa: E402
from .helpers import LandCase, write_source  # noqa: E402

PY = sys.executable


class TestSyncCallHoldsWhileChildBusy(LandCase):
    """父對子做一次 exec；子還沒閒著父就停在原地，不算失敗。子閒著且有結果才算成功。"""

    def setUp(self):
        super().setUp()
        self.child = layout.Land(os.path.join(self.land.root, "child"))
        layout.init(self.child.root)
        # 子地兩步：先跑一件跟結果無關的事，再寫結果，讓子地第一次 exec 之後還沒閒著
        write_source(self.child, [
            {"name": "c1", "kind": "inst", "inst": {"argv": [PY, "-c", "pass"]}, "then": "c2"},
            {"name": "c2", "kind": "inst",
             "inst": {"argv": [PY, "-c",
                                "import os; open(os.environ['AOS_RESULT'],'w').write('done')"]},
             "then": "end"},
        ])
        self.result_rel = "call_result.txt"
        write_source(self.land, [
            {"name": "p1", "kind": "call", "child": "child", "mode": "sync",
             "result": self.result_rel, "then": "end"},
        ])

    def test_hold_then_success(self):
        execute.exec_once(self.land)  # tick0：父開呼叫、子跑 c1，子還沒閒
        sr = S.load(self.land)["series"][0]
        self.assertEqual(sr["status"], S.RUNNING,
                          msg="子還在跑（未閒著）時，父那步該停在原地、不算失敗，實際 %r" % sr)
        self.assertEqual(sr["cursor"], "p1", msg="子沒閒著，父的游標不該動，實際 %r" % sr["cursor"])

        execute.exec_once(self.land)  # tick1：父再對子做一次 exec，子跑 c2、寫結果、閒下來
        sr = S.load(self.land)["series"][0]
        self.assertEqual(sr["status"], S.DONE,
                          msg="子閒著且結果落點有檔，父那步該成功、串該做完，實際 %r" % sr)

    def test_call_record_fields(self):
        execute.exec_once(self.land)
        calls_dir = self.land.calls_dir
        files = os.listdir(calls_dir)
        self.assertTrue(files, msg=".aos/calls/ 應該有一筆呼叫記錄")
        rec = fsutil.read_json(os.path.join(calls_dir, files[0]))
        for key in ("id", "tick", "series", "step", "child", "mode", "result", "args", "opened_at"):
            self.assertIn(key, rec, msg="呼叫記錄少了欄位 `%s`，實際 %r" % (key, rec))
        self.assertEqual(rec["mode"], "sync")
        self.assertEqual(rec["step"], "p1")
        self.assertEqual(rec["child"], self.child.root)


class TestChildEnvVars(LandCase):
    """子指令的環境變數：AOS_RESULT、AOS_CALLER、AOS_ARG_*。"""

    def test_env_vars_reach_child(self):
        child = layout.Land(os.path.join(self.land.root, "child"))
        layout.init(child.root)
        dump_path = os.path.join(self.land.root, "dump.json")
        write_source(child, [
            {"name": "c1", "kind": "inst",
             "inst": {"argv": [PY, "-c",
                                "import os, json, sys; "
                                "json.dump({'result': os.environ.get('AOS_RESULT'), "
                                "'caller': os.environ.get('AOS_CALLER'), "
                                "'arg_foo': os.environ.get('AOS_ARG_FOO')}, open(sys.argv[1], 'w')); "
                                "open(os.environ['AOS_RESULT'], 'w').write('ok')",
                                dump_path]},
             "then": "end"},
        ])
        write_source(self.land, [
            {"name": "p1", "kind": "call", "child": "child", "mode": "sync",
             "result": "result.txt", "args": {"foo": "bar"}, "then": "end"},
        ])
        execute.exec_once(self.land)
        sr = S.load(self.land)["series"][0]
        self.assertEqual(sr["status"], S.DONE, msg="單步子地一次 exec 就該閒著、父該成功，實際 %r" % sr)
        with open(dump_path, "r", encoding="utf-8") as f:
            dumped = json.load(f)
        self.assertEqual(dumped["result"], self.land.resolve("result.txt"),
                          msg="子指令的 AOS_RESULT 應該是父指定的結果落點，實際 %r" % dumped)
        self.assertEqual(dumped["caller"], self.land.root,
                          msg="子指令的 AOS_CALLER 應該是父地路徑，實際 %r" % dumped)
        self.assertEqual(dumped["arg_foo"], "bar",
                          msg="args.foo 應該變成 AOS_ARG_FOO 環境變數，實際 %r" % dumped)


class TestAwaitThreeStates(LandCase):
    def test_result_absent_holds_not_failed(self):
        write_source(self.land, [
            {"name": "w1", "kind": "await", "result": "watched.txt", "then": "end"},
        ])
        execute.exec_once(self.land)
        sr = S.load(self.land)["series"][0]
        self.assertEqual(sr["status"], S.RUNNING,
                          msg="結果檔還不在，這格不該動、更不算失敗，實際 %r" % sr)
        self.assertEqual(sr["cursor"], "w1", msg="還在等，游標不該動，實際 %r" % sr["cursor"])

    def test_result_present_succeeds(self):
        result_path = self.land.resolve("watched.txt")
        write_source(self.land, [
            {"name": "w1", "kind": "await", "result": "watched.txt", "then": "end"},
        ])
        fsutil.atomic_write_text(result_path, "here it is")
        execute.exec_once(self.land)
        sr = S.load(self.land)["series"][0]
        self.assertEqual(sr["status"], S.DONE,
                          msg="結果檔已經在了，這步該成功、串該做完，實際 %r" % sr)

    def test_status_file_present_fails(self):
        result_path = self.land.resolve("watched.txt")
        status.write_failed(result_path, "backend_error", "假裝子地說壞了")
        write_source(self.land, [
            {"name": "w1", "kind": "await", "result": "watched.txt", "then": "end"},
        ])
        execute.exec_once(self.land)
        sr = S.load(self.land)["series"][0]
        self.assertEqual(sr["status"], S.FAILED,
                          msg="<result>.status.json 在，await 該判失敗，實際 %r" % sr)
        self.assertEqual(sr["fail_reason"]["reason"], "backend_error",
                          msg="失敗原因該延用狀態檔的 reason，實際 %r" % sr["fail_reason"])


class TestAwaitMaxTicks(LandCase):
    def test_max_ticks_exceeded_fails_with_await_timeout(self):
        write_source(self.land, [
            {"name": "w1", "kind": "await", "result": "never.txt", "max_ticks": 1, "then": "end"},
        ])
        execute.exec_once(self.land)  # 第 1 次等：還沒超過
        sr = S.load(self.land)["series"][0]
        self.assertEqual(sr["status"], S.RUNNING,
                          msg="第一次還沒超過 max_ticks，不該失敗，實際 %r" % sr)

        execute.exec_once(self.land)  # 第 2 次等：超過了
        sr = S.load(self.land)["series"][0]
        self.assertEqual(sr["status"], S.FAILED,
                          msg="超過 max_ticks 該讓串失敗，實際 %r" % sr)
        self.assertEqual(sr["fail_reason"]["reason"], "await_timeout",
                          msg="超過 max_ticks 的失敗原因應該是 await_timeout，實際 %r" % sr["fail_reason"])
        result_path = self.land.resolve("never.txt")
        st = status.read_status(result_path)
        self.assertIsNotNone(st, msg="await_timeout 應該寫 <result>.status.json，卻沒有")
        self.assertEqual(st.get("reason"), "await_timeout",
                          msg="狀態檔的 reason 也該是 await_timeout，實際 %r" % st)
