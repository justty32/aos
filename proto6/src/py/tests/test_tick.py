"""aos-tick 第一段驗收（plan m1-tick-core.md）。真的開 bin/aos-tick 子程序。

〔使用者方向 2026-10-01〕POC 默認一切正常：互斥鎖、驗表、`user`、上下層、fsync、異常處理的測試都拿掉了。
結束碼照 aos 體系慣例（0 正常結束、1 錯誤結束、2 正常中斷；notes/verdicts/11 篇末 2026-10-01）：
aos-tick 的碼只講 tick 自己，任務怎麼結束只記進紀錄、不影響它。
"""
import json
import os
import subprocess
import unittest

from _util import Base, PY

HERE = os.path.dirname(os.path.abspath(__file__))
TICK = os.path.join(os.path.dirname(HERE), "bin", "aos-tick")

CLEAN_ENV = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}


def table(*tasks):
    return {"_metainfo": {"_type": "aos-tasks", "_version": 1}, "tasks": list(tasks)}


def sh(tid, script, **extra):
    return dict({"id": tid, "argv": ["sh", "-c", script]}, **extra)


class TickCase(Base):

    def setUp(self):
        super().setUp()
        os.makedirs(os.path.join(self.d, ".aos"))
        self.write(".aos/inst.json", json.dumps({"argv": ["aos-tick", "--node", self.d]}))

    def tasks(self, *items):
        self.write(".aos/tasks.json", json.dumps(table(*items), ensure_ascii=False))

    def tick(self, *args, env=None):
        e = dict(CLEAN_ENV, **(env or {}))
        args = args or ("--node", self.d)
        return subprocess.run([PY, TICK] + list(args), capture_output=True, text=True, env=e, timeout=30)

    def rec(self, name="current"):
        return json.loads(self.read(".aos/tick/%s.json" % name))


class Step1Node(TickCase):

    def test_inst_paths_normalize_to_node(self):
        self.tasks({"id": "t", "argv": ["true"]})
        for i, node in enumerate((self.d, os.path.join(self.d, ".aos", "inst.json"),
                                  os.path.join(self.d, "inst.json")), 1):
            r = self.tick("--node", node)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(self.rec()["seq"], i)

    def test_no_aos_inst_json_is_error(self):
        # 2026-10-01：拿掉「交給 aos-exec 跑 inst.json」的退路；沒有 .aos/inst.json 就回 1
        self.tasks(sh("t", "touch ran"))
        os.unlink(os.path.join(self.d, ".aos", "inst.json"))
        self.write("inst.json", json.dumps({"argv": ["sh", "-c", "touch ran"]}))
        r = self.tick()
        self.assertEqual(r.returncode, 1)
        self.assertIn("no_inst:", r.stderr)
        self.assertFalse(self.exists("ran"))
        self.assertFalse(self.exists(".aos/tick"))
        os.unlink(os.path.join(self.d, "inst.json"))
        os.unlink(os.path.join(self.d, ".aos", "tasks.json"))
        os.rmdir(os.path.join(self.d, ".aos"))
        self.assertEqual(self.tick().returncode, 1)
        self.assertEqual(os.listdir(self.d), [])

    def test_usage_errors(self):
        # aos 結束碼慣例：argv 用法錯算 1
        self.assertEqual(self.tick("--node", "relative/path").returncode, 1)
        self.assertEqual(self.tick("--node", os.path.join(self.d, "nope")).returncode, 1)
        self.assertEqual(self.tick("--bogus").returncode, 1)
        self.assertEqual(self.tick("--node").returncode, 1)

    def test_cwd_default_and_not_git(self):
        self.tasks({"id": "t", "argv": ["true"]})
        r = subprocess.run([PY, TICK], cwd=self.d, env=CLEAN_ENV, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(self.exists(".git"))

class Step2Blocked(TickCase):

    def test_blocked(self):
        self.tasks(sh("t", "echo ran >> ran.txt"))
        self.assertEqual(self.tick().returncode, 0)
        cur, last_exists = self.read(".aos/tick/current.json"), self.exists(".aos/tick/last.json")
        self.write(".aos/tick-blocked", "壞了\n")
        r = self.tick()
        self.assertEqual(r.returncode, 2)                 # 正常中斷
        self.assertIn("blocked: 壞了", r.stderr)
        self.assertEqual(self.read("ran.txt"), "ran\n")
        self.assertEqual(self.read(".aos/tick/current.json"), cur)
        self.assertEqual(self.exists(".aos/tick/last.json"), last_exists)
        os.unlink(os.path.join(self.d, ".aos/tick-blocked"))
        self.assertEqual(self.tick().returncode, 0)
        self.assertEqual(self.rec()["seq"], 2)


class Step3Seq(TickCase):

    def test_ten_ticks_and_shell(self):
        self.tasks({"id": "t", "argv": ["true"]})
        for i in range(1, 11):
            if i == 5:
                r = subprocess.run(["sh", "-c", 'cd "$1" && "$2" "$3"', "x", self.d, PY, TICK],
                                   env=CLEAN_ENV, capture_output=True, text=True)
            else:
                r = self.tick()
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(self.rec()["seq"], i)
            if i > 1:
                self.assertEqual(self.rec("last")["seq"], i - 1)
            check_record(self, self.rec())

    def test_first_run_no_last(self):
        self.tasks()
        self.assertEqual(self.tick().returncode, 0)
        self.assertEqual(self.rec(), dict(self.rec(), seq=1, tasks=[], ended=True, exit=0))
        self.assertFalse(self.exists(".aos/tick/last.json"))


class Step4Table(TickCase):

    def test_unknown_keys_and_whole_ref_run(self):
        self.write("task.json", json.dumps({"id": "from-ref", "argv": ["sh", "-c", "echo $AOS_TASK_ID > id.txt"]}))
        self.tasks({"id": "a", "argv": ["true"], "group": "g", "needs": ["x"], "kind": "system.x"},
                   {"$ref": "task.json"})
        self.assertEqual(self.tick().returncode, 0)
        self.assertEqual(self.read("id.txt"), "from-ref\n")


class Step5Run(TickCase):

    def test_env_record_signal_user_ignored(self):
        self.tasks(sh("a", "env > out.env"),
                   sh("b", 'cat "$AOS_TICK_RECORD" > rec.json'),
                   sh("c", "kill -9 $$"),
                   {"id": "d", "argv": ["true"], "user": "root" if os.geteuid() else "nobody"},
                   {"id": "f", "argv": ["sh", "-c", "exit 3"]},
                   sh("g", "touch g.ran"))
        r = self.tick()
        self.assertEqual(r.returncode, 0, r.stderr)       # 任務失敗不影響 tick 的碼
        env = dict(l.split("=", 1) for l in self.read("out.env").splitlines() if "=" in l)
        self.assertEqual(env["AOS_TASK_INDEX"], "0")
        self.assertEqual(env["AOS_TASK_ID"], "a")
        self.assertEqual(env["AOS_NODE_DIR"], self.d)
        self.assertEqual(env["AOS_TICK_RECORD"], os.path.join(self.d, ".aos/tick/current.json"))
        self.assertNotIn("AOS_TICK_LOCK_FD", env)
        self.assertEqual(json.loads(self.read("rec.json"))["tasks"], [{"id": "a", "exit": 0}])
        self.assertNotIn("user_mismatch", r.stderr)          # user 不看，照 tick 自己的帳號跑
        self.assertEqual(self.rec()["tasks"], [{"id": "a", "exit": 0}, {"id": "b", "exit": 0},
                                               {"id": "c", "signal": 9}, {"id": "d", "exit": 0},
                                               {"id": "f", "exit": 3},
                                               {"id": "g", "exit": 0}])
        check_record(self, self.rec())

class Step6Stop(TickCase):

    def test_stop_file(self):
        # 使用者 2026-10-01：停格檔不算中斷，回 0（暫定）
        self.tasks(sh("a", "true"), sh("b", "echo 手動停 > .aos/tick/stop"), sh("c", "touch c.ran"))
        r = self.tick()
        self.assertEqual(r.returncode, 0)
        self.assertIn("stopped: 手動停", r.stderr)
        self.assertFalse(self.exists("c.ran"))
        rec = self.rec()
        self.assertEqual((rec["stopped_after"], rec["exit"], len(rec["tasks"])), ("b", 0, 2))
        check_record(self, rec)
        self.tasks(sh("a", "true"), sh("b", "true"), sh("c", "touch c.ran"))
        self.assertEqual(self.tick().returncode, 0)
        self.assertTrue(self.exists("c.ran"))
        self.assertFalse(self.exists(".aos/tick/stop"))

    def test_stop_file_after_error(self):
        self.tasks(sh("a", "exit 1"), sh("b", "echo 停 > .aos/tick/stop"), sh("c", "touch c.ran"))
        r = self.tick()
        self.assertEqual(r.returncode, 0)
        self.assertFalse(self.exists("c.ran"))
        rec = self.rec()
        self.assertEqual((rec["stopped_after"], rec["exit"]), ("b", 0))
        check_record(self, rec)


class ExitCodes(TickCase):
    """aos 結束碼慣例下的 tick 結束碼（使用者 2026-10-01）：任務的碼只記、不影響 tick。"""

    def test_task_codes_only_recorded(self):
        self.tasks(sh("a", "exit 1"), sh("b", "exit 2"), sh("c", "exit 127"),
                   sh("d", "kill -2 $$"), sh("e", "touch e.ran"))
        r = self.tick()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertTrue(self.exists("e.ran"))             # 回 2、回錯都照常跑下一項
        rec = self.rec()
        self.assertEqual(rec["tasks"], [{"id": "a", "exit": 1}, {"id": "b", "exit": 2},
                                        {"id": "c", "exit": 127}, {"id": "d", "signal": 2},
                                        {"id": "e", "exit": 0}])     # 照實記原碼
        self.assertEqual(rec["exit"], 0)
        check_record(self, rec)

    def test_bad_current_json_is_error(self):
        self.tasks(sh("t", "touch ran"))
        self.write(".aos/tick/current.json", "{壞")
        r = self.tick()
        self.assertEqual(r.returncode, 1)
        self.assertIn("Error", r.stderr)                  # 沒接住的例外：traceback 進 stderr
        self.assertFalse(self.exists("ran"))

    def test_bad_tasks_json_is_error(self):
        self.write(".aos/tasks.json", "{壞")
        r = self.tick()
        self.assertEqual(r.returncode, 1)
        self.assertIn("Error", r.stderr)


class Step9Whole(TickCase):

    def test_b626_only_true_no_daemon(self):
        self.tasks({"id": "t", "argv": ["true"]})
        r = self.tick()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertNotIn("standard:", r.stderr)
        check_record(self, self.rec())


def check_record(case, rec):
    """P-213 的跨欄位規則＋（有 jsonschema 時）node-tick-record schema。"""
    if rec.get("ended"):
        case.assertEqual(rec["exit"], 0)                  # 寫得到收尾就是 0，任務成敗不影響
        if "stopped_after" in rec:
            case.assertEqual(rec["tasks"][-1]["id"], rec["stopped_after"])
    else:
        case.assertNotIn("exit", rec)
    try:
        from jsonschema import Draft202012Validator
        from referencing import Registry, Resource
    except ImportError:
        return
    sd = os.path.join(HERE, "..", "..", "..", "spec", "protocol", "schemas")
    res = {}
    for n in ("common.schema.json", "node-tick-record.schema.json"):
        with open(os.path.join(sd, n), encoding="utf-8") as f:
            res[n] = Resource.from_contents(json.load(f))
    reg = Registry().with_resources(res.items())
    Draft202012Validator(res["node-tick-record.schema.json"].contents, registry=reg).validate(rec)


if __name__ == "__main__":
    unittest.main()
