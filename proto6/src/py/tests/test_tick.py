"""aos-tick 第一段驗收（plan m1-tick-core.md 步驟 1～9）。真的開 bin/aos-tick 子程序。"""
import json
import os
import subprocess
import sys
import time
import unittest

from _util import Base, PY

HERE = os.path.dirname(os.path.abspath(__file__))
TICK = os.path.join(os.path.dirname(HERE), "bin", "aos-tick")
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lib"))
import aos_tick  # noqa: E402

CLEAN_ENV = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}


def table(*tasks):
    return {"_metainfo": {"_type": "aos-tasks", "_version": 1}, "tasks": list(tasks)}


def sh(tid, script, **extra):
    return dict({"id": tid, "argv": ["sh", "-c", script]}, **extra)


class TickCase(Base):

    def setUp(self):
        super().setUp()
        os.makedirs(os.path.join(self.d, ".aos"))

    def tasks(self, *items):
        self.write(".aos/tasks.json", json.dumps(table(*items), ensure_ascii=False))

    def tick(self, *args, env=None):
        e = dict(CLEAN_ENV, **(env or {}))
        args = args or ("--node", self.d)
        return subprocess.run([PY, TICK] + list(args), capture_output=True, text=True, env=e, timeout=30)

    def start(self, *args):
        args = args or ("--node", self.d)
        return subprocess.Popen([PY, TICK] + list(args), env=CLEAN_ENV,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def wait_for(self, rel):
        for _ in range(400):
            if self.exists(rel):
                return
            time.sleep(0.01)
        self.fail("等不到 " + rel)

    def rec(self, name="current"):
        return json.loads(self.read(".aos/tick/%s.json" % name))

    HOLD = "touch started; while [ ! -e release ]; do sleep 0.02; done"


class Step1Lock(TickCase):

    def test_two_at_once_and_inst_path_same_lock(self):
        self.tasks(sh("hold", self.HOLD))
        p = self.start()
        self.wait_for("started")
        before = self.read(".aos/tick/current.json")
        for node in (self.d, os.path.join(self.d, ".aos", "inst.json"), os.path.join(self.d, "inst.json")):
            r = self.tick("--node", node)
            self.assertEqual(r.returncode, 75, r.stderr)
        self.assertEqual(self.read(".aos/tick/current.json"), before)
        self.write("release", "")
        self.assertEqual(p.wait(timeout=10), 0)

    def test_no_aos_dir_is_error_not_created(self):
        os.rmdir(os.path.join(self.d, ".aos"))
        r = self.tick()
        self.assertEqual(r.returncode, 2)
        self.assertIn("config_invalid", r.stderr)
        self.assertEqual(os.listdir(self.d), [])

    def test_no_aos_dir_runs_inst_json_like_aos_exec(self):
        os.rmdir(os.path.join(self.d, ".aos"))
        self.write("inst.json", json.dumps({"argv": ["sh", "-c", "echo ran > out; exit 3"]}))
        r = self.tick()
        self.assertEqual(r.returncode, 3)
        self.assertEqual(self.read("out"), "ran\n")
        self.assertFalse(self.exists(".aos"))

    def test_usage_errors(self):
        self.assertEqual(self.tick("--node", "relative/path").returncode, 2)
        self.assertEqual(self.tick("--bogus").returncode, 2)

    def test_cwd_default_and_not_git(self):
        self.tasks({"id": "t", "argv": ["true"]})
        r = subprocess.run([PY, TICK], cwd=self.d, env=CLEAN_ENV, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(self.exists(".git"))

    def test_leftover_descendant_blocks_next(self):
        self.tasks(sh("bg", "sleep 30 & echo $! > bg.pid"))
        self.assertEqual(self.tick().returncode, 0)
        pid = int(self.read("bg.pid"))
        try:
            self.assertEqual(self.tick().returncode, 75)
        finally:
            os.kill(pid, 9)
        for _ in range(200):
            if self.tick().returncode != 75:
                break
            time.sleep(0.02)
        self.assertEqual(self.rec()["exit"], 0)


class Step2Blocked(TickCase):

    def test_blocked(self):
        self.tasks(sh("t", "echo ran >> ran.txt"))
        self.assertEqual(self.tick().returncode, 0)
        cur, last_exists = self.read(".aos/tick/current.json"), self.exists(".aos/tick/last.json")
        self.write(".aos/tick-blocked", "壞了\n")
        r = self.tick()
        self.assertEqual(r.returncode, 1)
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

    def check_bad(self, body):
        self.write(".aos/tasks.json", body if isinstance(body, str) else json.dumps(body))
        self.write("x", "")
        r = self.tick()
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("config_invalid", r.stderr)
        rec = self.rec()
        self.assertEqual((rec["ended"], rec["exit"], rec["tasks"]), (True, 2, []))
        check_record(self, rec)

    def test_bad_tables(self):
        t = {"id": "a", "argv": ["sh", "-c", "touch ran"]}
        for body in ("{not json", table(t, dict(t)), {"_metainfo": {"_type": "x", "_version": 1}, "tasks": []},
                     table({"id": "a", "argv": []}), table({"argv": ["true"]}),
                     table({"id": "a", "argv": ["true"], "user": -1})):
            with self.subTest(body=body):
                self.check_bad(body)
                self.assertFalse(self.exists("ran"))

    def test_missing_tasks_json(self):
        r = self.tick()
        self.assertEqual(r.returncode, 2)
        self.assertEqual(self.rec()["exit"], 2)

    def test_unknown_keys_and_system_x_run(self):
        self.tasks({"id": "a", "argv": ["true"], "group": "g", "needs": ["x"], "kind": "system.x"},
                   {"id": "b", "argv": ["true"]})
        self.assertEqual(self.tick().returncode, 0)

    def test_whole_ref_item(self):
        self.write("task.json", json.dumps({"id": "from-ref", "argv": ["sh", "-c", "echo $AOS_TASK_ID > id.txt"]}))
        self.tasks({"$ref": "task.json"})
        self.assertEqual(self.tick().returncode, 0)
        self.assertEqual(self.read("id.txt"), "from-ref\n")

    def test_spec_examples_only_four_checks(self):
        ex = os.path.join(HERE, "..", "..", "..", "spec", "protocol", "examples", "node")
        self.write("task.json", json.dumps({"id": "ref", "argv": ["true"]}))
        for name in sorted(os.listdir(ex)):
            if not name.startswith("tasks."):
                continue
            with self.subTest(name=name):
                with open(os.path.join(ex, name), encoding="utf-8") as f:
                    self.write(".aos/tasks.json", f.read())
                r = self.tick(env={"PROGRAM": "printf", "PATH": os.environ["PATH"]})
                self.assertIn(r.returncode, (0, 1), r.stderr)      # 範例表核心都不擋（不回 2）


class Step5Run(TickCase):

    LOCKCHECK = ("import fcntl,os,sys\n"
                 "fd=int(os.environ['AOS_TICK_LOCK_FD'])\n"
                 "a=os.fstat(fd); b=os.stat('.aos/tick.lock')\n"
                 "assert (a.st_dev,a.st_ino)==(b.st_dev,b.st_ino)\n"
                 "fcntl.flock(fd, fcntl.LOCK_EX|fcntl.LOCK_NB)\n"
                 "g=os.open('.aos/tick.lock', os.O_RDONLY)\n"
                 "try:\n fcntl.flock(g, fcntl.LOCK_EX|fcntl.LOCK_NB); sys.exit(9)\n"
                 "except BlockingIOError: pass\n")

    def test_env_record_signal_user(self):
        self.tasks(sh("a", "env > out.env"),
                   sh("b", 'cat "$AOS_TICK_RECORD" > rec.json'),
                   sh("c", "kill -9 $$"),
                   {"id": "d", "argv": ["true"], "user": "root" if os.geteuid() else "nobody"},
                   {"id": "e", "argv": [PY, "-c", self.LOCKCHECK]},
                   {"id": "f", "argv": ["sh", "-c", "exit 3"]},
                   sh("g", "touch g.ran"))
        r = self.tick()
        self.assertEqual(r.returncode, 1, r.stderr)
        env = dict(l.split("=", 1) for l in self.read("out.env").splitlines() if "=" in l)
        self.assertEqual(env["AOS_TASK_INDEX"], "0")
        self.assertEqual(env["AOS_TASK_ID"], "a")
        self.assertEqual(env["AOS_NODE_DIR"], self.d)
        self.assertEqual(env["AOS_TICK_RECORD"], os.path.join(self.d, ".aos/tick/current.json"))
        self.assertIn("AOS_TICK_LOCK_FD", env)
        self.assertEqual(json.loads(self.read("rec.json"))["tasks"], [{"id": "a", "exit": 0}])
        self.assertIn("user_mismatch: d", r.stderr)
        self.assertEqual(self.rec()["tasks"], [{"id": "a", "exit": 0}, {"id": "b", "exit": 0},
                                               {"id": "c", "signal": 9}, {"id": "d", "exit": 125},
                                               {"id": "e", "exit": 0}, {"id": "f", "exit": 3},
                                               {"id": "g", "exit": 0}])
        check_record(self, self.rec())

    def test_envs_clear_keeps_lock_fd(self):
        self.tasks({"id": "a", "argv": ["/bin/sh", "-c", "env > out.env"], "envs": {"$opt": "clear", "$val": {}}})
        self.assertEqual(self.tick().returncode, 0)
        self.assertIn("AOS_TICK_LOCK_FD=", self.read("out.env"))

    def test_other_tick_75_while_task_runs(self):
        self.tasks(sh("hold", self.HOLD))
        p = self.start()
        self.wait_for("started")
        self.assertEqual(self.tick().returncode, 75)
        self.write("release", "")
        self.assertEqual(p.wait(timeout=10), 0)


class Step6Stop(TickCase):

    def test_stop_file(self):
        self.tasks(sh("a", "true"), sh("b", "echo 手動停 > .aos/tick/stop"), sh("c", "touch c.ran"))
        r = self.tick()
        self.assertEqual(r.returncode, 1)
        self.assertIn("stopped: 手動停", r.stderr)
        self.assertFalse(self.exists("c.ran"))
        rec = self.rec()
        self.assertEqual((rec["stopped_after"], rec["exit"], len(rec["tasks"])), ("b", 1, 2))
        check_record(self, rec)
        self.tasks(sh("a", "true"), sh("b", "true"), sh("c", "touch c.ran"))
        self.assertEqual(self.tick().returncode, 0)
        self.assertTrue(self.exists("c.ran"))
        self.assertFalse(self.exists(".aos/tick/stop"))


class Step7Unwritable(TickCase):

    @unittest.skipIf(os.geteuid() == 0, "root 不受 chmod 限制")
    def test_readonly_tick_dir(self):
        self.tasks({"id": "t", "argv": ["true"]})
        self.assertEqual(self.tick().returncode, 0)
        self.tasks(sh("a", 'echo "${AOS_TICK_RECORD-unset}" > rec.txt'))
        d = os.path.join(self.d, ".aos/tick")
        os.chmod(d, 0o555)
        try:
            r = self.tick()
        finally:
            os.chmod(d, 0o755)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stderr.count("record_unwritable"), 1)
        self.assertEqual(self.read("rec.txt"), "unset\n")

    def test_fail_midway(self):
        self.tasks(sh("a", "true"), sh("b", "true"), sh("c", 'echo "${AOS_TICK_RECORD-unset}" > rec.txt'))
        r = self.tick(env={"AOS_TICK_TEST_FAIL_WRITE": "3"})       # 1＝開格、2＝a 之後、3＝b 之後
        self.assertIn("record_unwritable", r.stderr)
        self.assertEqual(self.read("rec.txt"), "unset\n")
        self.tasks()
        self.tick()
        last = self.rec("last")
        self.assertFalse(last["ended"])
        self.assertEqual(last["tasks"], [{"id": "a", "exit": 0}])   # 留最後一次寫成功的那份

    def test_fail_at_open(self):
        self.tasks({"id": "t", "argv": ["true"]})
        self.tick()
        self.tick()
        r = self.tick(env={"AOS_TICK_TEST_FAIL_WRITE": "1"})
        self.assertIn("record_unwritable", r.stderr)
        self.assertFalse(self.exists(".aos/tick/current.json"))
        self.tick()
        self.assertFalse(self.exists(".aos/tick/last.json"))
        self.assertEqual(self.rec()["seq"], 3)

    def test_both_unreadable(self):
        self.tasks({"id": "t", "argv": ["true"]})
        self.write(".aos/tick/current.json", "壞")
        self.write(".aos/tick/last.json", "{")
        r = self.tick()
        self.assertEqual(r.returncode, 0)
        self.assertIn("record_unreadable", r.stderr)
        self.assertEqual(self.read(".aos/tick/current.json"), "壞")

    def test_fsync_flag_runs(self):
        self.tasks({"id": "t", "argv": ["true"]})
        self.assertEqual(self.tick("--node", self.d, "--firstdo-fsync").returncode, 0)
        self.assertEqual(self.tick(env={"AOS_TICK_FIRSTDO_FSYNC": "1"}).returncode, 0)


class Step8Parent(Base):

    def test_default_parent(self):
        for rel in ("a/.aos/inst.json", "a/b/.aos/inst.json"):
            self.write(rel, "{}")
        os.makedirs(os.path.join(self.d, "a/x/c"))
        a = os.path.join(self.d, "a")
        self.assertEqual(aos_tick.default_parent(os.path.join(a, "b")), a)
        self.assertEqual(aos_tick.default_parent(os.path.join(a, "x/c")), a)
        self.assertIsNone(aos_tick.default_parent(a))


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
        case.assertIn(rec["exit"], (0, 1, 2))
        if "stopped_after" in rec:
            case.assertEqual(rec["exit"], 1)
            case.assertEqual(rec["tasks"][-1]["id"], rec["stopped_after"])
        if rec["exit"] == 0:
            case.assertTrue(all(t.get("exit") == 0 for t in rec["tasks"]))
        if rec["exit"] == 2:
            case.assertEqual(rec["tasks"], [])
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
