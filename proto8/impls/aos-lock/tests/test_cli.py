#!/usr/bin/env python3
"""test_cli.py：aos-lock 命令列的測試（ctest 會跑）。只用標準庫（unittest）。

    python3 tests/test_cli.py bin/aos-lock

A 段：命令列的錯；B 段：目標 → 鎖資料夾；C 段：名牌（holder、pid＝叫它的行程、started_at_ticks、boot_id、lease_ms、note）、show；
D 段：搶（十個行程搶同一把只有一個拿到）；E 段：收屍（kill -9 持有者、boot_id 不同、pid 被重用、租約到期、名牌沒寫好就死、
殭屍、30 個人同時收同一把死鎖）；
F 段：等（--wait-ms）；G 段：放（release、殘骸 .releasing.* 不擋人）。
"""
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

BIN = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else
                      os.path.join(os.path.dirname(__file__), "..", "bin", "aos-lock"))
AT = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}\+00:00$")


def ticks(pid):
    text = Path("/proc/%d/stat" % pid).read_text()
    return int(text[text.rfind(")") + 1:].split()[19])


def boot():
    return Path("/proc/sys/kernel/random/boot_id").read_text().strip()


def iso(epoch_ms):
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(epoch_ms // 1000)) + ".%03d+00:00" % (epoch_ms % 1000)


class Case(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.t = Path(self.td.name)
        self.home = self.t / "home"
        self.home.mkdir()
        self.target = self.t / "data.json"     # 檔的鎖：data.json.lock/
        self.lock = self.t / "data.json.lock"
        self.procs = []

    def tearDown(self):
        for p in self.procs:
            if p.poll() is None:
                p.kill()
            p.wait()
            for f in (p.stdout, p.stderr):
                if f:
                    f.close()
        self.td.cleanup()

    def env(self, extra=None):
        e = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        e["HOME"] = str(self.home)
        e.update(extra or {})
        return e

    def run_l(self, *args, extra=None):
        return subprocess.run([BIN, *[str(a) for a in args]], env=self.env(extra), cwd=self.t, capture_output=True,
                              text=True, timeout=60)

    def code(self, *args, extra=None):
        r = self.run_l(*args, extra=extra)
        self.assertEqual(r.stderr, "")
        return r.returncode

    def own_error(self, r, code):
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertEqual(len(r.stderr.splitlines()), 1, r.stderr)
        self.assertTrue(r.stderr.startswith("aos-lock: %s " % code), r.stderr)

    def holder(self, lock=None):
        return json.loads(((lock or self.lock) / "holder.json").read_text())

    def keeper(self, target=None, flags=()):
        """起一個 sh：拿鎖（持有者＝這個 sh）、印碼、一直睡。回 (Popen, 碼)。"""
        args = " ".join("'%s'" % a for a in [*flags, str(target or self.target)])
        p = subprocess.Popen(["sh", "-c", "'%s' acquire %s; echo $?; exec sleep 60" % (BIN, args)], env=self.env(),
                             stdout=subprocess.PIPE, text=True)
        self.procs.append(p)
        return p, int(p.stdout.readline())

    def fake(self, **over):
        """手寫一份名牌：預設是本行程（活著）。"""
        h = {"holder": "/x", "pid": os.getpid(), "started_at_ticks": ticks(os.getpid()), "boot_id": boot(),
             "acquired_at": iso(int(time.time() * 1000))}
        h.update(over)
        self.lock.mkdir()
        (self.lock / "holder.json").write_text(json.dumps(h))
        return h

    # ---------- A：命令列的錯 ----------
    def test_a1_args(self):
        self.own_error(self.run_l(), "ArgumentsBad")
        self.own_error(self.run_l("grab", self.target), "CommandUnknown")
        self.own_error(self.run_l("acquire"), "ArgumentsBad")
        self.own_error(self.run_l("show", self.target, "x"), "ArgumentsBad")
        self.own_error(self.run_l("acquire", "--nope", "1", self.target), "FlagUnknown")
        self.own_error(self.run_l("acquire", "--lease-ms", "-1", self.target), "ArgumentsBad")
        self.own_error(self.run_l("acquire", "--wait-ms", "x", self.target), "ArgumentsBad")
        self.own_error(self.run_l("acquire", "--pid", "999999999", self.target), "ArgumentsBad")
        self.assertFalse(self.lock.exists())

    def test_a2_parent_missing(self):
        self.own_error(self.run_l("acquire", self.t / "no" / "x"), "MkdirFailed")

    # ---------- B：目標 → 鎖資料夾 ----------
    def test_b1_targets(self):
        d = self.t / "dir"
        d.mkdir()
        self.assertEqual(self.code("acquire", d), 0)
        self.assertTrue((d / ".lock" / "holder.json").exists())
        (self.t / "f.txt").write_text("x")
        self.assertEqual(self.code("acquire", self.t / "f.txt"), 0)
        self.assertTrue((self.t / "f.txt.lock" / "holder.json").exists())
        self.assertEqual(self.code("acquire", self.t / "ghost"), 0)   # 還不存在的名字＝檔的鎖
        self.assertTrue((self.t / "ghost.lock").is_dir())
        self.own_error(self.run_l("acquire", str(self.t / "dir3") + "/"), "MkdirFailed")   # 結尾 / 但資料夾不在：建不了
        self.assertEqual(self.code("acquire", "rel"), 0)   # 相對 cwd
        self.assertTrue((self.t / "rel.lock").is_dir())

    # ---------- C：名牌、show ----------
    def test_c1_holder(self):
        ws = self.t / "ws"
        r = self.run_l("acquire", "--lease-ms", "5000", "--note", "寫 data", self.target, extra={"AOS_WS": str(ws)})
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))
        h = self.holder()
        self.assertEqual(list(h), ["holder", "pid", "started_at_ticks", "boot_id", "acquired_at", "lease_ms", "note"])
        self.assertEqual(h["holder"], str(ws))
        self.assertEqual(h["pid"], os.getpid())   # 持有者＝叫 aos-lock 的行程
        self.assertEqual(h["started_at_ticks"], ticks(os.getpid()))
        self.assertEqual(h["boot_id"], boot())
        self.assertRegex(h["acquired_at"], AT)
        self.assertEqual((h["lease_ms"], h["note"]), (5000, "寫 data"))
        out = self.run_l("show", self.target)
        self.assertEqual((out.returncode, json.loads(out.stdout)), (0, h))
        self.assertEqual(os.listdir(self.lock), ["holder.json"])

    def test_c2_holder_home_and_pid_flag(self):
        p = subprocess.Popen(["sleep", "60"])
        self.procs.append(p)
        self.assertEqual(self.code("acquire", "--pid", p.pid, self.target), 0)
        h = self.holder()
        self.assertEqual(h["holder"], str(self.home))
        self.assertEqual((h["pid"], h["started_at_ticks"]), (p.pid, ticks(p.pid)))
        self.assertNotIn("lease_ms", h)
        self.assertNotIn("note", h)

    def test_c3_show_none_and_bad(self):
        r = self.run_l("show", self.target)
        self.assertEqual((r.returncode, r.stdout, r.stderr), (10, "", ""))
        self.lock.mkdir()
        self.own_error(self.run_l("show", self.target), "HolderBad")

    # ---------- D：搶 ----------
    def test_d1_only_one_wins(self):
        ps = [subprocess.Popen(["sh", "-c", "'%s' acquire '%s'; echo $?; exec sleep 60" % (BIN, self.target)],
                               env=self.env(), stdout=subprocess.PIPE, text=True) for _ in range(10)]
        self.procs.extend(ps)
        codes = [int(p.stdout.readline()) for p in ps]
        self.assertEqual(sorted(codes), [0] + [10] * 9)
        winner = ps[codes.index(0)]
        self.assertEqual(self.holder()["pid"], winner.pid)

    # ---------- E：收屍 ----------
    def test_e1_kill9_then_reap(self):
        p, c = self.keeper()
        self.assertEqual(c, 0)
        self.assertEqual(self.holder()["pid"], p.pid)
        self.assertEqual(self.code("acquire", self.target), 10)   # 活著：拿不到
        p.kill()
        p.wait()
        self.assertEqual(self.code("acquire", self.target), 0)    # 死了：收屍、拿到
        self.assertEqual(self.holder()["pid"], os.getpid())
        self.assertEqual(sorted(os.listdir(self.t)), ["data.json.lock", "home"])   # 收掉的那把刪乾淨了

    def test_e2_other_boot(self):
        self.fake(boot_id="00000000-0000-0000-0000-000000000000")   # pid、ticks 都對得上，但開機過了
        self.assertEqual(self.code("acquire", self.target), 0)
        self.assertEqual(self.holder()["boot_id"], boot())

    def test_e3_pid_reused(self):
        self.fake(started_at_ticks=ticks(os.getpid()) - 1)
        self.assertEqual(self.code("acquire", self.target), 0)

    def test_e4_alive_kept(self):
        self.fake()
        self.assertEqual(self.code("acquire", self.target), 10)
        self.assertEqual(self.holder()["holder"], "/x")

    def test_e5_lease(self):
        now = int(time.time() * 1000)
        self.fake(lease_ms=100000, acquired_at=iso(now))
        self.assertEqual(self.code("acquire", self.target), 10)   # 租約還沒到
        (self.lock / "holder.json").write_text(json.dumps({**self.holder(), "lease_ms": 1000,
                                                           "acquired_at": iso(now - 5000)}))
        self.assertEqual(self.code("acquire", self.target), 0)    # 持有者活著，但租約過了

    def test_e6_no_holder_json(self):
        self.lock.mkdir()   # 持有者 mkdir 完、還沒寫名牌就死了
        self.assertEqual(self.code("acquire", self.target), 10)   # 剛建的：可能還在寫，不收
        old = time.time() - 11
        os.utime(self.lock, (old, old))
        self.assertEqual(self.code("acquire", self.target), 0)    # 10 秒沒動過：收

    def test_e7_null_ticks(self):
        p = subprocess.Popen(["sleep", "60"])
        self.procs.append(p)
        self.fake(pid=p.pid, started_at_ticks=None, boot_id=None)   # 非 Linux 寫的：只看 pid 在不在
        self.assertEqual(self.code("acquire", self.target), 10)
        p.kill()
        p.wait()
        self.assertEqual(self.code("acquire", self.target), 0)

    def test_e8_many_reapers(self):
        """很多人同時判到同一把死鎖：只有一個拿到，沒有人把別人剛拿到的新鎖搬走（收屍牌 .reaping）。"""
        for rnd in range(6):
            target = self.t / ("r%d" % rnd)
            self.target, self.lock = target, Path(str(target) + ".lock")
            sleeper = subprocess.Popen(["sleep", "60"])
            self.procs.append(sleeper)
            self.fake(pid=sleeper.pid, started_at_ticks=ticks(sleeper.pid))
            lock = self.lock
            # 等的人的持有者都寫本行程（活著）：誰拿到都不會被當成死的，所以拿到 0 的只能有一個
            ps = [subprocess.Popen([BIN, "acquire", "--wait-ms", "800", str(target)], env=self.env(),
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(30)]
            self.procs.extend(ps)
            time.sleep(0.3)   # 大家都在每 20 毫秒輪詢
            sleeper.kill()    # 持有者死掉：大家幾乎同時判到同一把死鎖
            sleeper.wait()
            res = [(p.wait(timeout=30), p.stderr.read()) for p in ps]
            self.assertEqual(sorted(c for c, _ in res), [0] + [10] * 29, "第 %d 輪：%r" % (rnd, res))
            self.assertEqual([e for _, e in res if e], [])
            self.assertEqual(json.loads((lock / "holder.json").read_text())["pid"], os.getpid())

    # ---------- F：等 ----------
    def test_f1_wait_times_out(self):
        self.fake()
        t0 = time.monotonic()
        self.assertEqual(self.code("acquire", "--wait-ms", "300", self.target), 10)
        self.assertGreaterEqual(time.monotonic() - t0, 0.3)

    def test_f2_wait_until_released(self):
        p, c = self.keeper()
        self.assertEqual(c, 0)
        w = subprocess.Popen([BIN, "acquire", "--wait-ms", "20000", str(self.target)], env=self.env(),
                             stderr=subprocess.PIPE, text=True)
        self.procs.append(w)
        time.sleep(0.3)
        self.assertIsNone(w.poll())
        p.kill()   # 持有者死了：等的人收屍拿到
        self.assertEqual(w.wait(timeout=10), 0)

    # ---------- G：放 ----------
    def test_g1_release(self):
        self.assertEqual(self.code("acquire", self.target), 0)
        self.assertEqual(self.code("release", self.target), 0)
        self.assertEqual(sorted(os.listdir(self.t)), ["home"])   # 改名再刪，不留殘骸
        self.own_error(self.run_l("release", self.target), "LockMissing")
        self.assertEqual(self.code("acquire", self.target), 0)

    def test_g2_releasing_leftover_does_not_block(self):
        left = self.t / "data.json.lock.releasing.00000000000000000001.1.1"
        left.mkdir()
        (left / "holder.json").write_text("{}")
        self.assertEqual(self.code("acquire", self.target), 0)
        self.assertTrue(left.exists())   # 別人刪到一半的殘骸不碰


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0], "-v"])
