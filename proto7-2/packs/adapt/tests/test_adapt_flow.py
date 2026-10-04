"""〔adapt〕真 daemon 的驗收矩陣（loop6 藍圖 §3.3）：同一個空間根兩個登記 node——`src`（發布者 sensor.py）、`dst`
（adapt 任務＋消費者）；dst 的 adapt 項掛 `{"src": "src/out", "srcclock": "src/.aos"}`。

流速三組（src／dst interval 20／200、200／20、50／50）、來源 pause（stall null／3）、daemon kill -9 重開、來源 node 重建、
半寫／壞檔／EACCES／換成資料夾、dst pause、adapt 被殺、門檻邊界＋fan 消費者、step `num` 條件、300 回合檔數。
任務的環境沒有 AOS7_TEST_*（aos7-run 拿掉），所以故障用真的檔案狀態造（截斷、chmod 000、換成資料夾），不用注入鉤子。
暫存器每個 dst 回合覆寫一次；`collect` 以 5ms 輪詢收下每個 `my_round` 的版本，逐回合斷言。
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)
TOP = os.path.dirname(os.path.dirname(PACK))
sys.path.insert(0, os.path.join(TOP, "tests"))
sys.path.insert(0, PACK)

from base import DaemonCase  # noqa: E402
from _matrix import alive  # noqa: E402
from aos7_fs import read_json, write_json  # noqa: E402

PY = sys.executable
ADAPT = os.path.join(PACK, "bin", "aos7-adapt")
EX = os.path.join(PACK, "examples", "temp")
STEP = os.path.join(os.path.dirname(PACK), "step", "bin", "aos7-step")
MOUNTS = {"src": "src/out", "srcclock": "src/.aos"}


class AdaptCase(DaemonCase):
    """共用：兩個 node、宣告、讀暫存器、逐回合收集、pause／resume。"""

    def setup_pair(self, src_ms, dst_ms, sensor=True, decl=None, dst_tasks=(), feed=None):
        self.src = self.mknode("src", tasks=[{"name": "sensor", "mode": "keep", "argv": [PY, os.path.join(EX, "sensor.py")]}]
                               if sensor else [], interval_ms=src_ms)
        if feed is not None:
            self.feed(feed)
        self.dst = self.mknode("dst", tasks=[{"name": "adapt-temp", "mode": "keep", "argv": [PY, ADAPT, "run", "adapt/temp.json"],
                                              "mounts": MOUNTS}] + list(dst_tasks), interval_ms=dst_ms)
        with open(os.path.join(EX, "temp.json")) as f:
            d = json.load(f)
        d.update(decl or {})
        write_json(os.path.join(self.dst, "adapt", "temp.json"), d)
        self.daemon = self.start_daemon(register=["src", "dst"])

    def feed(self, t_dc):
        write_json(os.path.join(self.src, "feed.json"), {"t_dc": t_dc})

    def reg(self):
        return read_json(os.path.join(self.dst, "in", "temp.json")) or {}

    def frame(self):
        return read_json(os.path.join(self.slot(self.dst, "adapt-temp"), "state.json")) or {}

    def src_clock(self):
        r = self.round_json(self.src)
        return r["round"] - (1 if r.get("open") else 0) if isinstance(r.get("round"), int) else None

    def collect(self, until, timeout=20, msg="沒等到", fresh=False):
        """以 5ms 輪詢暫存器，收下每個新的 my_round 版本，直到 until(版本清單) 成立；回清單。
        fresh＝不收現在這一份（只收之後的回合）。"""
        out, end = [], time.monotonic() + timeout
        seen = self.reg().get("my_round", -1) if fresh else -1
        while time.monotonic() < end:
            r = self.reg()
            if isinstance(r.get("my_round"), int) and r["my_round"] > seen:
                seen = r["my_round"]
                out.append(r)
                if until(out):
                    return out
            time.sleep(0.005)
        self.fail("%s：最後幾份 %s" % (msg, json.dumps(out[-3:], ensure_ascii=False)[:1500]))

    def wait_ok(self, pred=lambda r: True, timeout=20):
        return self.collect(lambda o: o[-1]["state"] == "ok" and pred(o[-1]), timeout, "暫存器沒到 ok")[-1]

    def rounds(self, n, timeout=20):
        """之後的 n 個 dst 回合（每個 my_round 一份，不含現在這份）。"""
        return self.collect(lambda o: len(o) >= n, timeout, "沒收滿 %d 回合" % n, fresh=True)

    def pause(self, nid):
        self.prog("aos7-ctl", "daemon", self.root, "pause", nid, "--owner", "t")
        self.wait_for(lambda: self.nstat(nid).get("phase") == "paused", 10, "%s 沒 pause" % nid)

    def resume(self, nid):
        self.prog("aos7-ctl", "daemon", self.root, "resume", nid, "--owner", "t")

    def kill_slot(self, node, s):
        """SIGKILL 槽裡任務的程序群組，等它確定不在；回被殺的 run（node 沒 pause 時 keep 下一回合就重起，不等 exit.json）。"""
        pj = self.wait_pid(node, s)
        os.killpg(pj["pgid"], signal.SIGKILL)
        self.wait_for(lambda: not alive(pj["pid"]), 5, "%s 收不掉" % s)
        return pj["run"]

    def write_src(self, seq, t_dc=801, rnd=None):
        """沒有 sensor 時由測試當發布者（原子寫）。rnd 預設取來源鐘。"""
        write_json(os.path.join(self.src, "out", "temp.json"),
                   {"v": 1, "seq": seq, "round": self.src_clock() if rnd is None else rnd, "value": {"t_dc": t_dc},
                    "at": "t"})


# ---------------------------------------------------------------- 流速三組

class TestFlow(AdaptCase):
    """〔adapt〕流速矩陣：來源快只是漏取樣、來源慢不是錯、相同速率照常。"""

    def check_all_ok(self, regs, max_age_seen=1):
        for r in regs:
            self.assertEqual((r["state"], r["why"]), ("ok", None), r)
            self.assertLessEqual(r["age_src_rounds"], max_age_seen, r)
            self.assertEqual(r["value"]["c"], round(r["trace"][0]["x"] * 0.1, 1))

    def test_fast_source(self):
        """src 20ms／dst 200ms：每個 dst 回合 src_round 前進 >1、skipped 累加、state ok、age ≤ 1；不報錯、不補。"""
        self.setup_pair(20, 200)
        self.wait_ok()
        regs = self.rounds(6)
        self.check_all_ok(regs)
        steps = [b["basis"]["src_round"] - a["basis"]["src_round"] for a, b in zip(regs, regs[1:])]
        self.assertTrue(all(s > 1 for s in steps), steps)
        self.assertTrue(all(r["src_state"] == "advancing" for r in regs), [r["src_state"] for r in regs])
        self.assertGreater(regs[-1]["skipped"], regs[0]["skipped"])
        self.assertEqual(regs[-1]["skipped"] - regs[0]["skipped"],
                         regs[-1]["basis"]["seq"] - regs[0]["basis"]["seq"] - (len(regs) - 1))

    def test_slow_source(self):
        """src 200ms／dst 20ms：連續多個 dst 回合同一份依據、age ≤ 1、不翻 unknown（慢不是壞）。"""
        self.setup_pair(200, 20)
        self.wait_ok()
        regs = self.rounds(25, timeout=30)
        self.check_all_ok(regs)
        run, best = 1, 1
        for a, b in zip(regs, regs[1:]):
            run = run + 1 if a["basis"]["sha"] == b["basis"]["sha"] else 1
            best = max(best, run)
        self.assertGreaterEqual(best, 3, [r["basis"]["seq"] for r in regs])
        self.assertIn("stalled", {r["src_state"] for r in regs})          # 只報，不翻
        self.assertEqual(regs[-1]["skipped"], regs[0]["skipped"])

    def test_same_rate(self):
        """src、dst 都 50ms：照常 ok、age ≤ 1。"""
        self.setup_pair(50, 50)
        self.wait_ok()
        self.check_all_ok(self.rounds(10))


# ---------------------------------------------------------------- 來源 pause／kill -9／重建

class TestSource(AdaptCase):
    """〔adapt〕來源出事：pause（只報 stalled／stall 選項翻 unknown）、daemon kill -9 回合接續、node 重建＝reset。"""

    def test_pause_stall_null(self):
        """來源 pause：來源鐘凍結、age 不長、state 維持 ok、src_state stalled；resume 後 ≤ 2 回合回 advancing。"""
        self.setup_pair(20, 100)
        self.wait_ok()
        self.pause("src")
        regs = self.rounds(8)[2:]                  # 前兩份可能還是 pause 生效那一刻的
        ages = {r["age_src_rounds"] for r in regs}
        self.assertEqual(len({r["basis"]["sha"] for r in regs}), 1)
        self.assertTrue(all(r["state"] == "ok" and r["src_state"] == "stalled" for r in regs), regs[-1])
        self.assertLessEqual(max(ages), 1)
        self.assertEqual(len(ages), 1, ages)
        self.resume("src")
        after = self.collect(lambda o: o[-1]["src_state"] == "advancing", 10, "resume 後沒前進")
        self.assertLessEqual(len(after), 3, [r["src_state"] for r in after])
        self.assertEqual(after[-1]["state"], "ok")

    def test_pause_stall_3(self):
        """stall: 3：來源 pause 後第 4 個 dst 回合翻 unknown（stalled）、last 還在；resume 後 ≤ 2 回合回 ok。"""
        self.setup_pair(20, 150, decl={"stall": 3})
        self.wait_ok()
        self.pause("src")
        regs = self.collect(lambda o: o[-1]["state"] == "unknown" and o[-1]["stall_rounds"] >= 5, 15, "沒翻 unknown")
        for r in regs:
            want = "ok" if r["stall_rounds"] <= 3 else "unknown"
            self.assertEqual(r["state"], want, r)
        self.assertTrue(any(r["stall_rounds"] == 4 and r["why"] == "stalled" for r in regs))
        self.assertIsNotNone(regs[-1]["last"])
        self.assertEqual(regs[-1]["value"], None)
        self.resume("src")
        after = self.collect(lambda o: o[-1]["state"] == "ok", 10, "resume 後沒回 ok")
        self.assertLessEqual(len(after), 3, [(r["state"], r["src_state"]) for r in after])
        self.assertEqual(after[-1]["src_state"], "advancing")

    def test_daemon_kill9_restart(self):
        """daemon（含進行中的 tick／tock）kill -9 再起：回合接續（核心 §3）、無 reset，最後回 ok 且依據是新回合。"""
        self.setup_pair(50, 100)
        before = self.wait_ok()
        fr0 = self.frame()
        os.killpg(self.daemon.pid, signal.SIGKILL)
        self.daemon.wait(5)
        time.sleep(0.3)
        self.start_daemon()
        regs = self.collect(lambda o: o[-1]["state"] == "ok"
                            and o[-1]["basis"]["src_round"] > before["basis"]["src_round"] + 3, 20, "重開後沒接上")
        self.assertNotIn("reset", {r["src_state"] for r in regs})
        self.assertTrue(all(r["why"] != "void_basis" for r in regs))
        self.assertGreaterEqual(regs[0]["my_round"], before["my_round"])
        self.assertEqual(self.frame()["since"], fr0["since"])

    def test_source_rebuilt(self):
        """來源 node 重建（回合從 1 起、舊檔還在）：src_state reset、state unknown、舊依據作廢；新值到才 ok，basis 是新鐘。"""
        self.setup_pair(50, 100, decl={"max_age": None})
        self.wait_ok(lambda r: r["basis"]["src_round"] >= 10, timeout=30)
        self.pause("src")
        self.kill_slot(self.src, "sensor")
        old = self.rounds(3)[-1]                    # 來源停住、發布者已死之後的最後一份依據
        self.assertEqual(old["state"], "ok")
        shutil.rmtree(os.path.join(self.src, ".aos"))
        self.src = self.mknode("src", interval_ms=50)          # 先不放發布者：舊鐘留下的檔還在
        self.resume("src")
        regs = self.collect(lambda o: o[-1]["src_state"] == "reset" and o[-1]["why"] == "void_basis"
                            and len(o) >= 3, 20, "沒認出 reset")
        resets = [r for r in regs if r["src_state"] == "reset"]
        self.assertTrue(all(r["state"] == "unknown" and r["value"] is None for r in resets), resets[-1])
        self.assertTrue(resets[-1]["last"]["void"])
        self.assertEqual(resets[-1]["basis"]["sha"], old["basis"]["sha"])          # 讀到的還是舊檔，但作廢
        self.set_tasks(self.src, [{"name": "sensor", "mode": "keep", "argv": [PY, os.path.join(EX, "sensor.py")]}])
        regs = self.collect(lambda o: o[-1]["state"] == "ok", 20, "新值到了沒回 ok")
        self.assertTrue(all(r["state"] == "unknown" for r in regs[:-1]))
        new = regs[-1]
        self.assertEqual(new["src_state"], "advancing")
        self.assertLess(new["basis"]["src_round"], old["basis"]["src_round"])
        self.assertLess(new["basis"]["seq"], old["basis"]["seq"])    # 槽跟著重建，發布者從 1 重數
        self.assertNotIn("void", new["last"])


# ---------------------------------------------------------------- 壞檔、dst pause、任務被殺

class TestFaults(AdaptCase):
    """〔adapt〕半寫／壞檔／EACCES／資料夾：耐性撐住再翻 unknown、last 留著、修好下一回合 ok；dst pause；adapt 被殺接回。"""

    def bad_phase(self, make_bad, fix, why):
        """壞掉之後：第 1～2 回合（patience 2）state 仍 ok、why 記錄；第 3 回合 unknown、last 留著；修好下一回合 ok。"""
        good = self.wait_ok()
        make_bad()
        regs = self.collect(lambda o: o[-1]["state"] == "unknown", 10, "沒翻 unknown")
        bad = [r for r in regs if r["why"] == why]
        self.assertEqual([(r["state"], r["held"]) for r in bad], [("ok", 1), ("ok", 2), ("unknown", 0)], regs)
        self.assertTrue(all(r["basis"] == good["basis"] for r in bad[:2]))
        self.assertEqual(bad[-1]["last"]["basis"], good["basis"])
        fix()
        after = self.collect(lambda o: o[-1]["state"] == "ok", 10, "修好後沒回 ok")
        self.assertLessEqual(len(after), 2, after)

    def test_half_written_unreadable_dir(self):
        """截斷（非原子寫）、缺 round、真 EACCES、換成資料夾、選不到欄；旁邊的半寫暫存檔不影響。宣告被改＝unknown，改回恢復。"""
        self.setup_pair(50, 100, sensor=False, decl={"max_age": None})
        path = os.path.join(self.src, "out", "temp.json")
        self.wait_for(lambda: self.src_clock(), 10, "來源沒開回合")
        self.write_src(1)
        seq = [1]

        def fix():
            if os.path.isdir(path):
                os.rmdir(path)
            if os.path.exists(path):
                os.chmod(path, 0o644)
            seq[0] += 1
            self.write_src(seq[0])

        def truncate():
            with open(path, "w") as f:
                f.write('{"v": 1, "seq": 9, "rou')
        self.bad_phase(truncate, fix, "src_bad")
        self.bad_phase(lambda: write_json(path, {"v": 1, "seq": 99, "value": {"t_dc": 801}}), fix, "src_bad")
        self.bad_phase(lambda: os.chmod(path, 0), fix, "src_unreadable")
        self.bad_phase(lambda: (os.unlink(path), os.mkdir(path)), fix, "src_unreadable")
        self.bad_phase(lambda: write_json(path, {"v": 1, "seq": 98, "round": self.src_clock(), "value": {"x": 1}}), fix,
                       "select_missing")
        # 原子寫留下的半寫暫存檔（寫者被殺）：讀的人只讀正式檔，照常 ok
        with open(os.path.join(self.src, "out", ".temp.json.tmp.999999"), "w") as f:
            f.write('{"v": 1, "se')
        self.assertTrue(all(r["state"] == "ok" for r in self.rounds(3)))
        # 鏈宣告工作中被改（誤用）：unknown（chain_changed）不崩；改回原宣告就恢復
        dpath = os.path.join(self.dst, "adapt", "temp.json")
        d = read_json(dpath)
        write_json(dpath, dict(d, patience=5))
        r = self.collect(lambda o: o[-1]["why"] == "chain_changed", 10, "沒認出鏈被改")[-1]
        self.assertEqual((r["state"], r["value"]), ("unknown", None))
        self.assertIsNotNone(r["last"])
        write_json(dpath, d)
        self.wait_ok()
        # 框架讀不到（槽 state.json 換成資料夾，誤用）：unknown（frame_bad）、last 從暫存器抄；人刪掉之後重建框架、回 ok
        st = os.path.join(self.slot(self.dst, "adapt-temp"), "state.json")
        os.unlink(st)
        os.mkdir(st)
        r = self.collect(lambda o: o[-1]["why"] == "frame_bad", 10, "沒報 frame_bad")[-1]
        self.assertEqual((r["state"], r["last"]["value"]["c"]), ("unknown", 80.1))
        os.rmdir(st)
        self.wait_ok()
        # 來源檔確定不存在＝absent
        os.unlink(path)
        r = self.collect(lambda o: o[-1]["state"] == "absent", 10, "沒報 absent")[-1]
        self.assertEqual((r["why"], r["value"]), ("src_missing", None))

    def test_dst_pause(self):
        """dst pause：沒回合 → 暫存器不動（內容與 mtime）、耐性不走；resume 後照常 ok。"""
        self.setup_pair(50, 100)
        self.wait_ok()
        self.pause("dst")
        time.sleep(0.3)
        p = os.path.join(self.dst, "in", "temp.json")
        r0, m0, f0 = self.reg(), os.stat(p).st_mtime_ns, self.frame()
        time.sleep(1.2)
        self.assertEqual((self.reg(), os.stat(p).st_mtime_ns, self.frame()), (r0, m0, f0))
        self.resume("dst")
        regs = self.rounds(3)
        self.assertTrue(all(r["state"] == "ok" and r["held"] == 0 for r in regs), regs[-1])
        self.assertEqual(regs[0]["my_round"], r0["my_round"] + 1)

    def test_adapt_killed_reattaches(self):
        """adapt 被 SIGKILL、keep 重起：新 run 從槽內 state.json 接 since／last_seq，skipped 不重算、同一版不當新版。"""
        self.setup_pair(50, 100, sensor=False, decl={"max_age": None})
        self.wait_for(lambda: self.src_clock(), 10, "來源沒開回合")
        self.write_src(1)
        self.wait_ok(lambda r: r["basis"]["seq"] == 1)
        self.write_src(5)
        before = self.wait_ok(lambda r: r["basis"]["seq"] == 5)
        self.assertEqual(before["skipped"], 3)
        fr0 = self.frame()
        run = self.kill_slot(self.dst, "adapt-temp")
        self.wait_for(lambda: (self.birth(self.dst, "adapt-temp").get("run") or 0) > run, 10, "keep 沒重起")
        regs = self.rounds(3)
        for r in regs:
            self.assertEqual((r["state"], r["skipped"], r["basis"]["sha"]), ("ok", 3, before["basis"]["sha"]), r)
        fr = self.frame()
        self.assertEqual((fr["since"], fr["last_seq"], fr["skipped"]), (fr0["since"], 5, 3))
        self.write_src(6)
        self.assertEqual(self.wait_ok(lambda r: r["basis"]["seq"] == 6)["skipped"], 3)
        self.write_src(9)
        self.assertEqual(self.wait_ok(lambda r: r["basis"]["seq"] == 9)["skipped"], 5)


# ---------------------------------------------------------------- 門檻、消費者、step、長跑

class TestConsumers(AdaptCase):
    """〔adapt〕門檻邊界＋fan 消費者、step 的 num 條件直接吃暫存器、300 回合檔數不長。"""

    def fan(self):
        return read_json(os.path.join(self.dst, "out", "fan.json")) or {}

    def test_threshold_and_fan(self):
        """801→hot true；800→hot null＋unknown（80.0±0.05 跨 80）；799、790→false。fan 在 unknown 時保持上一動作、記 held。"""
        fan = {"name": "fan", "mode": "keep", "argv": [PY, os.path.join(EX, "fan.py"), "in/temp.json"]}
        self.setup_pair(50, 100, dst_tasks=[fan], feed=801)
        r = self.wait_ok(lambda r: r["value"]["c"] == 80.1)
        self.assertEqual((r["value"], r["err"]), ({"c": 80.1, "hot": True}, {"c": 0.05}))
        self.wait_for(lambda: self.fan().get("on") is True, 10, "fan 沒開")
        self.feed(800)
        r = self.collect(lambda o: o[-1]["why"] == "within_error_band", 10, "800 沒落在誤差帶")[-1]
        self.assertEqual((r["state"], r["value"]), ("unknown", None))
        self.assertEqual(r["trace"][1]["x"], 80.0)
        self.assertIsNone(r["trace"][2]["v"])
        self.assertEqual(r["last"]["value"]["hot"], True)
        f = self.wait_for(lambda: self.fan() if self.fan().get("held", 0) >= 1 else None, 10, "fan 沒記 held")
        self.assertEqual((f["on"], f["why"]), (True, "within_error_band"))
        for t_dc in (799, 790):
            self.feed(t_dc)
            r = self.wait_ok(lambda r, t=t_dc: r["value"]["c"] == t_dc / 10)
            self.assertEqual(r["value"]["hot"], False)
        f = self.wait_for(lambda: self.fan() if self.fan().get("on") is False else None, 10, "fan 沒關")
        self.assertEqual((f["held"], f["basis"]["src"]), (0, "src/out/temp.json"))
        st = subprocess.run([PY, ADAPT, "status", "adapt/temp.json"], cwd=self.dst, capture_output=True, text=True)
        self.assertEqual(st.returncode, 0, st.stderr)
        self.assertEqual((json.loads(st.stdout)["state"], json.loads(st.stdout)["value"]["c"]), ("ok", 79.0))

    def test_step_num_condition(self):
        """step 不改一行：wait 的 num 條件讀 in/temp.json 的 value.c；79.0 不成立、80.0（unknown，欄位缺）不成立且耐性照步算、
        80.1 成立走 then。"""
        job = {"job": "gate", "start": "w", "steps": {
            "w": {"wait": {"num": "in/temp.json", "key": "value.c", "op": ">=", "value": 80}, "patience": 200,
                  "then": "done"},
            "done": {"end": "ok"}}}
        self.setup_pair(50, 100, feed=790,
                        dst_tasks=[{"name": "step-gate", "mode": "keep", "argv": [PY, STEP, "run", "jobs/gate"]}])
        write_json(os.path.join(self.dst, "jobs", "gate", "steps.json"), job)

        def frame():
            return read_json(os.path.join(self.dst, "jobs", "gate", "frame.json")) or {}
        self.wait_ok(lambda r: r["value"]["c"] == 79.0)
        self.wait_for(lambda: (frame().get("seen") or 0) > (frame().get("since") or 1 << 30), 10, "step 沒在等")
        self.feed(800)
        self.collect(lambda o: o[-1]["why"] == "within_error_band" and len(o) >= 3, 10, "800 沒落在誤差帶")
        time.sleep(0.3)
        fr = frame()
        self.assertEqual((fr["phase"], fr["pc"], fr["halt"]), ("running", "w", None))
        self.assertGreater(fr["seen"], fr["since"])            # 耐性照步算：since 不動、seen 前進
        self.feed(801)
        self.wait_for(lambda: frame().get("phase") == "ended", 10, "801 之後 step 沒走 then")
        self.assertEqual((frame()["end"], frame()["since"] >= fr["since"]), ("ok", True))
        self.assertEqual(self.reg()["value"]["c"], 80.1)

    def test_long_run_file_count(self):
        """300 個 dst 回合後 dst 的 in/、adapt/、adapt 槽與 src 的 out/ 檔數不變（暫存器、框架都覆寫）。"""
        self.setup_pair(20, 20, feed=790)          # 固定讀數：鋸齒波會碰到 800（誤差帶）
        self.wait_ok()

        def counts():
            out = {}
            for name, d in (("in", os.path.join(self.dst, "in")), ("adapt", os.path.join(self.dst, "adapt")),
                            ("slot", self.slot(self.dst, "adapt-temp")), ("out", os.path.join(self.src, "out"))):
                out[name] = sorted(n for n in os.listdir(d) if not n.startswith("."))
            return out
        c0, r0 = counts(), self.reg()["my_round"]
        regs = self.collect(lambda o: o[-1]["my_round"] >= r0 + 300, 180, "沒跑滿 300 回合", fresh=True)
        self.assertEqual(counts(), c0)
        self.assertEqual([(r["my_round"], r["why"]) for r in regs if r["state"] != "ok"], [])
        st = self.frame()
        self.assertEqual(set(st), {"v", "sense", "chain", "since", "my_round", "last_ok_my_round", "last_clock",
                                   "last_seq", "stall_rounds", "skipped", "resetting", "void_sha", "prev_state", "cur",
                                   "last"})


if __name__ == "__main__":
    import unittest
    unittest.main()
