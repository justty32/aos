"""aosp/execute.py：exec_once 走一步。傳輸層／語意層兩頻道、on_fail、暫存器、exclusive、跑到 end。"""
import os
import sys

PROTO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROTO not in sys.path:
    sys.path.insert(0, PROTO)

from aosp import execute, fsutil, series as S, status  # noqa: E402
from .helpers import LandCase, write_source  # noqa: E402

PY = sys.executable


class TestExecOnceBasics(LandCase):
    def test_exec_advances_cursor_and_writes_result(self):
        write_source(self.land, [
            {"name": "s1", "kind": "inst", "inst": {"argv": [PY, "-c", "pass"]}, "then": "end"},
        ])
        rep = execute.exec_once(self.land)
        self.assertEqual(rep["tick"], 0, msg="第一次跑應該是第 0 格，實際 %r" % rep)
        baton = S.load(self.land)
        sr = baton["series"][0]
        self.assertEqual(sr["cursor"], "end", msg="走完一步後游標應該推到 end，實際 %r" % sr["cursor"])
        results_dir = os.path.join(self.land.tick_dir(0), "results")
        files = os.listdir(results_dir)
        self.assertTrue(files, msg=".aos/ticks/0/results/ 應該有東西")
        res = fsutil.read_json(os.path.join(results_dir, files[0]))
        self.assertIn("exit_code", res, msg="執行結果應該有 exit_code 欄位，實際 %r" % res)
        self.assertEqual(res["exit_code"], 0, msg="pass 應該以 exit_code 0 結束，實際 %r" % res)


class TestTransportSpawnError(LandCase):
    def test_nonexistent_program_gives_spawn_error(self):
        write_source(self.land, [
            {"name": "s1", "kind": "inst", "inst": {"argv": ["/no/such/binary-xyz-abc"]}},
        ])
        execute.exec_once(self.land)
        baton = S.load(self.land)
        sr = baton["series"][0]
        self.assertEqual(sr["status"], S.FAILED,
                          msg="argv 指到不存在的程式，串應該失敗，實際 %r" % sr)
        self.assertIsNotNone(sr.get("fail_reason"),
                              msg="失敗的串應該有 fail_reason")
        self.assertEqual(sr["fail_reason"]["reason"], "spawn_error",
                          msg="沒跑起來，reason 應該是 spawn_error，實際 %r" % sr["fail_reason"])
        st = fsutil.read_json(self.land.stopped)
        self.assertIsNotNone(st, msg="沒給 on_fail 時應該寫 .aos/stopped.json")


class TestTransportTimeout(LandCase):
    def test_timeout_ms_marks_timed_out(self):
        write_source(self.land, [
            {"name": "s1", "kind": "inst",
             "inst": {"argv": [PY, "-c", "import time; time.sleep(5)"], "timeout_ms": 80}},
        ])
        execute.exec_once(self.land)
        results_dir = os.path.join(self.land.tick_dir(0), "results")
        files = [f for f in os.listdir(results_dir) if f.endswith(".json")]
        self.assertTrue(files, msg="逾時的指令也該留下結果檔")
        res = fsutil.read_json(os.path.join(results_dir, files[0]))
        self.assertTrue(res.get("timed_out"),
                         msg="timeout_ms 很短、指令又睡很久，timed_out 應該是 true，實際 %r" % res)
        baton = S.load(self.land)
        sr = baton["series"][0]
        self.assertEqual(sr["fail_reason"]["reason"], "timeout",
                          msg="逾時應該讓串失敗，reason 是 timeout，實際 %r" % sr.get("fail_reason"))


class TestSemanticNoExpect(LandCase):
    def test_exit_code_zero_succeeds_without_expect(self):
        write_source(self.land, [
            {"name": "s1", "kind": "inst", "inst": {"argv": [PY, "-c", "pass"]}, "then": "end"},
        ])
        execute.exec_once(self.land)
        sr = S.load(self.land)["series"][0]
        self.assertEqual(sr["status"], S.DONE,
                          msg="沒有 expect、結束碼 0，這步應該成功，串應該做完，實際 %r" % sr)

    def test_nonzero_exit_code_fails_without_expect(self):
        write_source(self.land, [
            {"name": "s1", "kind": "inst", "inst": {"argv": [PY, "-c", "import sys; sys.exit(1)"]}},
        ])
        execute.exec_once(self.land)
        sr = S.load(self.land)["series"][0]
        self.assertEqual(sr["status"], S.FAILED,
                          msg="沒有 expect、結束碼非 0，這步應該失敗，實際 %r" % sr)
        self.assertEqual(sr["fail_reason"]["reason"], "exit_code",
                          msg="沒有 expect 時失敗原因應該是 exit_code，實際 %r" % sr["fail_reason"])


class TestSemanticWithExpect(LandCase):
    def test_expect_file_missing_fails_even_with_exit_zero(self):
        write_source(self.land, [
            {"name": "s1", "kind": "inst",
             "inst": {"argv": [PY, "-c", "pass"]}, "expect": "never-appears.txt"},
        ])
        execute.exec_once(self.land)
        sr = S.load(self.land)["series"][0]
        self.assertEqual(sr["status"], S.FAILED,
                          msg="結束碼 0 但沒有產出 expect 檔，這步應該失敗，實際 %r" % sr)

    def test_expect_file_present_succeeds(self):
        write_source(self.land, [
            {"name": "s1", "kind": "inst",
             "inst": {"argv": [PY, "-c", "open('produced.txt','w').write('ok')"]},
             "expect": "produced.txt", "then": "end"},
        ])
        execute.exec_once(self.land)
        sr = S.load(self.land)["series"][0]
        self.assertEqual(sr["status"], S.DONE,
                          msg="產出了 expect 檔，這步應該成功、串該做完，實際 %r" % sr)

    def test_expect_status_file_present_fails(self):
        expect_path = self.land.resolve("watched.txt")
        status.write_failed(expect_path, "boom", "假裝壞掉")
        write_source(self.land, [
            {"name": "s1", "kind": "inst",
             "inst": {"argv": [PY, "-c", "pass"]}, "expect": "watched.txt"},
        ])
        execute.exec_once(self.land)
        sr = S.load(self.land)["series"][0]
        self.assertEqual(sr["status"], S.FAILED,
                          msg="<expect>.status.json 在，就算指令結束碼 0 也該失敗，實際 %r" % sr)
        self.assertEqual(sr["fail_reason"]["reason"], "boom",
                          msg="失敗原因應該延用狀態檔裡的 reason，實際 %r" % sr["fail_reason"])


class TestOnFail(LandCase):
    def test_on_fail_jumps_instead_of_stopping(self):
        write_source(self.land, [
            {"name": "s1", "kind": "inst",
             "inst": {"argv": [PY, "-c", "import sys; sys.exit(1)"]}, "on_fail": "s2"},
            {"name": "s2", "kind": "inst", "inst": {"argv": [PY, "-c", "pass"]}, "then": "end"},
        ])
        execute.exec_once(self.land)  # tick0: s1 失敗，跳到 s2
        sr = S.load(self.land)["series"][0]
        self.assertEqual(sr["status"], S.RUNNING,
                          msg="有 on_fail 就不該讓串失敗停住，實際 %r" % sr)
        self.assertEqual(sr["cursor"], "s2", msg="失敗後應該跳到 on_fail 指的步，實際 %r" % sr["cursor"])
        execute.exec_once(self.land)  # tick1: 真的跑 s2
        sr = S.load(self.land)["series"][0]
        self.assertEqual(sr["status"], S.DONE, msg="s2 應該順利跑完，串該做完，實際 %r" % sr)

    def test_no_on_fail_stops_series_and_writes_stopped_file(self):
        write_source(self.land, [
            {"name": "s1", "kind": "inst", "inst": {"argv": [PY, "-c", "import sys; sys.exit(1)"]}},
        ])
        execute.exec_once(self.land)
        sr = S.load(self.land)["series"][0]
        self.assertEqual(sr["status"], S.FAILED, msg="沒給 on_fail，串應該失敗，實際 %r" % sr)
        self.assertIsNotNone(sr.get("fail_reason"), msg="失敗的串要有 fail_reason")
        st = fsutil.read_json(self.land.stopped)
        self.assertIsNotNone(st, msg="沒給 on_fail 時應該寫 .aos/stopped.json，卻沒有")


class TestRegisters(LandCase):
    def test_land_and_tick_registers_get_substituted(self):
        out_path = os.path.join(self.land.root, "regs-out.txt")
        write_source(self.land, [
            {"name": "s1", "kind": "inst",
             "inst": {"argv": [PY, "-c",
                                "import sys; open(sys.argv[1],'w').write(sys.argv[2]+'|'+sys.argv[3])",
                                out_path, "${land}", "${tick}"]},
             "then": "end"},
        ])
        execute.exec_once(self.land)
        with open(out_path, "r", encoding="utf-8") as f:
            content = f.read()
        want_land, want_tick = content.split("|")
        self.assertEqual(want_land, self.land.root,
                          msg="${land} 應該替換成這塊地的根，實際 %r" % want_land)
        self.assertEqual(want_tick, "0",
                          msg="${tick} 第一格應該是 0，實際 %r" % want_tick)

    def test_missing_register_fails_series_and_names_it_in_message(self):
        write_source(self.land, [
            {"name": "s1", "kind": "inst", "inst": {"argv": [PY, "-c", "pass", "${nope_reg}"]}},
        ])
        execute.exec_once(self.land)
        sr = S.load(self.land)["series"][0]
        self.assertEqual(sr["status"], S.FAILED,
                          msg="引用不存在的暫存器，串應該失敗，實際 %r" % sr)
        msg = sr["fail_reason"]["message"]
        self.assertIn("nope_reg", msg,
                      msg="錯誤訊息應該指名是哪個暫存器沒有值，實際訊息 %r" % msg)


class TestExclusive(LandCase):
    def test_only_one_series_runs_the_other_holds_to_next_tick(self):
        out1 = os.path.join(self.land.root, "out1.txt")
        out2 = os.path.join(self.land.root, "out2.txt")
        write_source(self.land, [
            {"name": "s1", "kind": "inst",
             "inst": {"argv": [PY, "-c", "import sys; open(sys.argv[1],'w').write('x')", "${outfile}"],
                      "exclusive": ["G"]}, "then": "end"},
        ])
        # 兩條串都從 s1 開始、都搶同一組 exclusive；各自的 outfile 靠 regs 區分
        baton = S.empty()
        sr1 = S.new_series("main", "s1", regs={"outfile": out1})
        sr2 = S.new_series("main", "s1", regs={"outfile": out2})
        baton["series"] = [sr1, sr2]
        S.save(self.land, baton)

        rep = execute.exec_once(self.land)
        baton = S.load(self.land)
        s_a, s_b = baton["series"]
        # 兩條串裡剛好一條前進到 end、一條還停在 s1（游標沒動、也沒被判失敗）
        statuses = sorted([s_a["status"], s_b["status"]])
        cursors = sorted([s_a["cursor"], s_b["cursor"]])
        self.assertEqual(statuses, sorted([S.DONE, S.RUNNING]),
                          msg="同一格只有一條該跑完(done)，另一條該還在跑(running)，實際 %r" % statuses)
        self.assertEqual(cursors, sorted(["end", "s1"]),
                          msg="沒搶到的那條游標不該動，還停在 s1，實際 %r" % cursors)
        for s in (s_a, s_b):
            self.assertNotEqual(s["status"], S.FAILED,
                                 msg="搶不到 exclusive 只是延到下一格，不該被判失敗：%r" % s)

        rep2 = execute.exec_once(self.land)
        baton2 = S.load(self.land)
        self.assertTrue(all(s["status"] == S.DONE for s in baton2["series"]),
                        msg="第二格之後兩條串都該跑完了，實際 %r" % baton2["series"])


class TestFrameCleanup(LandCase):
    def test_frame_dir_removed_when_series_reaches_end(self):
        write_source(self.land, [
            {"name": "s1", "kind": "inst", "inst": {"argv": [PY, "-c", "pass"]}, "then": "end"},
        ])
        execute.exec_once(self.land)
        sr = S.load(self.land)["series"][0]
        self.assertEqual(sr["status"], S.DONE, msg="這步跑完該直接 done，實際 %r" % sr)
        frame_dir = self.land.frame(sr["id"])
        self.assertFalse(os.path.isdir(frame_dir),
                          msg="串跑到 end 之後，堆疊框目錄該被刪掉：%s" % frame_dir)
