"""事件保存與取樣：真 SIGKILL 驗證四個保存窗口及來源進度恢復。"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "tests"))

import argparse  # noqa: E402
import fcntl  # noqa: E402
import importlib.machinery  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402
import unittest  # noqa: E402
from unittest import mock  # noqa: E402
from base import CoreCase, MODULES  # noqa: E402
from aos7_fs import Unknown, read_json, write_json  # noqa: E402

EVENTS = os.path.join(MODULES, "events")
sys.path.insert(0, EVENTS)
import aos7_events_store as store  # noqa: E402
loader = importlib.machinery.SourceFileLoader("events_sampler", os.path.join(EVENTS, "aos7-events"))
spec = importlib.util.spec_from_loader(loader.name, loader)
sampler = importlib.util.module_from_spec(spec)
loader.exec_module(sampler)

DRIVER = '''import os, sys
sys.path.insert(0, %r)
import aos7_events_store as s
from aos7_fs import read_json, write_json
d, channel, n, crash_after, point, progress = sys.argv[1:]
for i in range((read_json(progress) or 0) + 1, int(n) + 1):
    if os.environ.get("DRIVER_ACK"):
        s.ack(d, i - 1)   # 消費者跟上：must 輪替時會刪已確認段（after-unlink 才打得到）
    if point and i >= int(crash_after):
        os.environ["AOS7_TEST_CRASH"] = point
    result = s.append(d, channel, {"kind": "t", "capture": "published", "event_id": "e%%d" %% i,
                      "source": {}, "payload": {"i": i, "pad": "x" * 200}}, node="n",
                      config={"segment_bytes": 2048, "keep_segments": 4})
    if not result["ok"]:
        sys.exit(3)
    write_json(progress, i)
    with open(progress + ".ok", "a") as f:
        f.write("%%d %%d %%d\\n" %% (i, result["seq"], result["dup"]))
''' % EVENTS


class EventsCase(CoreCase):
    def setUp(self):
        super().setUp()
        self.d = os.path.join(self.root, "events")

    def append(self, i=1, ch="obs", config=None, **extra):
        rec = {"kind": "t", "capture": "published", "event_id": "e%d" % i,
               "source": {}, "payload": {"i": i}}
        rec.update(extra)
        return store.append(self.d, ch, rec, node="n", config=config)

    def rows(self, ch="obs"):
        rows = []
        for name in sorted(os.listdir(self.d)):
            if name.startswith(ch + ".") and name.endswith(".jsonl"):
                with open(os.path.join(self.d, name), "rb") as f:
                    for line in f:
                        if line.endswith(b"\n"):
                            rows.append(json.loads(line))
        return sorted(rows, key=lambda r: r["seq"])

    def channel(self, ch="obs"):
        return store.load_state(self.d)["channels"][ch]

    def contents(self):
        result = {}
        for name in os.listdir(self.d):
            if name.endswith(".jsonl"):
                with open(os.path.join(self.d, name), "rb") as f:
                    result[name] = f.read()
        return result

    def assert_layout(self, ch="obs"):
        c = self.channel(ch)
        segs = sorted(int(n.split(".")[1]) for n in os.listdir(self.d)
                      if n.startswith(ch + ".") and n.endswith(".jsonl") and ".active." not in n)
        self.assertEqual(c["segments"], segs)
        self.assertLessEqual(len(segs), store.load_state(self.d)["config"]["keep_segments"])
        self.assertLessEqual(len(os.listdir(self.d)), 12)
        self.assertFalse(any(".tmp" in n for n in os.listdir(self.d)))
        self.assertEqual([r["seq"] for r in self.rows(ch)], list(range(c["dropped_upto"] + 1, c["next_seq"])))


class TestStore(EventsCase):
    def test_append_basic(self):
        for i in range(1, 4):
            self.assertEqual(self.append(i), {"ok": True, "seq": i, "dup": False, "why": None})
        self.assertEqual(set(os.listdir(self.d)), {"obs.active.jsonl", "state.json", "state.json.lock"})
        for row in self.rows():
            self.assertEqual((row["stream"], row["v"]), ("n/obs", 1))
            self.assertEqual(list(row)[:8], ["v", "stream", "seq", "kind", "capture", "event_id", "source", "at"])
        self.assert_layout()

    def test_dup(self):
        self.append()
        self.assertEqual(self.append()["dup"], True)
        self.assertEqual(self.append()["seq"], 1)
        self.assertEqual(len(self.rows()), 1)
        self.append(ch="must")
        self.assertEqual(len(self.rows("must")), 1)

    def test_too_large(self):
        self.append(config={"segment_bytes": 1, "max_record_bytes": 500})
        before = self.contents()
        self.assertEqual(self.append(2, payload={"pad": "漢" * 1000})["why"], "too_large")
        self.assertEqual(self.contents(), before)
        self.assertEqual(self.channel()["next_seq"], 2)

    def test_node_and_config(self):
        self.append(config={"keep_segments": 2})
        self.assertEqual(store.append(self.d, "obs", {}, node="other")["why"], "unknown")
        result = self.append(2, config={"keep_segments": 4, "unused": 8})
        self.assertTrue(result["config_ignored"])
        self.assertEqual(store.load_state(self.d)["config"]["keep_segments"], 2)
        self.assertIsNone(store.recover(self.d, node="other"))

    def test_bad_state(self):
        os.makedirs(self.d)
        path = os.path.join(self.d, "state.json")
        for data in (b"{", b"[]", b'{"v": 1}', b'{"v": 1, "node": "n", "channels": {}}'):
            with open(path, "wb") as f:
                f.write(data)
            self.assertEqual(self.append()["why"], "unknown")
            self.assertIsNone(store.recover(self.d, node="n"))
            with self.assertRaises(Unknown):
                store.ack(self.d, 1)
            with open(path, "rb") as f:
                self.assertEqual(f.read(), data)

    def test_locked_and_load_state(self):
        self.assertIsNone(store.load_state(self.d))
        self.append()
        with open(os.path.join(self.d, "state.json.lock"), "a") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            start = time.monotonic()
            self.assertIsNotNone(store.load_state(self.d))
            self.assertLess(time.monotonic() - start, 0.2)
            with mock.patch.object(store, "LOCK_TIMEOUT", 0.05):
                self.assertEqual(self.append(2)["why"], "unknown")
                self.assertIsNone(store.recover(self.d, node="n"))
                with self.assertRaises(Unknown):
                    store.ack(self.d, 1)
            self.assertLess(time.monotonic() - start, 1)

    def test_value_errors(self):
        cases = [("x", {}, "n"), ("obs", [], "n"), ("obs", {}, ""), ("obs", {}, 1)]
        cases += [("obs", {k: 1}, "n") for k in ("seq", "stream", "v")]
        cases += [("obs", {"capture": "published", "event_id": v}, "n") for v in (None, "", 3)]
        for ch, rec, node in cases:
            with self.subTest(ch=ch, rec=rec, node=node), self.assertRaises(ValueError):
                store.append(self.d, ch, rec, node=node)
        for v in (0, -1, True, "2"):
            with self.assertRaises(ValueError):
                self.append(config={"segment_bytes": v})
        for v in (True, "2", None):
            with self.assertRaises(ValueError):
                store.ack(self.d, v)

    def test_ack(self):
        self.assertEqual(store.ack(self.d, 100), 0)
        for i in range(1, 4):
            self.append(i, ch="must")
        self.assertEqual(store.ack(self.d, 2), 2)
        self.assertEqual(store.ack(self.d, 1), 2)
        self.assertEqual(store.ack(self.d, 999), 3)

    def test_oserror(self):
        self.append()
        with mock.patch.object(store, "write_json", side_effect=OSError("EIO")):
            self.assertEqual(self.append(2)["why"], "unknown")
            self.assertIsNone(store.recover(self.d, node="n"))
            with self.assertRaises(Unknown):
                store.ack(self.d, 1)
        self.assertTrue(self.append(2)["dup"])


class TestRecovery(EventsCase):
    def test_torn_and_tmp(self):
        self.append()
        with open(os.path.join(self.d, "obs.active.jsonl"), "ab") as f:
            f.write(b'{"seq": 2')
        with open(os.path.join(self.d, ".state.json.tmp.99999"), "w") as f:
            f.write("stale")
        self.assertEqual(self.append(2)["seq"], 2)
        self.assertEqual(self.channel()["torn"], 1)
        self.assert_layout()

    def test_missing_state(self):
        for i in range(1, 10):
            self.append(i, config={"segment_bytes": 1, "keep_segments": 2}, capture="sample", source={"node": "a", "round": i})
        os.unlink(os.path.join(self.d, "state.json"))
        self.assertEqual(self.append(10, config={"segment_bytes": 1, "keep_segments": 2})["seq"], 10)
        self.assertEqual(store.load_state(self.d)["sample"], {"a": 9})
        self.assertGreater(self.channel()["dropped_upto"], 0)
        self.assert_layout()

    def test_destination_exists(self):
        self.append(config={"segment_bytes": 1})
        dest = os.path.join(self.d, "obs.000000000001.jsonl")
        with open(dest, "w") as f:
            f.write("collision\n")
        before = self.contents()
        state = store.load_state(self.d)
        self.assertEqual(self.append(2)["why"], "unknown")
        self.assertEqual(self.contents(), before)
        self.assertEqual(store.load_state(self.d), state)

    def test_fast_path(self):
        self.append()
        with mock.patch.object(store, "_scan", side_effect=AssertionError("不應掃已知活躍段")):
            self.assertIsNotNone(store.recover(self.d, node="n"))
        self.assertEqual(self.channel()["next_seq"], 2)


class TestRotation(EventsCase):
    def test_obs_retention(self):
        for i in range(1, 40):
            self.assertTrue(self.append(i, config={"segment_bytes": 1})["ok"])
            self.assert_layout()
        self.assertGreater(self.channel()["dropped_upto"], 0)

    def test_must_full_ack(self):
        for i in range(1, 6):
            self.assertTrue(self.append(i, ch="must", config={"segment_bytes": 1})["ok"])
        before = self.contents()
        for _ in range(2):
            self.assertEqual(self.append(6, ch="must")["why"], "full")
            self.assertEqual(self.contents(), before)
        self.assertEqual(self.channel("must")["refused"], 2)
        self.assertEqual(store.ack(self.d, 2), 2)
        self.assertEqual(self.contents(), before)  # ack 本身不清段。
        self.assertTrue(self.append(6, ch="must")["ok"])
        self.assertEqual(self.channel("must")["dropped_upto"], 2)
        self.assert_layout("must")
        store.ack(self.d, 100)
        self.assertTrue(self.append(7, ch="must")["ok"])
        self.assert_layout("must")


class TestCrash(EventsCase):
    def crash_cycles(self, point, ch, ack=False):
        env = dict(os.environ, DRIVER_ACK="1" if ack else "")
        progress = os.path.join(self.root, "progress.json")
        small = ch == "must" and not ack   # 只測寫入窗口；輪替／刪段要夠多筆才打得到
        n = 18 if small else 70
        killed = []
        for _ in range(3):
            target = (read_json(progress) or 0) + (2 if small else 12)
            p = subprocess.run([sys.executable, "-c", DRIVER, self.d, ch, str(n), str(target), point, progress],
                               capture_output=True, text=True, timeout=20, env=env)
            self.assertEqual(p.returncode, -9, p.stderr)
            done = read_json(progress) or 0
            self.assertLess(done, n)
            self.assertGreaterEqual(done + 1, target)
            killed.append(done + 1)
            # 每次被殺後立即恢復並驗不變量（不等整批續跑完才看，astra E1 #7）
            self.assertIsNotNone(store.recover(self.d, node="n"))
            self.assert_layout(ch)
        p = subprocess.run([sys.executable, "-c", DRIVER, self.d, ch, str(n), "0", "", progress],
                           capture_output=True, text=True, timeout=20, env=env)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(read_json(progress), n)
        self.assert_layout(ch)
        c, rows = self.channel(ch), self.rows(ch)
        ids = [r["event_id"] for r in rows]
        self.assertEqual(len(ids), len(set(ids)))
        with open(progress + ".ok") as f:
            oks = [tuple(map(int, line.split())) for line in f]
        self.assertEqual([i for i, seq, dup in oks], list(range(1, n + 1)))
        for i, seq, dup in oks:
            if seq > c["dropped_upto"]:
                self.assertEqual(sum(r["event_id"] == "e%d" % i and r["seq"] == seq for r in rows), 1)
        if point == "events:after-partial":
            self.assertEqual(c["torn"], 3)
        if point == "events:after-append":
            self.assertEqual([i for i, seq, dup in oks if dup], killed)

    def test_after_append(self):
        self.crash_cycles("events:after-append", "must")

    def test_after_partial(self):
        self.crash_cycles("events:after-partial", "must")

    def test_after_rename(self):
        self.crash_cycles("events:after-rename", "obs")

    def test_after_unlink(self):
        self.crash_cycles("events:after-unlink", "obs")

    def test_after_unlink_must_acked(self):
        """must 有消費者跟上 ack：輪替刪已確認段時被殺 ×3，不丟未確認、不重 seq。"""
        self.crash_cycles("events:after-unlink", "must", ack=True)

    def test_after_rename_must_acked(self):
        self.crash_cycles("events:after-rename", "must", ack=True)


class TestTornCount(EventsCase):
    """V2：剛修掉半行就被殺，torn 不少記也不多記（截前、截後兩個點各 ×3）。"""
    def cycles(self, point):
        active = os.path.join(self.d, "must.active.jsonl")
        for k in range(1, 4):
            self.assertTrue(self.append(k, ch="must")["ok"])
            with open(active, "ab") as f:
                f.write(b'{"seq": 99, "half')
            code = "import sys; sys.path.insert(0, %r); import aos7_events_store as s; s.recover(%r, node='n')" % (EVENTS, self.d)
            p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=20,
                               env=dict(os.environ, AOS7_TEST_CRASH=point))
            self.assertEqual(p.returncode, -9, p.stderr)
            self.assertIsNotNone(store.recover(self.d, node="n"))
            c = self.channel("must")
            self.assertEqual(c["torn"], k)
            self.assertNotIn("torn_cut", c)
            self.assert_layout("must")
        self.assertTrue(self.append(4, ch="must")["ok"])
        self.assertEqual(self.channel("must")["torn"], 3)

    def test_kill_before_truncate(self):
        self.cycles("events:after-torn-save")

    def test_kill_after_truncate(self):
        self.cycles("events:after-truncate")

    def test_stale_cut_not_reused(self):
        """截後被殺留下截點標記；下一次寫入在同一點又撕裂被殺，仍要再記一次。"""
        active = os.path.join(self.d, "must.active.jsonl")
        self.append(1, ch="must")
        with open(active, "ab") as f:
            f.write(b'{"half')
        rec = "{'kind': 't', 'capture': 'published', 'event_id': 'e2', 'source': {}, 'payload': {}}"
        for point, code in (("events:after-truncate", "s.recover(%r, node='n')" % self.d),
                            ("events:after-partial", "s.append(%r, 'must', %s, node='n')" % (self.d, rec))):
            p = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, %r); "
                                "import aos7_events_store as s; " % EVENTS + code],
                               capture_output=True, text=True, timeout=20, env=dict(os.environ, AOS7_TEST_CRASH=point))
            self.assertEqual(p.returncode, -9, p.stderr)
        self.assertIsNotNone(store.recover(self.d, node="n"))
        self.assertEqual(self.channel("must")["torn"], 2)
        self.assertTrue(self.append(2, ch="must")["ok"])
        self.assert_layout("must")

    def test_bad_cut(self):
        self.append()
        st = read_json(os.path.join(self.d, "state.json"))
        st["channels"]["obs"]["torn_cut"] = "x"
        write_json(os.path.join(self.d, "state.json"), st)
        self.assertIsNone(store.recover(self.d, node="n"))


class TestReviewRegressions(EventsCase):
    """astra E1 審查的回歸：快速路徑重用 seq、清段先刪了目的檔、rename 後多一段、keep 上限。"""

    def test_rotation_then_kill_does_not_reuse_seq(self):
        """must 單筆成段、ack 後輪替清段，寫等長新筆後被殺：恢復不可走快速路徑重用 seq（#1）。"""
        cfg = {"segment_bytes": 1, "keep_segments": 4}
        self.assertEqual(self.append(1, ch="must", config=cfg)["seq"], 1)
        store.ack(self.d, 1)
        code = ("import sys, os; sys.path.insert(0, %r); import aos7_events_store as s; "
                "os.environ['AOS7_TEST_CRASH'] = 'events:after-append'; "
                "s.append(%r, 'must', {'kind': 't', 'capture': 'published', 'event_id': 'e2', 'source': {}, "
                "'payload': {'i': 2}}, node='n')") % (EVENTS, self.d)
        p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=20)
        self.assertEqual(p.returncode, -9, p.stderr)
        r2 = self.append(2, ch="must")
        self.assertEqual((r2["seq"], r2["dup"]), (2, True))
        self.assertEqual(self.append(3, ch="must")["seq"], 3)
        rows = self.rows("must")
        self.assertEqual([r["event_id"] for r in rows if r["seq"] >= 2], ["e2", "e3"])
        self.assertEqual(len({r["seq"] for r in rows}), len(rows))

    def test_cleanup_never_deletes_destination(self):
        """目的段已存在時，must 容量清理前就回 unknown，目的檔原樣（#2）。"""
        self.append(1, ch="must", config={"segment_bytes": 1, "keep_segments": 1})
        dest = os.path.join(self.d, "must.000000000001.jsonl")
        with open(dest, "w") as f:
            f.write('{"seq": 1, "event_id": "other"}\n')
        before = self.contents()
        self.assertEqual(self.append(2, ch="must")["why"], "unknown")
        self.assertEqual(self.contents(), before)

    def test_rename_kill_with_full_obs_recovers_to_limit(self):
        """obs 已 4 段，rename 後被殺：下一次恢復就清回 4 段，檔數 ≤12（#3）。"""
        cfg = {"segment_bytes": 1, "keep_segments": 4}
        for i in range(1, 6):
            self.append(i, config=cfg)
        for i in range(1, 6):
            self.append(i, ch="must", config=cfg)
        self.assertEqual(len(self.channel()["segments"]), 4)
        code = ("import sys, os; sys.path.insert(0, %r); import aos7_events_store as s; "
                "os.environ['AOS7_TEST_CRASH'] = 'events:after-rename'; "
                "s.append(%r, 'obs', {'kind': 't', 'capture': 'published', 'event_id': 'e9', 'source': {}, "
                "'payload': {'i': 9}}, node='n')") % (EVENTS, self.d)
        p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=20)
        self.assertEqual(p.returncode, -9, p.stderr)
        self.assertEqual(self.append(9, ch="must")["why"], "full")   # 另一通道的 append 也會恢復
        self.assertLessEqual(len(os.listdir(self.d)), 12)
        self.assert_layout("obs")

    def test_keep_cap(self):
        """keep_segments 上限 4（12 檔硬約束）：store 拒絕、CLI 用法錯（#6）。"""
        with self.assertRaises(ValueError):
            self.append(1, config={"keep_segments": 5})
        p = subprocess.run([sys.executable, os.path.join(EVENTS, "aos7-events"), "--keep", "5"],
                           capture_output=True, text=True, timeout=20)
        self.assertEqual(p.returncode, 2, p.stderr)


class TestSampler(EventsCase):
    def setUp(self):
        super().setUp()
        node = os.path.join(self.root, "n")
        task = os.path.join(node, ".aos", "tasks", "events")
        os.makedirs(task)
        self.me = {"root": self.root, "node": node, "node_id": "n", "task": task}
        self.args = argparse.Namespace(src=None, status=False, daemon_log=False, out=self.d,
                                       keep=4, segment_bytes=4096)
        self.st = store.recover(self.d, node="n", config={"segment_bytes": 4096})
        self.lr = os.path.join(node, ".aos", "last-round.json")
        self.log = os.path.join(self.root, ".aosd", "log.jsonl")
        os.makedirs(os.path.dirname(self.log))

    def once(self, r=None, **extra):
        if r is not None:
            write_json(self.lr, dict(extra, round=r))
        return sampler.once(self.me, self.args, lambda p: None, self.st)

    def write_log(self, data, mode="ab"):
        with open(self.log, mode) as f:
            f.write(data)

    def run_sampler(self, point="", *args):
        write_json(os.path.join(self.me["task"], "tock.json"), {"round": 1, "run": 1})
        env = dict(os.environ, AOS7_ROOT=self.root, AOS7_NODE=self.me["node"], AOS7_NODE_ID="n",
                   AOS7_TASK=self.me["task"], AOS7_TID="events#1", AOS7_RUN="1", AOS7_TEST_CRASH=point)
        return subprocess.run([sys.executable, os.path.join(EVENTS, "aos7-events"), "--rounds", "1", "--out", self.d, *args],
                              env=env, capture_output=True, text=True, timeout=20)

    def test_300_rounds(self):
        for r in range(1, 301):
            self.once(r, pad="x" * 500)
            self.assert_layout()
        self.assertGreater(self.channel()["dropped_upto"], 0)
        self.assertEqual(store.load_state(self.d)["sample"], {"n": 300})

    def test_gaps_and_reset(self):
        for r in (1, 2, 5, 1):
            self.once(r)
        gaps = [r for r in self.rows() if r["kind"] == "gap"]
        self.assertEqual(gaps[0]["payload"], {"from": 3, "to": 4, "why": "round_skip"})
        self.assertEqual(gaps[1]["payload"], {"from": 5, "to": 1, "why": "source_reset_unknown"})
        self.assertEqual(gaps[1]["source"]["round"], 0)
        self.assertEqual(self.rows()[-1]["payload"]["last_round"]["round"], 1)
        self.once(1)
        self.assertEqual(len(self.rows()), 6)

    def test_status_and_invalid_source(self):
        write_json(self.lr, {"round": True})
        self.assertFalse(self.once())
        self.args.status = True
        path = os.path.join(self.root, ".aosd", "status.json")
        write_json(path, {"last_event": {"ev": "start"}})
        self.once()
        self.once()
        self.assertEqual(len(self.rows()), 1)
        self.st = store.recover(self.d, node="n")  # 重起：去重鍵在 state.status_last，不再記一筆。
        self.once()
        self.assertEqual(len(self.rows()), 1)
        write_json(path, {"last_event": {"ev": "stop"}})
        self.once()
        self.assertEqual(len(self.rows()), 2)

    def test_status_dedup_across_restarts(self):
        """V2：同一 status 事件跨真重起（子程序 ×3）、state 遺失重推、舊 state 缺欄位都只記一筆。"""
        write_json(os.path.join(self.root, ".aosd", "status.json"), {"last_event": {"ev": "start", "n": 1}})
        for _ in range(3):
            self.assertEqual(self.run_sampler("", "--status").returncode, 0)
        self.assertEqual([r["kind"] for r in self.rows()].count("daemon.status"), 1)
        st = read_json(os.path.join(self.d, "state.json"))
        del st["status_last"]   # 舊 state 缺欄位視為空：記一次後補上
        write_json(os.path.join(self.d, "state.json"), st)
        for _ in range(2):
            self.assertEqual(self.run_sampler("", "--status").returncode, 0)
        self.assertEqual([r["kind"] for r in self.rows()].count("daemon.status"), 2)
        os.unlink(os.path.join(self.d, "state.json"))   # state 遺失：從留存紀錄推回
        self.assertEqual(self.run_sampler("", "--status").returncode, 0)
        self.assertEqual([r["kind"] for r in self.rows()].count("daemon.status"), 2)
        self.assertEqual(store.load_state(self.d)["status_last"], store.status_key({"ev": "start", "n": 1}))

    def test_snapshot_truncated_and_retry(self):
        self.once(1, pad="漢" * 30000)
        self.assertEqual(self.rows()[0]["payload"], {"last_round": {"round": 1}, "truncated": True})
        with mock.patch.object(store, "append", return_value={"ok": False, "why": "unknown"}):
            self.assertFalse(self.once(5))
        self.assertEqual(self.st["sample"]["n"], 1)
        self.once(5)
        self.assertEqual(len(self.rows()), 3)

    def test_log_offsets(self):
        self.args.daemon_log = True
        self.write_log(b'{"i": 1}\ntrue\nunparsed\npartial')
        self.once()
        first = self.rows()
        self.assertEqual([r["payload"] for r in first], [{"i": 1}, True, {"unparsed": "unparsed\n"}])
        self.write_log(b'\n{"i": 2}\n')
        self.once()
        rows = self.rows()
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[-1]["payload"], {"i": 2})
        self.assertEqual(rows[0]["source"]["off_from"], 0)
        for a, b in zip(rows, rows[1:]):
            self.assertEqual(a["source"]["off_to"], b["source"]["off_from"])
        self.assertEqual(store.load_state(self.d)["daemon_log"]["offset"], os.stat(self.log).st_size)
        before = open(self.log, "rb").read()
        self.once()
        self.assertEqual(open(self.log, "rb").read(), before)
        self.assertEqual(len(self.rows()), 5)

    def test_log_replaced_and_shorter(self):
        self.args.daemon_log = True
        self.write_log(b'{"long": "abcdefghijk"}\n')
        self.once()
        old = os.stat(self.log).st_ino
        # 保留舊 fd，防止檔系統立即重用 inode。
        with open(self.log, "rb"):
            os.unlink(self.log)
            self.write_log(b'1\n')
            self.assertNotEqual(os.stat(self.log).st_ino, old)
            self.once()
        self.write_log(b'\n', "wb")
        self.once()
        gaps = [r for r in self.rows() if r["kind"] == "gap"]
        self.assertEqual(len(gaps), 2)
        for gap in gaps:
            self.assertEqual(gap["payload"]["why"], "source_reset_unknown")
            self.assertEqual(gap["source"]["off_to"], 0)
        self.assertEqual(self.rows()[-1]["source"]["off_from"], 0)

    def test_log_too_large_and_failure(self):
        self.args.daemon_log = True
        data = json.dumps({"pad": "x" * 70000}).encode() + b"\n"
        self.write_log(data)
        with mock.patch.object(store, "append", return_value={"ok": False, "why": "unknown"}):
            self.once()
        self.assertIsNone(self.st["daemon_log"])
        self.once()
        self.assertEqual(self.rows()[0]["payload"], {"too_large": True, "bytes": len(data)})

    def test_crash_gap(self):
        self.once(1)
        for r in (5, 9, 13):
            write_json(self.lr, {"round": r})
            self.assertEqual(self.run_sampler("events:sample-after-gap").returncode, -9)
            self.assertEqual(self.run_sampler().returncode, 0)
            rows = self.rows()
            self.assertEqual(sum(x["kind"] == "gap" and x["source"]["round"] == r - 1 for x in rows), 1)
            self.assertEqual(sum(x["kind"] == "round.observed" and x["source"]["round"] == r for x in rows), 1)

    def test_crash_snapshot(self):
        for r in (1, 2, 3):
            write_json(self.lr, {"round": r})
            self.assertEqual(self.run_sampler("events:after-append").returncode, -9)
            self.assertEqual(self.run_sampler().returncode, 0)
        self.assertEqual([r["source"]["round"] for r in self.rows()], [1, 2, 3])

    def test_crash_log(self):
        for i in range(3):
            self.write_log((json.dumps({"i": i}) + "\n").encode())
            self.assertEqual(self.run_sampler("events:after-append", "--daemon-log").returncode, -9)
            self.assertEqual(self.run_sampler("", "--daemon-log").returncode, 0)
        rows = self.rows()
        self.assertEqual([r["payload"]["i"] for r in rows], [0, 1, 2])
        self.assertEqual(rows[0]["source"]["off_from"], 0)
        for a, b in zip(rows, rows[1:]):
            self.assertEqual(a["source"]["off_to"], b["source"]["off_from"])
        self.assertEqual(rows[-1]["source"]["off_to"], os.stat(self.log).st_size)


if __name__ == "__main__":
    unittest.main()
