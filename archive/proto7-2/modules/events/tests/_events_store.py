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


