"""〔control〕控制包：restart／reload 在請求端做（先加釘同槽的 once，再寫 kill 帶 run）。

從 tests/core/test_ctl.py 的 restart 系列、TestMounts 的 restart 帶動態掛載、tests/core/test_errors.py 的 restart 遇壞表、
tests/core/test_matrix_once.py 的 TestRestartCrash、tests/core/test_matrix_a3.py 的 TestCtlId 搬來改寫（頂層定案 1）。

**AOS7_TEST_* 只給測試用**：`AOS7_TEST_CRASH=restart-after-append` 讓請求端在加完 once、寫 kill 之前 SIGKILL 自己；
`ctl-after-done` 讓 tick／tock 在寫完 kill 的回條、刪請求之前 SIGKILL 自己。
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "tests"))  # tests/：base

import json  # noqa: E402
import subprocess  # noqa: E402
import unittest  # noqa: E402

from base import CONTROL, LIB, SLEEP, CoreCase  # noqa: E402
from _matrix import MatrixCase, alive, env, gen, rec_argv  # noqa: E402
import aos7_control  # noqa: E402
import aos7_task  # noqa: E402
from aos7_fs import read_json, write_json  # noqa: E402


def restart_items(case, node):
    return [i for i in case.tasks(node) or [] if isinstance(i, dict) and (i.get("x") or {}).get("restart_of")]


class TestRestart(CoreCase):
    """〔control〕restart／reload（F39）。"""
    def done(self, node, slot):
        return read_json(os.path.join(self.slot(node, slot), "ctl-done.json"))

    def test_restart_same_slot_new_run_keeps_state(self):
        node = self.mknode("a", [{"name": "w", "argv": ["sh", "-c", 'echo $AOS7_RUN >> "$AOS7_TASK/runs.txt"; sleep 60'],
                                  "from_round": 1}])
        self.tick()
        self.wait_pid(node, "w")
        self.set_tasks(node, [])   # 名字拿掉也照樣 restart（照 birth.json 的定義）
        r = aos7_control.restart(node, "w", why="test")
        self.assertTrue(r["ok"], r)
        once = self.tasks(node)
        self.assertEqual(len(once), 1)
        self.assertEqual((once[0]["mode"], once[0]["slot"], once[0]["x"]["restart_of"]), ("once", "w", "w#1"))
        self.tock()
        out = self.tick()
        self.assertEqual(out["started"], ["w#2"])
        self.assertEqual(self.tasks(node), [])
        b = self.birth(node, "w")
        self.assertEqual((b["run"], b["x"]["restart_of"]), (2, "w#1"))

        def runs():
            with open(os.path.join(self.slot(node, "w"), "runs.txt")) as f:
                return f.read().split() == ["1", "2"]
        self.wait_for(runs)

    def test_restart_reload_takes_new_definition(self):
        node = self.mknode("a", [{"name": "w", "mode": "keep", "argv": SLEEP}])
        self.tick()
        self.wait_pid(node, "w")
        self.set_tasks(node, [{"name": "w", "mode": "keep", "argv": ["sleep", "59"]}])
        r = aos7_control.restart(node, "w", reload=True)
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["diff"], {"argv": {"old": SLEEP, "new": ["sleep", "59"]}})
        self.tock()
        self.tick()
        self.assertEqual(self.birth(node, "w")["argv"], ["sleep", "59"])

    def test_reload_refused_without_kill(self):
        node = self.mknode("a", [{"name": "w", "mode": "keep", "argv": SLEEP}])
        self.tick()
        self.wait_pid(node, "w")
        self.set_tasks(node, [{"name": "w", "mode": "keep", "argv": SLEEP, "max_live": "2"}])
        r = aos7_control.restart(node, "w", reload=True)
        self.assertFalse(r["ok"], r)
        self.assertFalse(os.path.exists(os.path.join(self.slot(node, "w"), "ctl.json")), "reload 不合格還是送了 kill")
        self.tock()
        self.assertEqual(self.view(node, "w", 1).state, aos7_task.LIVE)   # 沒 kill
        self.assertEqual(len(self.tasks(node)), 1)

    def test_restart_receipt_survives_new_run(self):
        """kill 的回條換 run 不清（P2-04）：重起的新 run 起來之後，請求端照樣讀得到 `result.run` 是舊的那次。"""
        node = self.mknode("a", [{"name": "s", "mode": "keep", "argv": SLEEP}])
        self.tick()
        self.wait_pid(node, "s")
        aos7_control.restart(node, "s")
        self.tock()
        self.tick()
        self.assertEqual(self.done(node, "s")["result"]["run"], "s#1")

    def test_restart_carries_dynamic_mounts(self):
        """執行中加掛的掛載，restart 照 birth 抄進新 once 項的 mounts 宣告，新 run 照樣有。"""
        node = self.mknode("a", [{"name": "m", "mode": "keep", "argv": SLEEP}])
        os.makedirs(os.path.join(self.root, "z"))
        self.tick()
        sd = self.slot(node, "m")
        self.wait_pid(node, "m")
        write_json(os.path.join(sd, "mount-req", "z.json"), {"name": "z", "path": "z", "why": "t"})
        self.tock()
        self.tick()
        self.assertTrue(self.birth(node, "m")["mounts"]["z"].get("dyn"))
        self.assertTrue(aos7_control.restart(node, "m")["ok"])
        self.tock()
        self.tick()
        b = self.birth(node, "m")
        self.assertEqual(b["run"], 3)
        self.assertIn("at", b["mounts"]["z"])
        self.assertFalse(os.path.exists(os.path.join(sd, "mount-done")))   # 新 run 清掉

    def test_restart_with_bad_table_does_not_kill(self):
        """G1：要先加 once 項，表壞掉＝加不進去 → ok:false、不寫 kill、表原封不動。"""
        node = self.mknode("a", [{"name": "s", "mode": "keep", "argv": SLEEP}])
        self.tick()
        pid = self.wait_pid(node, "s")["pid"]
        self.tock()
        half = '{"tasks": [{"name": "a", "argv": ["true"]}, {"name": "b"'
        with open(os.path.join(node, ".aos", "tasks.json"), "w") as f:
            f.write(half)
        r = aos7_control.restart(node, "s")
        self.assertIs(r["ok"], False, r)
        self.assertIn("沒 kill", r["msg"])
        self.assertFalse(os.path.exists(os.path.join(self.slot(node, "s"), "ctl.json")))
        self.tick()
        self.assertTrue(alive(pid), "表壞掉還是 kill 了")
        with open(os.path.join(node, ".aos", "tasks.json")) as f:
            self.assertEqual(f.read(), half)


class TestReqId(MatrixCase):
    """〔control〕請求 id（req_id）去重：同槽同 req_id 的 once 不重加；不同 req_id（前綴再像）、不同槽各自生效。
    改寫自 TestCtlId（A3-04、A3-05）。"""
    def once_done_round(self, node, slot):
        self.itick()
        self.wait_ended(node, slot, 1)
        self.itock()

    def full_round(self, node, *slots):
        self.itick()
        for s in slots:
            self.settle(node, s)
        return self.itock()

    def test_same_prefix_req_ids_distinct(self):
        node = self.mknode("a", [{"name": "o", "mode": "once", "argv": rec_argv("o")}])
        self.once_done_round(node, "o")
        for last in "01":
            r = aos7_control.restart(node, "o", req_id="x" * 199 + last)
            self.assertEqual(r["once"], "added", r)
            self.full_round(node, "o")
        self.assertEqual(len(self.ran(node, "o")), 3, "前綴相同的不同 req_id 被當同一件：%r" % self.ran(node, "o"))

    def test_two_slots_same_req_id(self):
        node = self.mknode("a", [{"name": n, "mode": "once", "argv": rec_argv(n)} for n in ("o", "p")])
        self.itick()
        for n in ("o", "p"):
            self.wait_ended(node, n, 1)
        self.itock()
        for n in ("o", "p"):
            self.assertEqual(aos7_control.restart(node, n, req_id="same")["once"], "added")
        self.full_round(node, "o", "p")
        for n in ("o", "p"):
            self.assertEqual(len(self.ran(node, n)), 2, "槽 %s 的 restart 沒生效：%r" % (n, self.ran(node, n)))

    def test_cli_restart_auto_id_and_resend(self):
        """`aos7-ctl task <槽> restart` 每次自動帶新的 req_id，兩次都生效；`--id` 沿用原 id 重送＝once 不重加。"""
        node = self.mknode("a", [{"name": "o", "mode": "once", "argv": rec_argv("o")}])
        self.once_done_round(node, "o")
        ids = []
        for _ in range(2):
            out = self.prog("aos7-ctl", "task", self.slot(node, "o"), "restart")
            ids.append(out["req_id"])
            self.full_round(node, "o")
        self.assertNotEqual(ids[0], ids[1])
        self.assertEqual(len(self.ran(node, "o")), 3, self.ran(node, "o"))
        a = self.prog("aos7-ctl", "task", self.slot(node, "o"), "restart", "--id", "again")
        b = self.prog("aos7-ctl", "task", self.slot(node, "o"), "restart", "--id", "again")
        self.assertEqual((a["once"], b["once"]), ("added", "dup"))
        self.assertEqual(len(restart_items(self, node)), 1)


CRASH_POINTS = ("requester-after-append", "tock-ctl-after-done", "tick-ctl-after-done")


class TestRestartCrash(MatrixCase):
    """〔control〕restart 在交接點被殺：請求端加完 once、寫 kill 之前（用同一個 req_id 重試）、tick／tock 寫完 kill 回條刪請求之前
    （再執行同一份 kill run 也只補收）→ 只重起一次、不雙開。改寫自核心的 restart 交接點（A2-05）。"""

    def assert_one_restart_item(self, node, when):
        items = restart_items(self, node)
        self.assertLessEqual(len(items), 1, "%s：tasks.json 同時有 %d 個 restart 的 once 項：%r" % (when, len(items), items))

    def do_restart(self, node, slot, point):
        """照 point 送 restart，必要時讓對應的一方被殺。"""
        if point == "requester-after-append":
            code = ("import sys; sys.path[:0] = [%r, %r]; import aos7_control; aos7_control.restart(%r, %r, req_id='r1')"
                    % (CONTROL, LIB, node, slot))
            p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=30,
                               env=dict(os.environ, AOS7_TEST_CRASH="restart-after-append"))
            self.assertEqual(p.returncode, -9, "請求端沒在 restart-after-append 被殺：%s" % p.stderr)
            self.assertFalse(os.path.exists(os.path.join(self.slot(node, slot), "ctl.json")), "測試時序不成立：kill 寫了")
            return
        if point.startswith("tick"):
            self.itock()                               # 先關上這回合：kill 要留給下一個 tick 開頭的任務控制執行
        self.assertTrue(aos7_control.restart(node, slot, req_id="r1")["ok"])
        self.crash("aos7-tick" if point.startswith("tick") else "aos7-tock", "ctl-after-done")

    def recover(self, node, slot, point, check):
        """恢復：先把被打斷的回合收掉，再跑幾回合；請求端被殺的情境中途用同一個 req_id 重試一次。"""
        with env(AOS7_INCOMPLETE="tick" if point.startswith("tick") else "tock"):
            self.itock()
        check("恢復 tock 後")
        for r in range(3):
            if r == 1 and point == "requester-after-append":
                self.assertIn(aos7_control.restart(node, slot, req_id="r1")["once"], ("dup", "done"))
            self.itick()
            check("第 %d 次恢復 tick 後" % r)
            self.settle(node, slot)
            self.itock()
            check("第 %d 次恢復 tock 後" % r)

    def _once(self, point):
        """跑完的 once 被 restart：恢復後只重起一次（執行紀錄兩次），表上最後沒有殘項。"""
        node = self.mknode("a", [{"name": "x", "mode": "once", "argv": rec_argv("x")}])
        self.itick()
        self.wait_ended(node, "x", 1)
        self.do_restart(node, "x", point)
        self.assert_one_restart_item(node, "被殺後")
        self.recover(node, "x", point, lambda when: self.assert_one_restart_item(node, when))
        self.assertEqual(len(self.ran(node, "x")), 2, "restart 在 %s 被打斷後執行紀錄：%r（要原本＋一次重起）"
                         % (point, self.ran(node, "x")))
        self.assertEqual(restart_items(self, node), [])

    def _keep(self, point):
        """活著的 keep 被 restart：任何檢查點同槽活程序 ≤ 1；重起只發生一次；新 birth 帶 x.restart_of。"""
        node = self.mknode("a", [{"name": "k", "mode": "keep", "argv": rec_argv("k", keep=True)}])
        self.itick()
        self.wait_pid(node, "k")
        self.itock()
        self.itick()                                   # 第 2 回合開著，k 還活著（run 1）
        self.do_restart(node, "k", point)
        self.assert_le_one(node, "k", "被殺後")
        runs = {1}

        def check(when):
            self.assert_le_one(node, "k", when)
            self.assert_one_restart_item(node, when)
            runs.add(self.birth(node, "k").get("run"))
        self.recover(node, "k", point, check)
        self.wait_for(lambda: len(self.live_procs(node, "k")) == 1, 5, "恢復後槽裡不是剛好一個活程序")
        self.assertEqual(len(runs), 2, "birth 的 run 前進了 %d 次：%r" % (len(runs) - 1, sorted(runs)))
        self.assertEqual(len(self.ran(node, "k")), 2, self.ran(node, "k"))
        self.assertEqual(self.birth(node, "k").get("x", {}).get("restart_of"), "k#1")
        self.assertEqual(restart_items(self, node), [])


gen(TestRestartCrash, "restart_once", [(p, (p,)) for p in CRASH_POINTS], TestRestartCrash._once)
gen(TestRestartCrash, "restart_keep", [(p, (p,)) for p in CRASH_POINTS], TestRestartCrash._keep)


if __name__ == "__main__":
    unittest.main()
