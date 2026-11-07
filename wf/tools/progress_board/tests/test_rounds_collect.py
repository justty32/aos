"""Verify round posting, inference, complete collection, answers, and mounted reports offline."""

import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import collect
import assets
from rounds import report_urls


class RoundCollection(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aos_rounds_")
        self.addCleanup(self.tmp.cleanup)
        self.board = Path(self.tmp.name)
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, {"AOS_PROGRESS_DIR": str(self.board)}).start()
        self.now = dt.datetime.now().astimezone()
        self.cfg = {"aos_repo": str(self.board), "repos": [], "lines": [],
                    "summary": {"enabled": False, "eli5_enabled": False}}

    def event(self, text, index=0, **values):
        return {"ts": (self.now - dt.timedelta(days=10) + dt.timedelta(seconds=index)).isoformat(),
                "line": "alpha", "status": "progress", "text": text, "links": [], **values}

    def test_inference_carry_first_match_explicit_and_line_isolation(self):
        events = [self.event("unmarked"), self.event("批 4a first then 第三輪", 1),
                  self.event("carry", 2), self.event("第一輪", 3, round="chosen"),
                  self.event("第二輪 then 批5", 4)]
        state = collect.line_state({"id": "alpha"}, events, self.cfg, self.now)
        self.assertEqual([r["name"] for r in state["rounds"]],
                         ["未分輪", "批 4a", "chosen", "第二輪"])
        self.assertEqual(state["rounds"][1]["events_count"], 2)
        self.assertEqual(state["current_round"], "第二輪")
        empty = collect.line_state({"id": "other"}, [], self.cfg, self.now)
        self.assertEqual(empty["rounds"], [])
        self.assertIsNone(empty["current_round"])

    def test_complete_history_counts_and_old_answer_state(self):
        events = [self.event("第一輪", i) for i in range(12)]
        events[1].update(status="ask", id="q1", options=[], recommend=None)
        events[2].update(status="ask", id="q2", options=[], recommend=None)
        events[3]["status"] = "decision"
        events[-1]["status"] = "blocked"
        state = collect.line_state({"id": "alpha"}, events, self.cfg, self.now,
                                   [{"id": "q1"}])
        item = state["rounds"][0]
        self.assertEqual(len(state["events"]), 8)
        self.assertEqual(len(item["events"]), 12)
        self.assertEqual(item["events_count"], 12)
        self.assertEqual(item["decisions_count"], 1)
        self.assertEqual(item["counts"]["ask"], 2)
        self.assertEqual(item["asks_open"], 1)
        self.assertTrue(item["blocked"])

    def test_reopened_round_keeps_first_order_and_newest_current(self):
        events = [self.event("第一輪", 0), self.event("第二輪", 1),
                  self.event("第一輪 resumed", 2)]
        state = collect.line_state({"id": "alpha"}, list(reversed(events)), self.cfg, self.now)
        self.assertEqual([item["name"] for item in state["rounds"]], ["第一輪", "第二輪"])
        self.assertEqual(state["current_round"], "第一輪")
        self.assertEqual(state["rounds"][0]["first_ts"], events[0]["ts"])
        self.assertEqual(state["rounds"][0]["last_ts"], events[2]["ts"])
        self.assertEqual(state["rounds"][0]["events"], [dict(events[0], round="第一輪"),
                                                       dict(events[2], round="第一輪")])

    def test_assets_refresh_reference_and_exact_bundled_fallback(self):
        reference = Path("~/Desktop/aos-arknights/assets/style.css").expanduser()
        fallback = assets.ROOT / "web/ak-style.fallback.css"
        bundled = fallback.read_bytes()
        if reference.is_file():
            self.assertEqual(bundled.split(b"\n", 1)[1], reference.read_bytes())
        original = Path.is_file
        def without_reference(path):
            return False if path == reference else original(path)
        with patch.object(Path, "is_file", without_reference):
            assets.copy_assets(self.board)
        target = self.board / "assets/ak-style.css"
        self.assertEqual(target.read_bytes(), bundled)
        target.write_bytes(b"stale CSS")
        with patch.object(Path, "is_file", without_reference):
            assets.copy_assets(self.board)
        self.assertEqual(target.read_bytes(), bundled)
        if reference.is_file():
            assets.copy_assets(self.board)
            self.assertEqual(target.read_bytes(), reference.read_bytes())

    def test_safe_report_mapping(self):
        site = self.board / "site"
        site.mkdir()
        (site / "round1.html").write_text("report")
        cfg = {"sites": [{"mount": "arknights", "dir": str(site)}]}
        line = {"round_pages": {"第一輪": "arknights/round1.html"}}
        self.assertEqual(report_urls(line, "第一輪", cfg)["report_url"], "arknights/round1.html")
        for value in ("arknights/missing.html", "arknights/../round1.html", "/round1.html"):
            line["round_pages"]["第一輪"] = value
            self.assertEqual(report_urls(line, "第一輪", cfg), {})
        outside = self.board / "outside.html"
        outside.write_text("outside")
        (site / "escape.html").symlink_to(outside)
        line["round_pages"]["第一輪"] = "arknights/escape.html"
        self.assertEqual(report_urls(line, "第一輪", cfg), {})

    def test_post_round_all_statuses_and_reject_empty(self):
        script = Path(__file__).resolve().parents[2] / "progress_post.sh"
        for status in collect.STATUSES:
            result = subprocess.run([str(script), "alpha", status, "text", "--round", "第一輪"],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        events = collect.read_jsonl(self.board / "data/progress.jsonl")
        self.assertEqual(len(events), len(collect.STATUSES))
        self.assertTrue(all(event["round"] == "第一輪" for event in events))
        result = subprocess.run([str(script), "alpha", "done", "text", "--round", ""],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)

    def test_collect_static_assets_and_grouped_lines_offline(self):
        (self.board / "data").mkdir()
        events = [self.event("第一輪"), self.event("plain", line="beta")]
        (self.board / "data/progress.jsonl").write_text("\n".join(map(json.dumps, events)))
        with patch("collect.host_state", return_value={"load1": 0, "mem_avail_mb": 1, "codex_procs": 0}), \
                patch("eli5.eli5_state", return_value={"main": None}):
            state = collect.collect(self.board, self.cfg)
        self.assertEqual([line["current_round"] for line in state["lines"]], ["第一輪", "未分輪"])
        self.assertTrue((self.board / "assets/ak-style.css").is_file())


if __name__ == "__main__":
    unittest.main()
