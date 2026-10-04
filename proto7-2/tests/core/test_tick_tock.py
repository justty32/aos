"""tick／tock／任務的測試（不起 daemon）：槽與 run、mode、max_live、once、刪槽、核心只留上一次、tasks.json 驗證、inst。"""
import os, sys  # noqa: E401
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # tests/：base、_matrix
import os
import time
import unittest

from base import LIB, SLEEP, CoreCase
import aos7_task
from aos7_fs import read_json, write_json


class TestSlotsAndRuns(CoreCase):
    """〔core〕"""
    def test_tick_starts_in_slot_and_does_not_wait(self):
        node = self.mknode("a", [{"name": "s", "argv": SLEEP}])
        t0 = time.monotonic()
        out = self.tick()
        self.assertLess(time.monotonic() - t0, 5)
        self.assertEqual(out["round"], 1)
        self.assertEqual(out["started"], ["s#1"])
        self.assertTrue(out["tasks_rev"])
        b = self.birth(node, "s")
        self.assertEqual((b["name"], b["slot"], b["run"], b["round"]), ("s", "s", 1, 1))
        self.assertIsInstance(b["runner"]["pid"], int)
        pid = self.wait_pid(node, "s")
        self.assertEqual(pid["run"], 1)
        self.assertEqual(self.round_json(node)["tasks_rev"], out["tasks_rev"])

    def test_task_env_and_tock_json(self):
        node = self.mknode("a", [{"name": "w", "mode": "keep", "argv": ["python3", "waiter.py", "2"]}])
        self.tick()
        self.wait_pid(node, "w")
        self.tock()
        t = read_json(os.path.join(self.slot(node, "w"), "tock.json"))
        self.assertEqual((t["run"], t["round"]), (1, 1))
        self.round_trip()
        self.wait_ended(node, "w", 1)
        seen = [x["round"] for x in __import__("aos7_taskside").read_jsonl(os.path.join(self.slot(node, "w"), "seen.jsonl"))]
        self.assertEqual(seen, [1, 2])
        lr = self.tock() if self.round_json(node).get("open") else self.round_trip()
        self.assertIn({"run": "w#1", "code": 0}, self.last_round(node)["ended"] + lr.get("ended", []))

    def test_run_is_round_and_increases(self):
        node = self.mknode("a", [{"name": "j", "argv": ["true"]}])
        runs = []
        for _ in range(3):
            self.tick()
            runs.append(self.birth(node, "j")["run"])
            self.wait_ended(node, "j", runs[-1])
            self.tock()
        self.assertEqual(runs, [1, 2, 3])
        # 回合數被人手倒退：run 不倒退（上一個 run＋1）
        write_json(os.path.join(node, ".aos", "round.json"), {"round": 0, "open": False})
        self.tick()
        self.assertEqual(self.birth(node, "j")["run"], 4)

    def test_infra_files_cleared_task_files_kept(self):
        node = self.mknode("a", [{"name": "j", "argv": ["sh", "-c", "echo run $AOS7_RUN; echo x > mine.txt"]}])
        self.tick()
        self.wait_ended(node, "j", 1)
        sd = self.slot(node, "j")
        with open(os.path.join(sd, "state.json"), "w") as f:
            f.write('{"keep": 1}')
        write_json(os.path.join(sd, "tock.json"), {"run": 1, "round": 1})
        self.tock()
        self.tick()
        self.wait_ended(node, "j", 2)
        with open(os.path.join(sd, "out.log")) as f:
            self.assertEqual(f.read().strip(), "run 2")   # out.log 是這次 run 的
        self.assertEqual(read_json(os.path.join(sd, "state.json")), {"keep": 1})   # 任務自己的檔留著（W6）
        self.assertFalse(os.path.exists(os.path.join(sd, "tock.json")))

    def test_stale_infra_of_other_run_ignored(self):
        node = self.mknode("a", [{"name": "s", "mode": "keep", "argv": SLEEP}])
        self.tick()
        self.wait_pid(node, "s")
        write_json(os.path.join(self.slot(node, "s"), "exit.json"), {"run": 99, "code": 0})   # 別的 run 的
        self.assertEqual(self.view(node, "s", 1).state, aos7_task.LIVE)

    def test_bad_names_skipped_not_mangled(self):
        node = self.mknode("a", [{"name": "a.b", "argv": ["true"]}, {"name": "x/y", "argv": ["true"]},
                                 {"argv": ["true"]}, {"name": "ok", "argv": ["true"]}])
        out = self.tick()
        self.assertEqual(out["started"], ["ok#1"])
        errs = self.round_json(node)["tasks_error"]
        self.assertEqual(len(errs), 3, errs)
        self.assertEqual(sorted(os.listdir(os.path.join(node, ".aos", "tasks"))), ["ok"])

    def test_bad_field_types_skip_only_that_item(self):
        node = self.mknode("a", [{"name": "m", "mode": "sometimes", "argv": ["true"]},
                                 {"name": "l", "max_live": 0, "argv": ["true"]},
                                 {"name": "e", "enabled": "no", "argv": ["true"]},
                                 {"name": "f", "from_round": "1", "argv": ["true"]},
                                 {"name": "z", "argv": []},
                                 {"name": "good", "argv": ["true"]}])
        self.assertEqual(self.tick()["started"], ["good#1"])
        self.assertEqual(len(self.round_json(node)["tasks_error"]), 5)

    def test_unreadable_tasks_json_is_empty_table(self):
        node = self.mknode("a")
        with open(os.path.join(node, ".aos", "tasks.json"), "w") as f:
            f.write("{oops")
        self.assertEqual(self.tick()["started"], [])
        self.assertTrue(self.round_json(node)["tasks_error"])
        os.remove(os.path.join(node, ".aos", "tasks.json"))
        os.mkfifo(os.path.join(node, ".aos", "tasks.json"))   # FIFO 當不存在，不卡
        self.tock()
        self.assertEqual(self.tick()["started"], [])

    def test_timeline_json_optional(self):
        node = self.mknode("a", [{"name": "j", "argv": ["true"]}], timeline=False)
        self.assertEqual(self.tick()["started"], ["j#1"])
        self.assertFalse(os.path.exists(os.path.join(node, ".aos", "timeline.json")))


class TestModes(CoreCase):
    """〔core〕"""
    def test_each_skips_while_previous_still_running(self):
        node = self.mknode("a", [{"name": "e", "argv": SLEEP}])
        self.assertEqual(self.tick()["started"], ["e#1"])
        self.tock()
        out = self.tick()
        self.assertEqual(out["started"], [])
        lr = self.tock()
        self.assertEqual(lr["skipped"], [{"name": "e", "why": "busy"}])
        self.assertEqual(lr["alive"], ["e#1"])

    def test_each_max_live_slots(self):
        node = self.mknode("a", [{"name": "e", "argv": SLEEP, "max_live": 3}])
        started = [self.round_trip() and self.round_json(node)["started"] for _ in range(4)]
        self.assertEqual(started, [["e#1"], ["e.1#2"], ["e.2#3"], []])
        self.assertEqual(self.last_round(node)["skipped"], [{"name": "e", "why": "busy"}])
        self.assertEqual(sorted(os.listdir(os.path.join(node, ".aos", "tasks"))), ["e", "e.1", "e.2"])

    def test_keep_fills_all_slots_and_restarts_ended(self):
        node = self.mknode("a", [{"name": "k", "mode": "keep", "argv": ["sh", "-c", "sleep 0.2"], "max_live": 2}])
        self.assertEqual(self.tick()["started"], ["k#1", "k.1#1"])
        self.wait_ended(node, "k")
        self.wait_ended(node, "k.1")
        lr = self.tock()
        self.assertEqual(sorted(e["run"] for e in lr["ended"]), ["k#1", "k.1#1"])
        self.assertEqual(self.tick()["started"], ["k#2", "k.1#2"])

    def test_keep_does_not_double_start(self):
        node = self.mknode("a", [{"name": "k", "mode": "keep", "argv": SLEEP}])
        self.tick()
        for _ in range(3):
            self.tock()
            self.assertEqual(self.tick()["started"], [])

    def test_from_round_and_enabled(self):
        node = self.mknode("a", [{"name": "late", "argv": ["true"], "from_round": 3},
                                 {"name": "off", "mode": "keep", "argv": ["true"], "enabled": False}])
        got = []
        for _ in range(3):
            got.append(self.tick()["started"])
            self.tock()
        self.assertEqual(got, [[], [], ["late#3"]])

    def test_disabled_keeps_slot_and_state(self):
        node = self.mknode("a", [{"name": "k", "mode": "keep", "argv": ["sh", "-c", "echo 1 > $AOS7_TASK/state.json"]}])
        self.tick()
        self.wait_ended(node, "k", 1)
        self.tock()
        self.set_tasks(node, [{"name": "k", "mode": "keep", "argv": ["true"], "enabled": False}])
        for _ in range(3):
            self.round_trip()
        self.assertTrue(os.path.exists(os.path.join(self.slot(node, "k"), "state.json")))


class TestOnce(CoreCase):
    """〔core〕"""
    def test_once_runs_once_and_item_removed(self):
        node = self.mknode("a", [{"name": "fix", "mode": "once", "argv": ["true"]},
                                 {"name": "k", "mode": "keep", "argv": SLEEP}])
        out = self.tick()
        self.assertEqual(out["started"], ["fix#1", "k#1"])
        self.assertEqual([t["name"] for t in self.tasks(node)], ["k"])
        self.wait_ended(node, "fix", 1)
        self.tock()
        self.assertEqual(self.tick()["started"], [])

    def test_once_from_round(self):
        node = self.mknode("a", [{"name": "fix", "mode": "once", "argv": ["true"], "from_round": 2}])
        self.assertEqual(self.tick()["started"], [])
        self.assertEqual(len(self.tasks(node)), 1)
        self.tock()
        self.assertEqual(self.tick()["started"], ["fix#2"])
        self.assertEqual(self.tasks(node), [])

    def test_batch_once_same_round(self):
        node = self.mknode("a")
        self.prog("aos7-ctl", "add", node, '{"name":"b1","mode":"once","argv":["true"]}',
                  '{"name":"b2","mode":"once","argv":["true"]}')
        self.assertEqual(self.tick()["started"], ["b1#1", "b2#1"])
        self.assertEqual(self.tasks(node), [])

    def test_once_in_busy_slot_waits(self):
        node = self.mknode("a", [{"name": "x", "mode": "keep", "argv": SLEEP}])
        self.tick()
        self.wait_pid(node, "x")
        self.tock()
        self.set_tasks(node, [{"name": "x", "mode": "once", "argv": ["true"], "slot": "x"}])
        out = self.tick()
        self.assertEqual(out["started"], [])
        self.assertEqual(len(self.tasks(node)), 1)   # 還在，等槽空
        self.assertEqual(self.tock()["skipped"], [{"name": "x", "slot": "x", "why": "busy"}])


class TestSlotRemoval(CoreCase):
    """〔core〕"""
    def test_removed_name_slot_deleted_one_round_after_report(self):
        node = self.mknode("a", [{"name": "j", "argv": ["sh", "-c", "echo hi > mine.txt"]}])
        self.tick()
        self.wait_ended(node, "j", 1)
        self.set_tasks(node, [])
        lr = self.tock()   # 第 1 回合：報結束
        self.assertEqual(lr["ended"], [{"run": "j#1", "code": 0}])
        self.assertEqual(self.exit_of(node, "j")["seen_round"], 1)
        self.assertTrue(os.path.isdir(self.slot(node, "j")))
        self.round_trip()   # 第 2 回合：報過了 → 刪
        self.assertFalse(os.path.exists(self.slot(node, "j")))

    def test_once_slot_deleted_after_report(self):
        node = self.mknode("a", [{"name": "o", "mode": "once", "argv": ["true"]}])
        self.tick()
        self.wait_ended(node, "o", 1)
        self.assertEqual(self.tock()["ended"], [{"run": "o#1", "code": 0}])
        self.assertTrue(os.path.isdir(self.slot(node, "o")))
        self.round_trip()
        self.assertFalse(os.path.exists(self.slot(node, "o")))

    def test_live_slot_of_removed_name_kept(self):
        node = self.mknode("a", [{"name": "s", "argv": SLEEP}])
        self.tick()
        self.set_tasks(node, [])
        for _ in range(3):
            self.tock()
            self.tick()
        self.assertTrue(os.path.isdir(self.slot(node, "s")))

    def test_shrunk_max_live_slot_deleted(self):
        node = self.mknode("a", [{"name": "e", "argv": ["true"], "max_live": 2}])
        self.tick()
        self.wait_ended(node, "e", 1)
        self.tock()
        self.tick()   # e 已結束：each 重用第一個空槽 e
        self.wait_ended(node, "e", 2)
        write_json(os.path.join(self.slot(node, "e.1"), "birth.json"), {"name": "e", "slot": "e.1", "run": 1, "round": 1})
        write_json(os.path.join(self.slot(node, "e.1"), "exit.json"), {"run": 1, "code": 0})
        self.set_tasks(node, [{"name": "e", "argv": ["true"], "max_live": 1}])
        self.tock()
        self.round_trip()
        self.assertFalse(os.path.exists(self.slot(node, "e.1")))
        self.assertTrue(os.path.exists(self.slot(node, "e")))

    def test_unreadable_table_deletes_nothing(self):
        node = self.mknode("a", [{"name": "j", "argv": ["true"]}])
        self.tick()
        self.wait_ended(node, "j", 1)
        with open(os.path.join(node, ".aos", "tasks.json"), "w") as f:
            f.write("not json")
        for _ in range(3):
            self.tock()
            self.tick()
        self.assertTrue(os.path.isdir(self.slot(node, "j")))


class TestOnlyLastKept(CoreCase):
    """〔core〕"""
    def count_files(self, node):
        n = 0
        for d, dirs, files in os.walk(os.path.join(node, ".aos")):
            n += len(files) + len(dirs)
        return n

    def test_200_rounds_file_count_constant(self):
        """槽重用：同名跑 200 回合，`.aos` 底下的檔案數維持常數（核心只留上一次）。"""
        node = self.mknode("a", [{"name": "j", "argv": ["true"]}, {"name": "k", "mode": "keep", "argv": SLEEP},
                                 {"name": "e", "argv": ["true"], "max_live": 2}])
        counts = {}
        for r in range(1, 201):
            out = self.itick()
            for rid in out["started"]:
                slot, _, run = rid.partition("#")
                if slot != "k":
                    self.wait_ended(node, slot, int(run))
            self.itock()
            if r in (10, 100, 200):
                counts[r] = self.count_files(node)
        self.assertEqual(self.round_json(node)["round"], 200)
        self.assertEqual(counts[10], counts[100], counts)
        self.assertEqual(counts[100], counts[200], counts)
        self.assertEqual(sorted(os.listdir(os.path.join(node, ".aos", "tasks"))), ["e", "j", "k"])
        lr = self.last_round(node)
        self.assertEqual(lr["round"], 200)
        self.assertEqual(sorted(e["run"] for e in lr["ended"]), ["e#200", "j#200"])

    def test_ended_after_tock_then_reused_still_reported(self):
        """上一個 run 在 tock 之後才結束、下一個 tick 就重用槽：清掉前記進 round.json，tock 照樣報（P2-03）。"""
        node = self.mknode("a", [{"name": "k", "mode": "keep", "argv": ["sh", "-c", "sleep 0.3"]}])
        self.tick()
        self.tock()          # 還活著
        self.wait_ended(node, "k", 1)
        out = self.tick()    # 重用槽，k#1 的結束還沒報過
        self.assertEqual(out["started"], ["k#2"])
        lr = self.tock()
        self.assertIn({"run": "k#1", "code": 0}, lr["ended"])


class TestInst(CoreCase):
    """〔core〕"""
    def test_inst_task(self):
        node = self.mknode("a", [{"name": "i", "inst": "i.inst.json"}])
        write_json(os.path.join(node, "i.inst.json"),
                   {"argv": ["sh", "-c", "echo $AOS7_TID#$AOS7_RUN > inst-out.txt; echo hi"], "stdout": {"$opt": "inherit"}})
        self.tick()
        ex = self.wait_ended(node, "i", 1)
        with open(os.path.join(self.slot(node, "i"), "out.log")) as f:
            log = f.read()
        self.assertEqual(ex["code"], 0, log)
        self.assertEqual(log.strip(), "hi")
        with open(os.path.join(node, "inst-out.txt")) as f:
            self.assertEqual(f.read().strip(), "i#1")

    def test_argv_and_inst_exclusive(self):
        node = self.mknode("a", [{"name": "i", "inst": "x", "argv": ["true"]}])
        self.assertEqual(self.tick()["started"], [])


class TestGone(CoreCase):
    """〔core〕"""
    def test_gone_node_not_recreated(self):
        node = self.mknode("a")
        os.rename(node, node + "-moved")
        self.assertTrue(self.tick().get("gone"))
        self.assertFalse(os.path.exists(node))

    def test_unregistered_but_existing_dir_works_by_hand(self):
        node = self.mknode("b", [{"name": "j", "argv": ["true"]}])
        self.assertEqual(self.tick("b")["started"], ["j#1"])


if __name__ == "__main__":
    unittest.main()
