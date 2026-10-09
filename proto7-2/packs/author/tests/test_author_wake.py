"""EF2：作者編出的 step 派工後使用既有 daemon wake。"""
import json
from pathlib import Path
import sys

PACK = Path(__file__).resolve().parents[1]
TOP = PACK.parents[1]
sys.path[:0] = [str(TOP / "tests"), str(PACK), str(PACK / "tests")]
from base import CoreCase, DaemonCase  # noqa: E402
from test_author import EXAMPLE, TestAuthorHelpers  # noqa: E402
import aos7_author as author  # noqa: E402
import aos7_author_pub as pub  # noqa: E402
import aos7_step  # noqa: E402


class TestAuthorWakeCore(CoreCase):
    def test_compile_steps_enables_wake(self):
        candidate = json.loads((EXAMPLE / "valid.json").read_bytes())
        table, _ = author.compile_steps(candidate, author.load_toolcards(), "csv1_test")
        self.assertIs(table["options"]["wake"], True)
        issues = aos7_step.check(table)
        self.assertEqual([i for i in issues if i["level"] == "error"], [], issues)


class TestAuthorWakeDaemon(TestAuthorHelpers, DaemonCase):
    def test_each_dispatch_wakes_daemon(self):
        # 不寫 timeline.json，使用固定 1000 ms interval／early_tock=false 預設。
        node = self.mknode(timeline=False)
        aosd = Path(self.root, ".aosd")
        aosd.mkdir()
        (aosd / "log.on").touch()
        self.start_daemon(register=["a"])
        self.register(node)
        version = self.propose(node)
        self.good(pub.publish(node, "csv1"))
        self.wait_job(node, version["job"])
        records = [json.loads(line) for line in (aosd / "log.jsonl").read_text().splitlines()]
        wakes = [r for r in records if r.get("ev") == "ctl" and r.get("op") == "wake"
                 and (r.get("by") or "").startswith("a:author-" + version["job"])]
        self.assertGreaterEqual(len(wakes), 2, records)
        self.assertTrue(all(r.get("ok") is True and r.get("node") == "a" for r in wakes), wakes)
