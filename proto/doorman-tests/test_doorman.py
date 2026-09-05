"""門房第一級：在同一支行程裡直接呼叫 Doorman 的測試（不起子行程，快且穩）。"""
import functools
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import doorman  # noqa: E402


LAND_ID = "0123456789abcdef0123456789abcdef"


def make_land(root, name, land_id=LAND_ID, atomic=True, layout=None):
    """建一塊地：`.aos/layout.json` 用原子改名就位（跟 aos init 一樣）。"""
    land = os.path.join(root, name)
    aos = os.path.join(land, ".aos")
    os.makedirs(aos, exist_ok=True)
    if layout is None:
        layout = {"format_version": 1, "layout_version": 1}
        if land_id is not None:
            layout["land_id"] = land_id
    body = layout if isinstance(layout, str) else json.dumps(layout, ensure_ascii=False)
    target = os.path.join(aos, "layout.json")
    if atomic:
        tmp = target + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(body)
        os.rename(tmp, target)
    else:
        with open(target, "w", encoding="utf-8") as f:
            f.write(body)
    return os.path.realpath(land)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="doorman-test.")
        self.root = os.path.realpath(os.path.join(self.tmp, "root"))
        self.home = os.path.realpath(os.path.join(self.tmp, "home"))
        os.makedirs(self.root)
        os.makedirs(self.home)
        self.registry = os.path.join(self.home, ".aos", "registry.json")
        self.log = os.path.join(self.home, ".aos", "doorman.jsonl")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def doorman(self, **kw):
        kw.setdefault("force_poll", True)
        return doorman.Doorman(self.root, self.home, **kw)

    def entries(self):
        reg = doorman.read_json(self.registry, {"entries": []})
        return reg["entries"]

    def entry(self, path):
        for e in self.entries():
            if e["path"] == path:
                return e
        return None

    def lines(self):
        if not os.path.exists(self.log):
            return []
        with open(self.log, encoding="utf-8") as f:
            return [json.loads(ln) for ln in f if ln.strip()]

    def kinds(self):
        return [ln["kind"] for ln in self.lines()]


class TestBirth(Base):
    def test_birth_registers_stopped_with_no_clock(self):
        land = make_land(self.root, "a")
        d = self.doorman()
        d.run(once=True)

        e = self.entry(land)
        self.assertIsNotNone(e, "出生沒被登記：%s" % self.entries())
        self.assertEqual(e["state"], "stopped")          # S-13-22
        self.assertIsNone(e["pid"])
        self.assertIsNone(e["pid_start"])
        self.assertIsNone(e["clock"])                    # S-13-23 門房不起時鐘
        self.assertIsNone(e["parent"])
        self.assertEqual(e["land_id"], LAND_ID)
        self.assertEqual(e["ext"]["by"], "doorman")

    def test_birth_writes_one_event_line(self):
        land = make_land(self.root, "a")
        self.doorman().run(once=True)
        lines = self.lines()
        self.assertEqual(len(lines), 1, lines)
        ln = lines[0]
        self.assertEqual(ln["kind"], "born")
        self.assertEqual(ln["path"], land)
        self.assertRegex(ln["at"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
        # schema 要的欄名也同時寫著
        self.assertEqual(ln["event"], "born")

    def test_bare_aos_dir_is_not_a_birth(self):
        """S-13-48：只建了 .aos/ 不算出生。"""
        os.makedirs(os.path.join(self.root, "half", ".aos"))
        self.doorman().run(once=True)
        self.assertEqual(self.kinds(), [])
        self.assertEqual(self.entries(), [])

    def test_broken_layout_is_born_invalid_and_not_registered(self):
        """S-13-49：layout.json 讀不到／不合格就記 born_invalid，不登記。"""
        land = make_land(self.root, "bad", layout="{ 不是 json")
        self.doorman().run(once=True)
        self.assertEqual(self.kinds(), ["born_invalid"])
        self.assertIsNone(self.entry(land))
        self.assertIn("json", self.lines()[0]["ext"]["why"])

    def test_layout_without_land_id_still_registers_by_default(self):
        """proto 的 aos init 不寫 land_id；預設放行（land_id 記 null）並在本子留警告。"""
        land = make_land(self.root, "noid", land_id=None)
        self.doorman().run(once=True)
        self.assertEqual(self.kinds(), ["born"])
        self.assertIsNone(self.entry(land)["land_id"])
        self.assertIn("land_id", self.lines()[0]["ext"]["warn"])

    def test_broken_layout_is_not_logged_over_and_over(self):
        """同一塊壞地每輪掃描都記一行的話，本子會被洗版。"""
        make_land(self.root, "bad", layout="{ 不是 json")
        d = self.doorman()
        d.run(once=True)
        d.sweep()
        d.sweep()
        self.assertEqual(self.kinds(), ["born_invalid"])

    def test_strict_layout_rejects_missing_land_id(self):
        land = make_land(self.root, "noid", land_id=None)
        self.doorman(strict_layout=True).run(once=True)
        self.assertEqual(self.kinds(), ["born_invalid"])
        self.assertIsNone(self.entry(land))

    def test_depth_limit(self):
        """S-13-31：不遞迴整棵樹，只看 --depth 層以內。"""
        shallow = make_land(self.root, os.path.join("x", "shallow"))     # 深度 2
        deep = make_land(self.root, os.path.join("x", "y", "deep"))      # 深度 3
        self.doorman(depth=2).run(once=True)
        self.assertIsNotNone(self.entry(shallow))
        self.assertIsNone(self.entry(deep))

    def test_root_itself_can_be_a_land(self):
        os.makedirs(os.path.join(self.root, ".aos"), exist_ok=True)
        with open(os.path.join(self.root, ".aos", "layout.json"), "w", encoding="utf-8") as f:
            json.dump({"format_version": 1, "layout_version": 1, "land_id": LAND_ID}, f)
        self.doorman().run(once=True)
        self.assertIsNotNone(self.entry(self.root))


class TestDeath(Base):
    def test_deleting_the_folder_marks_stopped_with_died_at(self):
        land = make_land(self.root, "a")
        d = self.doorman()
        d.run(once=True)
        shutil.rmtree(land)
        d.sweep()

        e = self.entry(land)
        self.assertEqual(e["state"], "stopped")
        self.assertIsNone(e["pid"])
        self.assertIn("died_at", e["ext"])
        self.assertEqual(e["ext"]["died_by"], "doorman")
        self.assertEqual(self.kinds(), ["born", "gone"])

    def test_deleting_only_dot_aos_counts_as_death(self):
        land = make_land(self.root, "a")
        d = self.doorman()
        d.run(once=True)
        shutil.rmtree(os.path.join(land, ".aos"))
        d.sweep()
        self.assertEqual(self.kinds(), ["born", "gone"])
        self.assertIn("died_at", self.entry(land)["ext"])

    def test_fresh_doorman_picks_up_a_death_it_never_saw(self):
        """門房重啟：登記表上有、路徑不在了 → 照樣判死（S-13-19 的保底那條路）。"""
        land = make_land(self.root, "a")
        self.doorman().run(once=True)
        shutil.rmtree(land)
        self.doorman().run(once=True)           # 全新的門房，seen 是空的
        self.assertEqual(self.kinds(), ["born", "gone"])

    def test_death_is_not_logged_twice(self):
        land = make_land(self.root, "a")
        self.doorman().run(once=True)
        shutil.rmtree(land)
        self.doorman().run(once=True)
        self.doorman().run(once=True)           # 再掃一遍不該再記一次
        self.assertEqual(self.kinds(), ["born", "gone"])


class TestNoDuplicateEntry(Base):
    def test_repeated_life_and_death_keeps_one_entry(self):
        """同一塊地反覆生死，登記表永遠只有一筆（S-08-11）。"""
        d = self.doorman()
        for _ in range(3):
            land = make_land(self.root, "a")
            d.sweep()
            shutil.rmtree(land)
            d.sweep()
        land = make_land(self.root, "a")
        d.sweep()

        same = [e for e in self.entries() if e["path"] == land]
        self.assertEqual(len(same), 1, self.entries())
        self.assertEqual(len(self.entries()), 1)
        # 本子照樣一次生死記一筆
        self.assertEqual(self.kinds(), ["born", "gone"] * 3 + ["born"])
        # 重生時把死亡標記清掉，狀態看得見
        self.assertNotIn("died_at", same[0]["ext"])
        self.assertIn("reborn_at", same[0]["ext"])

    def test_rebirth_does_not_overwrite_someone_elses_clock(self):
        """S-08-87 的精神：門房不准改別人寫的鐘。"""
        land = make_land(self.root, "a")
        d = self.doorman()
        d.run(once=True)
        # 假裝 daemon 替它起了鐘
        reg = doorman.read_json(self.registry)
        reg["entries"][0]["clock"] = {"kind": "every", "every_ms": 5000}
        reg["entries"][0]["state"] = "running"
        doorman.write_json(self.registry, reg)

        shutil.rmtree(land)
        d.sweep()
        make_land(self.root, "a")
        d.sweep()
        e = self.entry(land)
        self.assertEqual(e["clock"], {"kind": "every", "every_ms": 5000})


class TestOrphanReap(Base):
    def _spawn(self):
        p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"],
                             start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(self._kill, p)
        for _ in range(100):
            if doorman.proc_start(p.pid) is not None:
                break
            time.sleep(0.01)
        return p

    @staticmethod
    def _kill(p):
        try:
            p.kill()
            p.wait(timeout=5)
        except Exception:
            pass

    def test_orphan_pid_is_reaped_then_entry_marked_stopped(self):
        """S-13-17：路徑不在了、pid 還活著 → 先補刀再改登記表。"""
        land = make_land(self.root, "a")
        d = self.doorman()
        d.run(once=True)
        p = self._spawn()
        reg = doorman.read_json(self.registry)
        reg["entries"][0]["pid"] = p.pid
        reg["entries"][0]["pid_start"] = doorman.proc_start(p.pid)
        reg["entries"][0]["state"] = "running"
        doorman.write_json(self.registry, reg)

        shutil.rmtree(land)
        d.sweep()

        self.assertFalse(doorman.alive(p.pid), "孤魂沒被補掉")
        p.wait(timeout=5)
        e = self.entry(land)
        self.assertEqual(e["state"], "stopped")
        self.assertIsNone(e["pid"])
        self.assertIsNone(e["pid_start"])
        self.assertEqual(e["ext"]["killed_pid"], p.pid)
        # 本子看得到：先記 gone（帶 orphan_pid），補完刀再記一筆
        lines = self.lines()
        self.assertEqual([ln["kind"] for ln in lines], ["born", "gone", "gone"])
        self.assertEqual(lines[1]["ext"]["orphan_pid"], p.pid)
        self.assertEqual(lines[2]["ext"]["killed_pid"], p.pid)

    def test_stale_pid_start_means_no_kill(self):
        """S-08-68：pid 被系統重用時不准把刀砍到無辜的第三方。"""
        land = make_land(self.root, "a")
        d = self.doorman()
        d.run(once=True)
        p = self._spawn()
        reg = doorman.read_json(self.registry)
        reg["entries"][0]["pid"] = p.pid
        reg["entries"][0]["pid_start"] = doorman.proc_start(p.pid) + 999999   # 對不上
        reg["entries"][0]["state"] = "running"
        doorman.write_json(self.registry, reg)

        shutil.rmtree(land)
        d.sweep()

        self.assertIsNone(p.poll(), "不該去動 pid_start 對不上的行程")
        e = self.entry(land)
        self.assertEqual(e["state"], "stopped")
        self.assertNotIn("killed_pid", e["ext"])


class TestWriteDiscipline(Base):
    def test_event_lands_in_the_notebook_before_the_registry(self):
        """S-13-08：事件先落本子，再改登記表。鎖被活人佔住時，本子已經有那一筆。"""
        make_land(self.root, "a")
        lock = os.path.join(self.home, ".aos", "registry.lock")
        os.makedirs(os.path.dirname(lock), exist_ok=True)
        with open(lock, "w", encoding="utf-8") as f:            # 佔鎖的是本行程，活的
            json.dump({"pid": os.getpid(), "at": doorman.now_iso()}, f)

        d = self.doorman()
        orig = doorman.Lock
        doorman.Lock = functools.partial(orig, wait_ms=200)     # 別等滿 5 秒
        try:
            with self.assertRaises(doorman.LockBusy):
                d.run(once=True)
        finally:
            doorman.Lock = orig
        self.assertEqual(self.kinds(), ["born"])                # 本子有了
        self.assertFalse(os.path.exists(self.registry))         # 登記表還沒動

    def test_dead_lock_holder_is_stolen_like_aosp_does(self):
        """跟 aosp/fsutil.Lock 同一把鎖：持鎖者死了就收回，不是另一種鎖。"""
        dead = subprocess.Popen([sys.executable, "-c", "pass"])
        dead.wait()
        lock = os.path.join(self.home, ".aos", "registry.lock")
        os.makedirs(os.path.dirname(lock), exist_ok=True)
        with open(lock, "w", encoding="utf-8") as f:
            json.dump({"pid": dead.pid, "at": doorman.now_iso()}, f)

        make_land(self.root, "a")
        self.doorman().run(once=True)
        self.assertEqual(len(self.entries()), 1)
        self.assertFalse(os.path.exists(lock), "做完要把鎖還回去")

    def test_registry_write_is_atomic_and_leaves_no_tmp(self):
        make_land(self.root, "a")
        self.doorman().run(once=True)
        self.assertTrue(os.path.exists(self.registry))
        self.assertFalse(os.path.exists(self.registry + ".tmp"))
        with open(self.registry, encoding="utf-8") as f:
            reg = json.load(f)
        self.assertEqual(reg["format_version"], 1)
        self.assertIn("daemon_pid", reg)

    def test_entry_has_every_field_the_registry_schema_requires(self):
        land = make_land(self.root, "a")
        self.doorman().run(once=True)
        e = self.entry(land)
        for k in ("path", "pid", "pid_start", "land_id", "state", "clock",
                  "budget", "parent", "registered_at", "updated_at"):
            self.assertIn(k, e)
        for k in ("registered_at", "updated_at"):
            self.assertRegex(e[k], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")

    def test_doorman_never_touches_a_land_dot_aos(self):
        """S-13-09：門房不准改任何一塊地的 .aos/。"""
        land = make_land(self.root, "a")
        aos = os.path.join(land, ".aos")
        before = sorted(os.listdir(aos))
        stat_before = os.stat(os.path.join(aos, "layout.json")).st_mtime_ns
        self.doorman().run(once=True)
        self.assertEqual(sorted(os.listdir(aos)), before)
        self.assertEqual(os.stat(os.path.join(aos, "layout.json")).st_mtime_ns, stat_before)


class TestLayoutCheck(Base):
    def test_check_layout_verdicts(self):
        ok, lid, why = doorman.check_layout(make_land(self.root, "good"))
        self.assertTrue(ok)
        self.assertEqual(lid, LAND_ID)
        self.assertIsNone(why)

        ok, lid, why = doorman.check_layout(
            make_land(self.root, "novers", layout={"format_version": 1}))
        self.assertFalse(ok)
        self.assertIn("layout_version", why)

        ok, lid, why = doorman.check_layout(
            make_land(self.root, "badid", layout={"format_version": 1, "layout_version": 1,
                                                  "land_id": "XYZ"}))
        self.assertTrue(ok)          # 只警告，不否決
        self.assertIsNone(lid)
        self.assertIn("hex", why)

        ok, _, why = doorman.check_layout(os.path.join(self.root, "nothing"))
        self.assertFalse(ok)
        self.assertIn("沒有", why)


if __name__ == "__main__":
    unittest.main()
