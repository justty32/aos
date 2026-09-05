"""aosp/fsutil.py：原子寫、鎖、now_iso()、new_id()。"""
import os
import subprocess
import sys

PROTO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROTO not in sys.path:
    sys.path.insert(0, PROTO)

from aosp import fsutil  # noqa: E402
from .helpers import LandCase  # noqa: E402


class TestAtomicWrite(LandCase):
    def test_content_roundtrips(self):
        p = os.path.join(self.tmp, "f.txt")
        fsutil.atomic_write_text(p, "hello world")
        with open(p, "r", encoding="utf-8") as f:
            got = f.read()
        self.assertEqual(got, "hello world",
                          msg="atomic_write_text 寫完的內容要原封不動讀回來，實際讀到 %r" % got)

    def test_no_leftover_tmp_file(self):
        p = os.path.join(self.tmp, "g.txt")
        fsutil.atomic_write_text(p, "x")
        self.assertFalse(os.path.exists(p + ".tmp"),
                          msg="寫完不該留下 .tmp 檔：%s" % (p + ".tmp"))

    def test_overwrite_replaces_whole_content(self):
        p = os.path.join(self.tmp, "h.txt")
        fsutil.atomic_write_text(p, "a very long old content that is much longer than new")
        fsutil.atomic_write_text(p, "short")
        with open(p, "r", encoding="utf-8") as f:
            got = f.read()
        self.assertEqual(got, "short",
                          msg="覆寫應該整份換掉，不該殘留舊內容的尾巴，實際讀到 %r" % got)

    def test_write_json_read_json_roundtrip(self):
        p = os.path.join(self.tmp, "j.json")
        fsutil.write_json(p, {"a": 1, "b": [1, 2, 3]})
        got = fsutil.read_json(p)
        self.assertEqual(got, {"a": 1, "b": [1, 2, 3]},
                          msg="write_json/read_json 應該對稱，實際讀到 %r" % got)

    def test_read_json_missing_returns_default(self):
        got = fsutil.read_json(os.path.join(self.tmp, "nope.json"), default="fallback")
        self.assertEqual(got, "fallback",
                          msg="檔不存在時 read_json 應該回傳 default，實際 %r" % got)


class TestLock(LandCase):
    def test_double_acquire_raises_lock_busy(self):
        lock_path = os.path.join(self.tmp, "lock")
        lk1 = fsutil.Lock(lock_path)
        lk1.acquire()
        try:
            lk2 = fsutil.Lock(lock_path)
            with self.assertRaises(fsutil.LockBusy,
                                    msg="同一把鎖已經被拿走時，再拿應該丟 LockBusy"):
                lk2.acquire()
        finally:
            lk1.release()

    def test_release_then_acquire_succeeds(self):
        lock_path = os.path.join(self.tmp, "lock2")
        lk1 = fsutil.Lock(lock_path)
        lk1.acquire()
        lk1.release()
        lk2 = fsutil.Lock(lock_path)
        try:
            lk2.acquire()  # 不應該丟例外
        except fsutil.LockBusy:
            self.fail("release() 之後同一把鎖應該拿得到，卻丟了 LockBusy")
        finally:
            lk2.release()

    def test_dead_pid_lock_is_reclaimed(self):
        lock_path = os.path.join(self.tmp, "lock3")
        # 手動製造一個「持鎖者已經死了」的鎖檔：起一支馬上結束的子行程，wait() 完保證它死了
        p = subprocess.Popen([sys.executable, "-c", "pass"])
        dead_pid = p.pid
        p.wait()
        fsutil.write_json(lock_path, {"pid": dead_pid, "at": fsutil.now_iso()})
        lk = fsutil.Lock(lock_path)
        try:
            lk.acquire()
        except fsutil.LockBusy:
            self.fail("鎖檔裡的 pid 已死，acquire() 應該把鎖收回來，而不是丟 LockBusy")
        finally:
            lk.release()

    def test_live_pid_lock_is_not_reclaimed(self):
        """對照組：pid 還活著（自己的 pid）不該被偷走。"""
        lock_path = os.path.join(self.tmp, "lock4")
        fsutil.write_json(lock_path, {"pid": os.getpid(), "at": fsutil.now_iso()})
        lk = fsutil.Lock(lock_path)
        with self.assertRaises(fsutil.LockBusy,
                                msg="持鎖者還活著就不該被當成孤兒鎖偷走"):
            lk.acquire()


class TestMisc(LandCase):
    def test_now_iso_format(self):
        s = fsutil.now_iso()
        self.assertRegex(s, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$",
                          msg="now_iso() 格式應該是 YYYY-MM-DDTHH:MM:SS.mmmZ，實際是 %r" % s)

    def test_new_id_is_32_lowercase_hex(self):
        i = fsutil.new_id()
        self.assertRegex(i, r"^[0-9a-f]{32}$",
                          msg="new_id() 應該是 32 個小寫 hex，實際是 %r" % i)

    def test_new_id_is_unique(self):
        ids = [fsutil.new_id() for _ in range(200)]
        self.assertEqual(len(ids), len(set(ids)),
                          msg="new_id() 連續產生 200 次不該重複")
