"""kernel 骨架（spec.md）：設定、state、快照、執行順序、送出與核對。驗收條號見 kernel-pack §9。"""
import json
import os
from pathlib import Path
import subprocess
import time
import unittest
from functools import partial
from unittest.mock import patch

from kernelcase import BRAIN, FAKE, KERNEL, PACK, PY, RUN, CoreCase, KernelMixin, read_json, write_json
from base import DaemonCase
from aos7_kernel_state import load_state, sha_of, snapshot


class KernelSmoke(KernelMixin, CoreCase):
    def setUp(self):
        super().setUp()
        self.setup_kernel()

    def test_kill_round_trip(self):
        """存意圖 → 送 ctl → 核心收掉 → 回條 ok → done；keep 重起新 run，不再 kill。"""
        self.cfg([self.kill_rule(until=1)])
        run = self.brain_run()
        p = self.tock_kernel(1)
        self.assertEqual(p.returncode, 0, self.show(p))
        st = self.state()
        self.assertEqual(len(st["pending"]), 1, self.show(p))
        self.assertEqual(self.ctl()["run"], run)
        self.assertEqual(self.ctl()["id"], st["pending"][0]["id"])
        self.core_round()
        self.assertEqual(self.receipt()["result"]["ok"], True, self.receipt())
        p = self.tock_kernel(2)
        st = self.state()
        self.assertEqual(st["pending"], [], self.show(p))
        self.assertEqual(st["done"][-1]["result"], "ok")
        self.assertEqual(st["done"][-1]["basis"], {"t": "test"})
        self.core_round()
        self.assertNotEqual(self.brain_run(), run)
        p = self.tock_kernel(3)
        self.assertIsNone(self.ctl(), self.show(p))


class KernelCore(KernelMixin, CoreCase):
    def setUp(self):
        super().setUp()
        self.setup_kernel()

    def assert_ok(self, p):
        self.assertEqual(p.returncode, 0, self.show(p))

    def assert_error(self, p, code):
        self.assertEqual(p.returncode, code, self.show(p))
        lines = p.stderr.splitlines()
        self.assertEqual(len(lines), 1, p.stderr)
        self.assertTrue(lines[0].startswith("aos7-kernel: "), p.stderr)
        self.assertIn("。", lines[0])
        if code == 3:
            self.assertIn("不確定：", lines[0])

    def no_ctl(self):
        self.assertFalse(Path(self.brain_slot(), "ctl.json").exists())

    def test_k01_minimal_official_entry(self):
        """K01：正式入口只用 noop 啟動，建立 state 而不送控制或載入擴充。"""
        self.cfg([{"name": "noop"}])
        write_json(os.path.join(self.kslot, "tock.json"), {"run": RUN, "round": 1})
        self.assert_ok(self.kernel("run", "--rounds", "1", entry=KERNEL))
        st = self.state()
        self.assertEqual(st["v"], 1)
        self.assertTrue(st["instance"])
        self.assertEqual(st["last_tock"], 1)
        self.no_ctl()
        # 在乾淨子程序檢查傳遞 import，避免測試程序本身已載入核心造成誤判。
        code = ("import sys; sys.path.insert(0, %r); import aos7_kernel; "
                "print(__import__('json').dumps(sorted(sys.modules)))") % PACK
        p = subprocess.run([PY, "-B", "-c", code], capture_output=True, text=True, timeout=10)
        self.assertEqual(p.returncode, 0, p.stderr)
        forbidden = {"aos7_step", "aos7_budget", "aos7_adapt"}
        self.assertFalse(forbidden.intersection(json.loads(p.stdout)))

    def test_k02_dry_run_expired_candidate_not_delivered(self):
        """K02：已有 state 的模擬位元組不變，過期候選不能在正常回合交付。"""
        # 建立尚未收到 tock 的正式初始 state；候選只在模擬的第零回合成立。
        cfg = self.cfg([self.kill_rule(frm=0, until=0)])
        load_state(self.kslot, sha_of(cfg))
        paths = [Path(self.kslot, name) for name in ("state.json", "decisions.json")]
        before = [p.read_bytes() for p in paths]
        p = self.kernel("run", "--dry-run")
        self.assert_ok(p)
        self.assertEqual(len(p.stdout.splitlines()), 1)
        rec = json.loads(p.stdout)
        self.assertIn("decided", rec)
        self.assertEqual(len(rec["decided"]), 1)
        ident = rec["decided"][0]["id"]
        self.assertEqual([p.read_bytes() for p in paths], before)
        self.no_ctl()
        self.assert_ok(self.tock_kernel(1))
        self.assertNotIn(ident, [p["id"] for p in self.state()["pending"]])
        self.assertEqual(self.state()["pending"], [])
        self.no_ctl()

    def test_k02_dry_run_existing_state(self):
        """K02：同候選在模擬與下一正常回合皆成立，模擬 id 仍不能進 pending。"""
        cfg = self.cfg([self.kill_rule(frm=0)])
        load_state(self.kslot, sha_of(cfg))
        paths = [Path(self.kslot, name) for name in ("state.json", "decisions.json")]
        before = [p.read_bytes() for p in paths]
        p = self.kernel("run", "--dry-run")
        self.assert_ok(p)
        self.assertEqual(len(p.stdout.splitlines()), 1)
        rec = json.loads(p.stdout)
        self.assertEqual(len(rec["decided"]), 1)
        ident = rec["decided"][0]["id"]
        self.assertEqual([p.read_bytes() for p in paths], before)
        self.no_ctl()
        self.assert_ok(self.tock_kernel(1))
        pending = self.state()["pending"]
        # 正常回合可以重新決定 kill，但必須與模擬決定區分 id。
        self.assertEqual(len(pending), 1)
        self.assertNotIn(ident, [p["id"] for p in pending])
        self.assertEqual(self.ctl()["id"], pending[0]["id"])

    def test_k02_dry_run_fresh_slot(self):
        """K02：全新槽 dry-run 有候選也不建 state、decisions 或 ctl。"""
        self.cfg([self.kill_rule(frm=0)])
        p = self.kernel("run", "--dry-run")
        self.assert_ok(p)
        self.assertEqual(len(p.stdout.splitlines()), 1)
        self.assertTrue(json.loads(p.stdout)["decided"])
        for name in ("state.json", "decisions.json"):
            self.assertFalse(Path(self.kslot, name).exists())
        self.no_ctl()

    def rejected_rules(self, rules):
        cfg = self.cfg(rules)
        st = load_state(self.kslot, sha_of(cfg))
        # 非空舊規則狀態能抓到拒絕時被清空或被候選狀態取代的錯誤。
        st["rules"] = {r["name"]: {"old": "保留"} for r in rules}
        write_json(os.path.join(self.kslot, "state.json"), st)
        self.assert_ok(self.tock_kernel(1))
        got = self.state()
        self.no_ctl()
        self.assertEqual(got["pending"], [])
        self.assertEqual(got["rules"], st["rules"])
        self.assertTrue(got["last_error"])
        self.assertTrue(self.decisions()["rejected"])
        self.assertEqual(self.decisions()["decided"], [])

    def raw_rule(self, candidate, **extra):
        return dict(name="raw", ret=[{"new": "不可提交"}, [candidate]], **extra)

    def test_k03_unknown_operation(self):
        """K03：未知 op 整份拒絕，連另一條合法規則也不能部分提交。"""
        self.rejected_rules([self.kill_rule(), self.raw_rule({"op": "restart"})])

    def test_k03_string_run(self):
        """K03：kill 的 run 字串不視為整數，規則狀態保持原樣。"""
        c = dict(self.kill_rule()["emit"][0], run="1")
        self.rejected_rules([self.raw_rule(c)])

    def test_k03_boolean_run(self):
        """K03：kill 的 run 為 true 也拒絕，不能冒充整數一。"""
        c = dict(self.kill_rule()["emit"][0], run=True)
        self.rejected_rules([self.raw_rule(c)])

    def test_k03_unlisted_target(self):
        """K03：候選目標不在 targets 時不送 ctl，留下拒絕原因。"""
        c = dict(self.kill_rule()["emit"][0], run=self.brain_run(), target={"node": "a", "slot": "other"})
        self.rejected_rules([self.raw_rule(c)])
        self.assertFalse(Path(self.node, ".aos", "tasks", "other", "ctl.json").exists())

    def test_k03_list_return(self):
        """K03：規則回 list 而非二項 tuple 時整份拒絕。"""
        c = dict(self.kill_rule()["emit"][0], run=self.brain_run())
        self.rejected_rules([self.raw_rule(c, ret_shape="list")])

    def test_k03_rule_exception(self):
        """K03：規則丟例外，合法候選與新規則狀態都不能提交。"""
        self.rejected_rules([self.kill_rule(), {"name": "boom"}])

    def test_k03_conflicting_runs(self):
        """K03：兩條規則對同槽指定不同 run 時整份拒絕。"""
        c = dict(self.kill_rule()["emit"][0], run=self.brain_run() + 1)
        self.rejected_rules([self.kill_rule(), self.raw_rule(c)])

    def test_k03_duplicate_kills_merge(self):
        """K03、K21：同一規則重複 emit 相同 kill 合併成一筆 pending。"""
        rule = self.kill_rule()
        rule["emit"] *= 2
        self.cfg([rule])
        self.assert_ok(self.tock_kernel(1))
        pending = self.state()["pending"]
        self.assertEqual(len(pending), 1)
        self.assertEqual(len(self.decisions()["decided"]), 1)
        self.assertEqual(self.ctl()["id"], pending[0]["id"])

    def wait_without_progress(self, tock):
        write_json(os.path.join(self.kslot, "tock.json"), tock)
        before = Path(self.kslot, "state.json").read_bytes()
        p = subprocess.Popen([PY, "-B", FAKE, "run", "--rounds", "1"],
                             cwd=self.node, env=self.kenv(), stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, start_new_session=True)
        self.procs.append(p)
        try:
            # 等待一秒仍未完成＝沒有把無效 tock 算成一個新回合。
            with self.assertRaises(subprocess.TimeoutExpired):
                p.wait(timeout=1)
            self.assertEqual(Path(self.kslot, "state.json").read_bytes(), before)
            self.assertEqual(self.state()["pending"], [])
            self.no_ctl()
        finally:
            p.terminate()
            out, err = p.communicate(timeout=5)
        self.assertEqual(p.returncode, 0, (out, err))

    def test_k04_repeated_tock(self):
        """K04：同號 tock 第二次不處理，rev 與 pending 保持原樣。"""
        self.cfg([{"name": "echo", "emit": []}])
        self.assert_ok(self.tock_kernel(1))
        self.wait_without_progress({"run": RUN, "round": 1})

    def test_k04_other_run_tock(self):
        """K04：別的 run 的新 tock 不處理，也不更新水位。"""
        self.cfg([{"name": "echo", "emit": []}])
        self.assert_ok(self.tock_kernel(1))
        self.wait_without_progress({"run": 99, "round": 2})

    def test_k04_skipped_tocks(self):
        """K04：從一跳到五只叫規則一次，不補造二到四的回合。"""
        self.cfg([{"name": "echo", "emit": []}])
        self.assert_ok(self.tock_kernel(1))
        rev = self.state()["rev"]
        self.assert_ok(self.tock_kernel(5))
        st = self.state()
        self.assertEqual(st["last_tock"], 5)
        self.assertEqual(st["rules"]["echo"]["seen"], 5)
        self.assertEqual(st["rev"], rev + 1)

    def test_k06_snapshot_four_states_and_clock(self):
        """K06：快照區分缺檔、壞檔、FIFO、無 birth 與正常值，完成回合照來源鐘。"""
        cfg = self.cfg([{"name": "noop"}])
        env = {"node": self.node, "node_id": "a"}
        task = Path(self.node, "brain", "task.json")
        task.parent.mkdir(exist_ok=True)

        def snap_task(read, value=None):
            started = time.monotonic()
            items = snapshot(env, cfg, resolve=lambda p: None)
            self.assertLess(time.monotonic() - started, 1)
            self.assertEqual(len(items), 2)
            for item in items:
                self.assertNotEqual(item, {})
                self.assertNotEqual(item["value"], {})
            self.assertEqual(items[1]["read"], read)
            self.assertEqual(items[1]["value"], value)
            return items

        snap_task("absent")
        task.write_text("{壞掉", encoding="utf-8")
        snap_task("bad")
        task.unlink()
        os.mkfifo(task)
        # 子程序逾時保護：若一般檔檢查退化，FIFO 讀取不能卡死整個測試。
        code = ("import sys; sys.path.insert(0, %r); from aos7_kernel_state import snapshot; "
                "import json; print(json.dumps(snapshot(%r, %r, lambda p: None)))") % (PACK, env, cfg)
        p = subprocess.run([PY, "-B", "-c", code], capture_output=True, text=True, timeout=3)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout)[1]["read"], "unknown")
        snap_task("unknown")
        task.unlink()
        value = {"id": "工作", "step": 7}
        write_json(str(task), value)
        birth = Path(self.brain_slot(), "birth.json")
        old_birth = birth.read_bytes()
        birth.unlink()
        items = snap_task("unknown")
        self.assertEqual(items[0]["read"], "absent")
        birth.write_bytes(old_birth)
        items = snap_task("ok", value)
        self.assertEqual(items[1]["run"], self.brain_run())
        self.assertEqual(items[1]["seq"], 7)
        clock = Path(self.node, ".aos", "round.json")
        for opened, expected in ((True, 8), (False, 9)):
            write_json(str(clock), {"round": 9, "open": opened})
            for item in snap_task("ok", value):
                self.assertEqual(item["completed_tock"], expected)
        clock.unlink()
        for item in snap_task("ok", value):
            self.assertEqual(item["completed_tock"], 0)
        clock.write_text("bad", encoding="utf-8")
        for item in snap_task("ok", value):
            self.assertIsNone(item["completed_tock"])

    def test_k10_corrupt_state_preserved(self):
        """K10：state 壞 JSON 退三，原位元組不變且不送控制。"""
        self.cfg([self.kill_rule()])
        path = Path(self.kslot, "state.json")
        path.write_bytes(b"{broken")
        before = path.read_bytes()
        self.assert_error(self.tock_kernel(1), 3)
        self.assertEqual(path.read_bytes(), before)
        self.no_ctl()

    def test_k10_missing_state_not_reinitialized(self):
        """K10：decisions 尚在而 state 遺失退一，不能當新槽重建。"""
        self.cfg([{"name": "noop"}])
        self.assert_ok(self.tock_kernel(1))
        path = Path(self.kslot, "state.json")
        path.unlink()
        self.assert_error(self.tock_kernel(2), 1)
        self.assertFalse(path.exists())
        self.no_ctl()

    def test_k10_config_changed_keeps_pending(self):
        """K10：設定內容變更退一，在途意圖完整保留而不補送 ctl。"""
        cfg = self.cfg([self.kill_rule()])
        self.assert_ok(self.tock_kernel(1))
        before = Path(self.kslot, "state.json").read_bytes()
        Path(self.brain_slot(), "ctl.json").unlink()
        cfg["rules"][0]["extra"] = "改動"
        write_json(os.path.join(self.node, "kernel", "kernel.json"), cfg)
        self.assert_error(self.tock_kernel(2), 1)
        self.assertEqual(Path(self.kslot, "state.json").read_bytes(), before)
        self.assertEqual(len(self.state()["pending"]), 1)
        self.no_ctl()

    def test_k10_bad_config(self):
        """K10：kernel.json 壞 JSON 退二，不建立 state 或控制。"""
        self.cfg([{"name": "noop"}])
        Path(self.node, "kernel", "kernel.json").write_text("{bad", encoding="utf-8")
        self.assert_error(self.tock_kernel(1), 2)
        self.assertFalse(Path(self.kslot, "state.json").exists())
        self.no_ctl()

    def test_k10_target_outside_sources(self):
        """K10：targets 不在 sources 的設定退二，不能偷偷控制未知槽。"""
        self.cfg([{"name": "noop"}], targets=[{"node": "a", "slot": "other"}])
        self.assert_error(self.tock_kernel(1), 2)
        self.assertFalse(Path(self.kslot, "state.json").exists())
        self.no_ctl()

    def test_k21_control_conflict_then_same_id_delivery(self):
        """K21：別人的 ctl 不覆蓋，核心消耗後沿用原 id 送自己的 kill。"""
        self.cfg([self.kill_rule(until=1)])
        # 別人釘舊 run 的請求會被核心拒絕，目標原 run 留著供自己的意圖交付。
        other = {"op": "kill", "run": self.brain_run() - 1, "id": "other", "by": "human"}
        path = Path(self.brain_slot(), "ctl.json")
        write_json(str(path), other)
        before = path.read_bytes()
        self.assert_ok(self.tock_kernel(1))
        self.assertEqual(path.read_bytes(), before)
        pending = self.state()["pending"]
        self.assertEqual(len(pending), 1)
        self.assertIsInstance(pending[0]["wait"], str)
        self.assertTrue(pending[0]["wait"])
        ident, run = pending[0]["id"], pending[0]["run"]
        self.core_round()
        self.assertFalse(path.exists())
        self.assertEqual(self.receipt()["id"], "other")
        self.assertFalse(self.receipt()["result"]["ok"])
        self.tick("a")
        self.assert_ok(self.tock_kernel(2))
        self.assertEqual(self.ctl()["id"], ident)
        self.assertEqual(self.ctl()["run"], run)
        self.tock("a")
        killed = self.exit_of(self.node, "brain")
        self.assertEqual(killed["run"], run)
        self.assertLess(killed["code"], 0)
        self.assert_ok(self.tock_kernel(3))
        self.assertEqual(self.state()["pending"], [])
        self.assertEqual(self.state()["done"][-1]["id"], ident)

    def test_k21_pending_target_skips_new_candidate(self):
        """K21：目標已有 pending 時新 kill 不新增，decisions 留略過說明。"""
        rule = dict(self.kill_rule(), once=False)
        self.cfg([rule])
        self.assert_ok(self.tock_kernel(1))
        before = self.state()["pending"]
        ctl = Path(self.brain_slot(), "ctl.json").read_bytes()
        self.assert_ok(self.tock_kernel(2))
        self.assertEqual(self.state()["pending"], before)
        self.assertEqual(Path(self.brain_slot(), "ctl.json").read_bytes(), ctl)
        self.assertEqual(self.decisions()["decided"], [])
        self.assertTrue(self.decisions()["note"])

    def test_k24_three_hundred_tocks_bounded_state(self):
        """K24：三百 tock 每五十回合 kill，兩次遺失 decisions 重起也不累積歷史。"""
        self.cfg([dict(self.kill_rule(frm=50, until=300), once=False)])
        # 薄入口只加週期門檻，仍由共用 echo 產生候選，正式 kernel 處理所有狀態與控制。
        entry = Path(self.root, "periodic_kernel.py")
        entry.write_text("import sys\nsys.path.insert(0, %r)\nimport kernel_fake as fake\n"
                         "def periodic(ctx, snap, rstate):\n"
                         "    if ctx['tock'] %% 50: return dict(rstate, seen=ctx['tock']), []\n"
                         "    return fake.echo(ctx, snap, rstate)\n"
                         "sys.exit(fake.aos7_kernel.main(rules=dict(fake.RULES, echo=periodic)))\n"
                         % os.path.dirname(FAKE), encoding="utf-8")
        sizes, ids = [], []
        started = time.monotonic()
        with patch.object(self, "kernel", partial(self.kernel, entry=str(entry))):
            for n in range(1, 301):
                if n in (100, 200):
                    Path(self.kslot, "decisions.json").unlink()
                if n % 50 == 0:
                    self.tick("a")
                self.assert_ok(self.tock_kernel(n))
                st = self.state()
                self.assertEqual(st["last_tock"], n)
                self.assertLessEqual(len(st["done"]), 20)
                if n % 50 == 0:
                    self.assertEqual(len(st["pending"]), 1)
                    self.assertEqual(self.ctl()["id"], st["pending"][0]["id"])
                    run = self.brain_run()
                    ident = self.ctl()["id"]
                    ids.append(ident)
                    self.tock("a")
                    self.assertEqual(self.receipt()["id"], ident)
                    self.assertTrue(self.receipt()["result"]["ok"])
                    killed = self.exit_of(self.node, "brain")
                    self.assertEqual(killed["run"], run)
                    self.assertLess(killed["code"], 0)
                    self.core_round()
                    self.assertNotEqual(self.brain_run(), run)
                else:
                    self.assertEqual(st["pending"], [])
                if n in (100, 200, 300):
                    sizes.append(Path(self.kslot, "state.json").stat().st_size)
        self.assertLess(time.monotonic() - started, 120)
        self.assertEqual(len(set(ids)), 6)
        self.assertEqual(len(self.state()["done"]), 5)
        self.assertLess(max(sizes) - min(sizes), 2048, sizes)

    def official_status(self):
        # status 不帶任務環境，且依正式槽與 tasks 表定位。
        env = {k: v for k, v in os.environ.items() if not k.startswith("AOS7_")}
        return subprocess.run([PY, "-B", KERNEL, "status", self.node], env=env,
                              capture_output=True, text=True, timeout=10)

    def register_status_slot(self):
        self.set_tasks(self.node, self.tasks(self.node) + [
            {"name": "kslot", "argv": ["python3", KERNEL, "run"], "enabled": False}])
        Path(self.slot(self.node, "kslot")).mkdir(exist_ok=True)
        for name in ("state.json", "decisions.json"):
            Path(self.slot(self.node, "kslot"), name).write_bytes(Path(self.kslot, name).read_bytes())

    def test_status_missing_kernel_config(self):
        """status：沒有 kernel.json 退二，stderr 一行帶程式名與句點。"""
        self.assert_error(self.official_status(), 2)

    def test_status_no_pending(self):
        """status：從 tasks 表找到正式槽，沒有 pending 顯示監督一件都在動。"""
        self.cfg([{"name": "noop"}])
        self.assert_ok(self.tock_kernel(1))
        self.register_status_slot()
        p = self.official_status()
        self.assert_ok(p)
        self.assertEqual(len(p.stdout.splitlines()), 1)
        self.assertIn("監督 1 件：都在動", p.stdout)

    def test_status_pending_kill(self):
        """status：在途 kill 顯示原 run 與等回條。"""
        self.cfg([self.kill_rule()])
        self.assert_ok(self.tock_kernel(1))
        cfg = self.cfg([{'name': 'noop'}])
        write_json(os.path.join(self.kslot, 'state.json'), dict(self.state(), config_sha=sha_of(cfg)))
        self.register_status_slot()
        p = self.official_status()
        self.assert_ok(p)
        self.assertEqual(len(p.stdout.splitlines()), 1)
        self.assertIn("等回條", p.stdout)
        self.assertIn("brain#%d" % self.brain_run(), p.stdout)

    def test_config_validation_before_initialization(self):
        cases = [{'no_progress_rounds': v} for v in (True, 0, -1, '6')]
        cases += [{'kill_after_rounds': v} for v in (False, 0, 6, '12')]
        cases += [{'max_kills': v} for v in (True, 0, -1, '3')]
        cases += [{'no_progress_rounds': 12}, {'no_progress_rounds': 10, 'kill_after_rounds': 9}]
        for params in cases:
            with self.subTest(params=params):
                self.cfg([dict(name='supervise-brain', **params)])
                self.assert_error(self.tock_kernel(1), 2)
                self.assert_error(self.official_status(), 2)
                self.assertFalse(Path(self.kslot, 'state.json').exists())
        self.cfg([{'name': 'noop'}], sources=[dict(node=f'n{i}', slot='brain', kind='brain') for i in range(11)],
                 targets=[dict(node='n0', slot='brain')])
        self.assert_error(self.tock_kernel(1), 2)
        self.cfg([{'name': 'noop'}], mail={'root': '..', 'from': 123})
        self.assert_error(self.tock_kernel(1), 2)

    def test_deep_state_validation_preserves_bytes(self):
        cfg = self.cfg([{'name': 'noop'}])
        base = load_state(self.kslot, sha_of(cfg))
        self.register_status_slot()
        status_path = Path(self.slot(self.node, 'kslot'), 'state.json')
        bad = [dict(base, pending=[None]), dict(base, done=[None]), dict(base, done=[{}])]
        brain = dict(id='信', step=2, run=1, since=1, last=8, notified=True, gap=False)
        for rstate in ([], {'brains': []}, {'gaps': {'a/brain': '壞'}}, {'killed': {'a/brain': True}}, {'notified': {'a/brain': 1}},
                       {'retries': {'a/brain': {'id': '信', 'step': 2, 'count': False}}},
                       {'brains': {'a/brain': dict(brain, last=True)}}):
            bad.append(dict(base, rules={'supervise-brain': rstate}))
        for damaged in bad:
            with self.subTest(damaged=damaged):
                write_json(str(Path(self.kslot, 'state.json')), damaged)
                before = Path(self.kslot, 'state.json').read_bytes()
                status_path.write_bytes(before)
                self.assert_error(self.tock_kernel(1), 3)
                self.assert_error(self.official_status(), 3)
                self.assertEqual(Path(self.kslot, 'state.json').read_bytes(), before)
                self.assertEqual(status_path.read_bytes(), before)
                self.no_ctl()

    def test_status_stall_gap_and_missing_state(self):
        cfg = self.cfg([{'name': 'supervise-brain'}], mail={'root': '..'})
        base = load_state(self.kslot, sha_of(cfg))
        brain = dict(id='信', step=2, run=1, since=1, last=9, notified=True, gap=False)
        state = dict(base, rules={'supervise-brain': {'brains': {'a/brain': brain}, 'notified': {'a/brain': '信'}}})
        write_json(os.path.join(self.kslot, 'state.json'), state)
        self.register_status_slot()
        p = self.official_status()
        self.assert_ok(p)
        self.assertIn('停住 8 回合，已寄信給 you', p.stdout)
        brain['gap'] = True
        write_json(str(Path(self.slot(self.node, 'kslot'), 'state.json')), state)
        p = self.official_status()
        self.assert_ok(p)
        self.assertIn('讀不到，等它恢復', p.stdout)
        Path(self.slot(self.node, 'kslot'), 'state.json').unlink()
        self.assert_error(self.official_status(), 1)

    def test_config_normalization_and_snapshot_title(self):
        from aos7_kernel_state import load_config
        cfg = self.cfg([{'name': 'noop'}], sources=[dict(BRAIN, node='x/../a', kind='brain')])
        normalized, sha = load_config(self.node, {'noop'})
        self.assertEqual(normalized['sources'][0]['node'], normalized['targets'][0]['node'])
        self.assertEqual(sha, sha_of(cfg))
        task = Path(self.node, 'brain', 'task.json')
        write_json(str(task), {'id': '原信', 'step': 2})
        box = Path(self.node, 'inbox', 'done')
        box.mkdir(parents=True)
        letter = box / 'request.md'
        letter.write_text('---\nid: 原信\n---\n# 做 5 回合的整理\n', encoding='utf-8')
        def snap():
            return snapshot(dict(node=self.node, node_id='a'), normalized, lambda _: None)[1]
        self.assertEqual(snap()['title'], '做 5 回合的整理')
        letter.write_bytes(b'\xff')
        self.assertIsNone(snap()['title'])
        self.assertEqual(snap()['read'], 'ok')

    def test_boolean_receipt_and_tock_and_outer_exception(self):
        import aos7_kernel as kernel
        self.assertFalse(kernel._receipt_matches({'id': 'k', 'op': 'kill', 'run': True}, {'id': 'k', 'run': 1}))
        env = dict(task=self.kslot, node=self.node, node_id='a', tid='kernel', run=1)
        self.cfg([{'name': 'noop'}])
        with patch.object(kernel, 'task_env', return_value=env), patch.object(kernel, 'resolver', return_value=lambda _: None), \
                patch.object(kernel, 'wait_tock', side_effect=[True, '2', 1]), \
                patch.object(kernel.signal, 'signal'):
            self.assertEqual(kernel.main(['run', '--rounds', '1']), 0)
        self.assertEqual(self.state()['rev'], 1)
        import io
        with patch.object(kernel, 'status_line', side_effect=RuntimeError('錯\n誤')), patch('sys.stderr', new_callable=io.StringIO) as err:
            self.assertEqual(kernel.main(['status', self.node]), 3)
            self.assertEqual(len(err.getvalue().splitlines()), 1)
            self.assertNotIn('Traceback', err.getvalue())

    def test_candidate_body_validation(self):
        self.rejected_rules([self.raw_rule(dict(op='notify', target='you', text='提醒', body=3, basis={}))])


if __name__ == "__main__":
    unittest.main()
