"""aosp/execute.py 的 call(sync) / await：三態、呼叫記錄、子指令的環境變數。"""
import json
import os
import sys

PROTO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROTO not in sys.path:
    sys.path.insert(0, PROTO)

from aosp import execute, fsutil, layout, registry, series as S, status  # noqa: E402
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


class TestAsyncCallNeedsDaemon(LandCase):
    """裁決 P-01：沒 daemon 時脫節呼叫直接失敗，狀態檔寫 no_daemon（不再自己 detach 起 run）。"""

    def setUp(self):
        super().setUp()
        self.child = layout.Land(os.path.join(self.land.root, "child"))
        layout.init(self.child.root)
        write_source(self.child, [
            {"name": "c1", "kind": "inst",
             "inst": {"argv": [PY, "-c",
                                "import os; open(os.environ['AOS_RESULT'],'w').write('done')"]},
             "then": "end"},
        ])

    def _write_parent(self, on_fail=None):
        step = {"name": "p1", "kind": "call", "child": "child", "mode": "async",
                "clock": {"kind": "until", "until": "idle"},
                "result": "out/child.txt", "args": {"foo": "bar"}, "then": "end"}
        if on_fail:
            step["on_fail"] = on_fail
            write_source(self.land, [step,
                                     {"name": "rescue", "kind": "inst",
                                      "inst": {"argv": [PY, "-c", "pass"]}, "then": "end"}])
        else:
            write_source(self.land, [step])

    def test_no_daemon_fails_with_no_daemon_status_file(self):
        self._write_parent()
        execute.exec_once(self.land)
        sr = S.load(self.land)["series"][0]
        self.assertEqual(sr["status"], S.FAILED,
                          msg="P-01：daemon 不在時 async 呼叫該當場失敗，實際 %r" % sr)
        self.assertEqual(sr["fail_reason"]["reason"], status.NO_DAEMON,
                          msg="失敗原因該是 no_daemon，實際 %r" % sr["fail_reason"])
        st = status.read_status(self.land.resolve("out/child.txt"))
        self.assertIsNotNone(st, msg="該在結果落點旁寫 <result>.status.json，卻沒有")
        self.assertEqual(st.get("state"), "failed",
                          msg="狀態檔的 state 該是 failed，實際 %r" % st)
        self.assertEqual(st.get("reason"), status.NO_DAEMON,
                          msg="狀態檔的 reason 該是 no_daemon，實際 %r" % st)
        self.assertIn("daemon start", st.get("message", ""),
                      msg="錯誤要指路：訊息裡該講「先 aos daemon start」，實際 %r" % st)

    def test_no_daemon_does_not_register_or_spawn_child(self):
        self._write_parent()
        execute.exec_once(self.land)
        reg = registry.load(layout.Home())
        self.assertIsNone(registry.find(reg, self.child.root),
                          msg="呼叫都失敗了，登記表不該留一筆沒人會去起的 pending，實際 %r" % reg)
        self.assertFalse(os.path.exists(self.child.resolve(".aos/detached.log")),
                         msg="P-01 之後不該再有自己 detach 出去的 run")
        self.assertFalse(os.path.exists(self.land.resolve("out/child.txt")),
                         msg="沒人跑子地，結果落點不該有東西")

    def test_no_daemon_follows_on_fail(self):
        self._write_parent(on_fail="rescue")
        execute.exec_once(self.land)
        sr = S.load(self.land)["series"][0]
        self.assertEqual(sr["status"], S.RUNNING,
                          msg="有 on_fail 就該照它走、不該把串判死，實際 %r" % sr)
        self.assertEqual(sr["cursor"], "rescue",
                          msg="該跳到 on_fail 指的 `rescue`，實際 %r" % sr["cursor"])

    def test_with_daemon_registers_child_and_succeeds(self):
        self._write_parent()
        home = layout.Home()
        registry.set_daemon_pid(os.getpid(), home)   # 假裝 daemon 在跑
        execute.exec_once(self.land)
        sr = S.load(self.land)["series"][0]
        self.assertEqual(sr["status"], S.DONE,
                          msg="daemon 在時 async 呼叫登記完就該成功，實際 %r" % sr)
        e = registry.find(registry.load(home), self.child.root)
        self.assertIsNotNone(e, msg="子地該登進登記表，實際登記表 %r" % registry.load(home))
        self.assertEqual(e["state"], registry.PENDING,
                          msg="登記完是 pending，等 daemon 去起，實際 %r" % e)
        self.assertEqual(e["result"], self.land.resolve("out/child.txt"),
                          msg="登記表要記結果落點（子地靠它拿 AOS_RESULT），實際 %r" % e)
        self.assertEqual(e["parent"], self.land.root,
                          msg="登記表要記父是誰，實際 %r" % e)
        self.assertEqual(e.get("args"), {"foo": "bar"},
                          msg="呼叫的 args 要記進登記表，子地才拿得到 AOS_ARG_*，實際 %r" % e)

    def test_run_rebuilds_child_env_from_registry(self):
        """daemon 起的那支 run 拿不到父 exec 的環境，只能從登記表重建。"""
        from aosp import run as runmod
        home = layout.Home()
        fsutil.ensure_dir(self.land.resolve("out"))   # 落點目錄由父先開好（同 _do_call）
        registry.register(self.child.root, {"kind": "until", "until": "idle"},
                          parent=self.land.root,
                          result=self.land.resolve("out/child.txt"),
                          args={"foo": "bar"}, home=home)
        env = runmod._call_env(self.child, home)
        self.assertEqual(env.get("AOS_RESULT"), self.land.resolve("out/child.txt"),
                          msg="AOS_RESULT 該從登記表的 result 重建，實際 %r" % env)
        self.assertEqual(env.get("AOS_CALLER"), self.land.root,
                          msg="AOS_CALLER 該從登記表的 parent 重建，實際 %r" % env)
        self.assertEqual(env.get("AOS_ARG_FOO"), "bar",
                          msg="AOS_ARG_* 該從登記表的 args 重建，實際 %r" % env)
        out = runmod.run(self.child, until="idle", home=home)
        self.assertEqual(out["reason"], runmod.IDLE,
                          msg="子地該跑到閒著，實際 %r" % out)
        self.assertTrue(os.path.exists(self.land.resolve("out/child.txt")),
                        msg="子地拿到 AOS_RESULT 就該把結果寫到父指定的落點")
