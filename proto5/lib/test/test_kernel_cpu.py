"""kernel 的 cpu add／rm／ls（kernel-cli.md）：只改 info、鎖、指示詞保留、按池摘要。用假 daemon，不拉真行程。"""
import contextlib
import fcntl
import io
import json
import os
import threading
import unittest
from unittest.mock import patch

import aos_home
import aos_kernel as kernel
import aos_kernel_cpu
import aos_kernel_rows
from _kernel_fake import FakeCase


class CpuCase(FakeCase):
    def main(self, *args, code=0):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            result = kernel.main([*map(str, args[:2]), "--target", str(self.K), *map(str, args[2:])])
        self.assertEqual(result, code, out.getvalue() + err.getvalue())
        return out.getvalue(), err.getvalue()

    def pools(self):
        return self.info()["pools"]

    def booted(self, pools=None, **settings):
        self.init(pools, **settings)
        self.boot()
        self.settle()


class CpuAddRm(CpuCase):
    def test_add_new_pool_writes_only_that_cell(self):
        self.init({"default": {"count": 1}})
        before = self.info()
        out, _ = self.main("cpu", "add", "--pool", "gpu", "--count", 2, "--env", "A=1", "--env", "B=x=y",
                           "--daemon", self.root / "D2", "--dpool", "k1-gpu")
        self.assertEqual(out.splitlines()[0], "pool gpu count 0 -> 2")
        self.assertIn("下次 boot 生效", out)
        after = self.info()
        self.assertEqual(after["pools"].pop("gpu"), {"count": 2, "envs": {"A": "1", "B": "x=y"},
                                                     "daemon": str(self.root / "D2"), "dpool": "k1-gpu"})
        self.assertEqual(after, before)
        self.assertFalse(list(self.K.glob(".*.tmp")))
        self.assertEqual(list((self.K / "requests").iterdir()), [])

    def test_add_default_count_one_and_existing_adds(self):
        self.init({"default": {"count": 1}})
        self.assertEqual(self.main("cpu", "add", "--pool", "x")[0].splitlines()[0], "pool x count 0 -> 1")
        self.assertEqual(self.main("cpu", "add", "--pool", "default", "--count", 3)[0].splitlines()[0],
                         "pool default count 1 -> 4")
        self.assertEqual(self.pools()["default"], {"count": 4})

    def test_add_existing_with_env_daemon_dpool_is_pool_exists(self):
        self.init({"default": {"count": 1}})
        before = self.info()
        for extra in (["--env", "A=1"], ["--daemon", "/abs/D"], ["--dpool", "other"]):
            with self.subTest(extra=extra):
                _, err = self.main("cpu", "add", "--pool", "default", *extra, code=2)
                self.assertTrue(err.startswith("aos-kernel: PoolExists: "), err)
                self.assertEqual(self.info(), before)

    def test_kernel_pool_and_bad_arguments_are_usage(self):
        self.init({"default": {"count": 2}})
        before = self.info()
        for args in (["add", "--pool", "kernel"], ["rm", "kernel/0"], ["rm", "--pool", "kernel", "--count", 1],
                     ["add", "--pool", "a/b"], ["add", "--pool", "x", "--count", -1], ["add", "--pool", "x", "--env", "NOEQ"],
                     ["add", "--pool", "x", "--env", "=v"], ["add", "--pool", "x", "--env", "A=1", "--env", "A=2"],
                     ["add", "--pool", "x", "--env", "$ref=v"], ["add", "--pool", "x", "--dpool", "a/b"],
                     ["rm", "default/01"], ["rm", "default"], ["rm"], ["rm", "default/0", "--pool", "default"],
                     ["rm", "--pool", "default"], ["rm", "--pool", "default", "--count", 0],
                     ["rm", "--pool", "default", "--count", -2], ["rm", "--pool", "default", "--count", 3],
                     ["add"], ["ls", "--pool", ""]):
            with self.subTest(args=args):
                _, err = self.main("cpu", *args, code=2)
                self.assertEqual(len(err.splitlines()), 1, err)
                self.assertEqual(self.info(), before)

    def test_rm_member_writes_sorted_skip(self):
        self.init({"default": {"count": 4, "skip": [2]}})
        self.assertEqual(self.main("cpu", "rm", "default/1")[0].splitlines()[0], "pool default count 4 -> 3")
        self.assertEqual(self.pools()["default"], {"count": 3, "skip": [1, 2]})
        self.assertEqual(kernel.members(3, [1, 2]), [0, 3, 4])

    def test_rm_not_member_is_not_found(self):
        self.init({"default": {"count": 2, "skip": [1]}})
        before = self.info()
        for name in ("default/1", "default/9", "nope/0"):
            with self.subTest(name=name):
                _, err = self.main("cpu", "rm", name, code=1)
                self.assertTrue(err.startswith("aos-kernel: NotFound: "), err)
                self.assertEqual(self.info(), before)

    def test_rm_keeps_skip_above_top_member(self):
        """D-38 隊長裁定：skip 一律保留不丟（Q4 永久退休優先於 skip 長度），排序、去重照做。"""
        self.init({"default": {"count": 2}})
        self.edit_info(default={"count": 2, "skip": [5, 1]})
        self.main("cpu", "add", "--pool", "default")
        self.assertEqual(self.pools()["default"], {"count": 3, "skip": [1, 5]})

    def test_rm_max_member_then_add_does_not_reuse_it(self):
        """D-38：cpu rm P/<最大號> 退休的號永久退休，之後 cpu add 不會用回那號。"""
        self.init({"default": {"count": 3}})
        self.main("cpu", "rm", "default/2")
        self.assertEqual(self.pools()["default"], {"count": 2, "skip": [2]})
        self.main("cpu", "add", "--pool", "default")
        self.assertEqual(self.pools()["default"], {"count": 3, "skip": [2]})
        self.assertEqual(kernel.members(3, [2]), [0, 1, 3])

    def test_rm_count_takes_largest(self):
        self.init({"default": {"count": 5, "skip": [1]}})
        self.assertEqual(self.main("cpu", "rm", "--pool", "default", "--count", 2)[0].splitlines()[0],
                         "pool default count 5 -> 3")
        self.assertEqual(self.pools()["default"], {"count": 3, "skip": [1]})
        self.main("cpu", "rm", "--pool", "default", "--count", 3)
        self.assertEqual(self.pools()["default"], {"count": 0, "skip": [1]})

    def test_directives_elsewhere_are_kept(self):
        self.init({"default": {"count": 1, "envs": {"A": {"$env": "HOME"}}}})
        raw = self.info()
        aos_home.write_json(self.K / "iv.json", 7)
        raw["interval_ms"] = {"$ref": "iv.json"}
        aos_home.write_json(self.K / "info.json", raw)
        self.assertEqual(kernel.load_info(self.K)["interval_ms"], 7)
        self.main("cpu", "add", "--pool", "default")
        after = self.info()
        self.assertEqual(after["interval_ms"], {"$ref": "iv.json"})
        self.assertEqual(after["pools"]["default"], {"count": 2, "envs": {"A": {"$env": "HOME"}}})

    def test_directive_count_or_pools_is_not_literal(self):
        self.init({"default": {"count": 1}})
        aos_home.write_json(self.K / "n.json", 2)
        self.edit_info(default={"count": {"$ref": "n.json"}})
        before = self.info()
        _, err = self.main("cpu", "add", "--pool", "default", code=1)
        self.assertTrue(err.startswith("aos-kernel: NotLiteral: "), err)
        self.assertEqual(self.info(), before)
        # 新池不用碰那格：照樣可以加
        self.main("cpu", "add", "--pool", "other")
        self.assertEqual(self.pools()["default"], {"count": {"$ref": "n.json"}})

    def test_invalid_result_is_not_written(self):
        self.init({"default": {"count": 1}})
        before = self.info()
        _, err = self.main("cpu", "add", "--pool", "default", "--count", 1000000, code=1)
        self.assertTrue(err.startswith("aos-kernel: FieldTypeMismatch: "), err)
        self.assertEqual(self.info(), before)

    def test_broken_or_missing_info(self):
        _, err = self.main("cpu", "add", "--pool", "x", code=1)
        self.assertTrue(err.startswith("aos-kernel: ReadFailed: "), err)
        self.assertFalse(self.K.exists())
        self.init({})
        (self.K / "info.json").write_text("{")
        self.main("cpu", "add", "--pool", "x", code=1)
        self.assertEqual((self.K / "info.json").read_text(), "{")

    def test_lock_busy(self):
        self.init({})
        fd = os.open(self.K / ".info.lock", os.O_RDWR | os.O_CREAT)
        self.addCleanup(os.close, fd)
        fcntl.flock(fd, fcntl.LOCK_EX)
        with patch.object(aos_kernel_cpu, "LOCK_WAIT_S", 0.1):
            _, err = self.main("cpu", "add", "--pool", "x", code=1)
        self.assertTrue(err.startswith("aos-kernel: Busy: "), err)
        self.assertNotIn("x", self.pools())

    def test_concurrent_adds_queue_up(self):
        self.init({"default": {"count": 0}})
        errors = []

        def worker():
            for _ in range(10):
                try:
                    aos_kernel_cpu.cpu_add(self.K, "default")
                except Exception as exc:  # pragma: no cover - 失敗時看得到原因
                    errors.append(exc)
        threads = [threading.Thread(target=worker) for _ in range(3)]
        with contextlib.redirect_stdout(io.StringIO()):
            for t in threads:
                t.start()
            for t in threads:
                t.join(30)
        self.assertEqual(errors, [])
        self.assertEqual(self.pools()["default"]["count"], 30)

    def test_running_kernel_has_no_boot_line_and_next_tick_declares(self):
        self.booted({"default": {"count": 1}})
        out, _ = self.main("cpu", "add", "--pool", "default", "--count", 2)
        self.assertEqual(out, "pool default count 1 -> 3\n")
        state = self.ticks(3)
        self.assertEqual(state["pools"]["default"]["sent"], {"count": 3, "skip": []})
        self.main("cpu", "rm", "default/1")
        state = self.ticks(3)
        self.assertEqual(state["pools"]["default"]["sent"], {"count": 2, "skip": [1]})
        self.assertEqual(self.fake.pool("default")["skip"], [1])


class CpuLs(CpuCase):
    def test_ls_before_boot(self):
        self.init({"default": {"count": 2}})
        out, _ = self.main("cpu", "ls")
        lines = out.splitlines()
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("kernel   want 1  sent -   daemon kernel: 沒有這池"), lines[0])
        self.assertIn("default  want 2  sent -   daemon default: 沒有這池", lines[1])
        self.assertIn("還沒宣告", lines[1])

    def test_ls_running_pools(self):
        self.booted({"default": {"count": 2}, "llm": {"count": 1}})
        out, _ = self.main("cpu", "ls")
        lines = out.splitlines()
        self.assertEqual(lines[0], "kernel   want 1  sent 1   daemon kernel: running 1 pending 0 dead 0 failed 0")
        self.assertEqual(lines[1], "default  want 2  sent 2  busy 0  idle 2  draining 0   "
                                   "daemon default: running 2 pending 0 dead 0 failed 0")
        # restarting 是 running 的子集：>0 才寫進 running 那格（使用者代裁）；--json 照舊分兩欄
        row = {"pool": "default", "want": 2, "sent": 2, "declared": True, "busy": 0, "idle": 2, "draining": 0,
               "daemon": "/d", "dpool": "default", "error": None, "gone": False, "pending": None,
               "phase": "running", "daemon_alive": True, "moving": False, "removing": False, "waiting": [],
               "summary": {"running": 2, "restarting": 1, "pending": 0, "dead": 0, "failed": 0}}
        self.assertEqual(aos_kernel_rows.row_line("/k", {"daemon": "/d"}, row),
                         "default  want 2  sent 2  busy 0  idle 2  draining 0   "
                         "daemon default: running 2（含 restarting 1） pending 0 dead 0 failed 0")
        self.assertTrue(lines[2].startswith("llm      want 1  sent 1  busy 0  idle 1"), lines[2])

    def test_ls_pool_one_line_per_cpu_with_kids(self):
        self.booted({"default": {"count": 3}})
        kids = self.fake.home / "pools" / "default" / "kids"
        kids.mkdir(parents=True, exist_ok=True)
        aos_home.write_json(kids / "1.json", {"pid": 5, "gen": 3, "state": "failed"})
        self.add("job")
        state = self.tick()
        key = next(iter(state["busy"]))
        out, _ = self.main("cpu", "ls", "--pool", "default")
        lines = out.splitlines()
        self.assertTrue(lines[0].startswith("default  want 3  sent 3  busy 1  idle 2"), lines[0])
        self.assertIn("%s  busy job  daemon pending" % key, lines)
        self.assertIn("default/1  idle  daemon failed gen 3", lines)
        self.assertEqual(len(lines), 4)

    def test_draining_shows_waiting_proc(self):
        self.booted({"default": {"count": 2}})
        self.add("job")
        state = self.tick()
        key = next(iter(state["busy"]))
        self.main("cpu", "rm", key)
        # run.md 碰到的問題 3：cpu rm 剛下時池行的 draining 要跟單顆行對得上，不必等帳本下一格重算。
        out, _ = self.main("cpu", "ls", "--pool", "default")
        self.assertIn("收掉中 1 顆，等 job", out.splitlines()[0])
        self.assertRegex(out.splitlines()[0], r"\bdraining 1\b")
        self.assertIn("%s  draining job" % key, out)
        self.ticks(2)
        out, _ = self.main("cpu", "ls", "--pool", "default")
        self.assertIn("收掉中 1 顆，等 job", out.splitlines()[0])
        self.assertIn("%s  draining job" % key, out)
        self.respond(key)
        self.ticks(3)
        out, _ = self.main("cpu", "ls")
        self.assertNotIn("收掉中", out)
        self.assertRegex(out, r"default  want 1  sent 1  busy \d  idle \d  draining 0 ")

    def test_pending_scale_order_wording(self):
        # run.md 碰到的問題 1／4：daemon 活著、kernel 在跑時「等下一格」，kernel 停機時「等下次 boot」。
        self.booted({"default": {"count": 1}})
        self.main("cpu", "add", "--pool", "default")
        self.tick(process=False)
        out, _ = self.main("cpu", "ls", "--pool", "default")
        self.assertIn("宣告已送出，下一格確認", out.splitlines()[0])
        state = self.state()
        state["phase"] = "stopped"
        aos_home.write_json(self.K / "state.json", state)
        out, _ = self.main("cpu", "ls", "--pool", "default")
        self.assertIn("停機中，下次 boot 收回音", out.splitlines()[0])
        self.assertNotIn("在路上", out)

    def test_error_pending_dead_daemon_moving_removed(self):
        self.booted({"default": {"count": 1}, "gpu": {"count": 1}})
        self.fake.errors["gpu"] = ["NameTaken"]
        self.main("cpu", "add", "--pool", "gpu")
        self.ticks(2)
        out, _ = self.main("cpu", "ls")
        self.assertIn("daemon gpu: 錯誤 NameTaken（NameTaken）", out)
        # daemon 沒在跑：單留在路上
        self.fake.set_alive(False)
        self.main("cpu", "add", "--pool", "default")
        self.tick(process=False)
        out, _ = self.main("cpu", "ls", "--pool", "default")
        self.assertIn("宣告已送出，daemon 沒在跑（daemon 一上線就會收到）", out.splitlines()[0])
        self.fake.set_alive(True)
        self.ticks(2)
        # 搬池
        self.fake.linger.add("default")
        info = self.info()
        info["pools"]["default"]["dpool"] = "moved"
        aos_home.write_json(self.K / "info.json", info)
        self.ticks(2)
        out, _ = self.main("cpu", "ls")
        self.assertIn("搬池中（舊位置收完才換到 %s moved）" % self.D, out)
        # 拿掉池
        self.edit_info(gpu=None)
        self.fake.errors.pop("gpu", None)
        self.tick(process=False)
        out, _ = self.main("cpu", "ls")
        self.assertIn("移除中", out)

    def test_gone_pool(self):
        self.booted({"default": {"count": 1}})
        self.fake.gone("default")
        out, _ = self.main("cpu", "ls")
        self.assertIn("daemon default: 池不見了（跑 aos-kernel boot --target %s）" % self.K, out)

    def test_other_daemon_label(self):
        self.init({"default": {"count": 1, "daemon": "/abs/D9", "dpool": "k9"}})
        out, _ = self.main("cpu", "ls")
        self.assertIn("daemon /abs/D9 k9: 沒有這池", out)

    def test_json_and_unknown_pool(self):
        self.booted({"default": {"count": 2}})
        data = json.loads(self.main("cpu", "ls", "--json")[0])
        self.assertEqual(list(data["pools"]), ["kernel", "default"])
        row = data["pools"]["default"]
        self.assertEqual((row["want"], row["sent"], row["busy"], row["idle"], row["draining"]), (2, 2, 0, 2, 0))
        self.assertEqual(row["summary"]["running"], 2)
        data = json.loads(self.main("cpu", "ls", "--pool", "default", "--json")[0])
        self.assertEqual([c["cpu"] for c in data["pools"]["default"]["cpus"]], ["default/0", "default/1"])
        _, err = self.main("cpu", "ls", "--pool", "nope", code=1)
        self.assertTrue(err.startswith("aos-kernel: NotFound: "), err)

    def test_awaiting_cpu_status_wording_text_only_json_unchanged(self):
        # run.md 碰到的問題 1：剛 cpu add 完、還沒宣告到帳本前，單顆行的字要白話，
        # 但 cpu_rows() 回的 status（--json 也讀這個）不動（team-rules：只改印出來的字）。
        self.init({"default": {"count": 1}})
        out, _ = self.main("cpu", "ls", "--pool", "default")
        self.assertIn("default/0  等 daemon 確認  daemon -", out)
        data = json.loads(self.main("cpu", "ls", "--pool", "default", "--json")[0])
        self.assertEqual(data["pools"]["default"]["cpus"][0]["status"], "待宣告")


class CpuLineWording(unittest.TestCase):
    """cpu_line() 是純文字排版；直接餵假 item，不用拉真假 daemon（run.md 碰到的問題 1／3）。"""

    def test_pending_declared_relabelled_to_plain_words(self):
        line = aos_kernel_rows.cpu_line({"cpu": "default/0", "status": "待宣告", "proc": None,
                                        "daemon": None, "declared": False})
        self.assertEqual(line, "default/0  等 daemon 確認  daemon -")

    def test_collecting_with_no_kid_record_reads_as_in_progress_not_pending(self):
        line = aos_kernel_rows.cpu_line({"cpu": "default/0", "status": "收掉中", "proc": None,
                                        "daemon": None, "declared": True})
        self.assertEqual(line, "default/0  收掉中  daemon 在收")

    def test_busy_with_no_kid_record_is_unchanged(self):
        line = aos_kernel_rows.cpu_line({"cpu": "default/1", "status": "busy", "proc": "job",
                                        "daemon": None, "declared": True})
        self.assertEqual(line, "default/1  busy job  daemon pending")

    def test_idle_with_kid_record_is_unchanged(self):
        line = aos_kernel_rows.cpu_line({"cpu": "default/1", "status": "idle", "proc": None,
                                        "daemon": {"state": "running", "gen": 2, "pid": 5}, "declared": True})
        self.assertEqual(line, "default/1  idle  daemon running gen 2")
