#!/usr/bin/env python3
"""評分器的單元測試（不叫模型、不需要真 corpus）：python -m unittest test_eval -v"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import evidence_check as ec  # noqa: E402
import judge  # noqa: E402
import mech_check  # noqa: E402
import run_metrics  # noqa: E402

SRC = "\n".join([
    "[name=\"老法官\"]况且，一桩罪不至死，十桩呢？",     # L1
    "莱昂图索：让人意外的是您，罗索阁下。",               # L2
    "阿米娅：这种事由不得我去天真什么，陈长官。",         # L3
    "高登：我们的账一笔勾销。",                           # L4
    "米莎：我一定会......",                               # L5
    "米莎：让碎骨活过来。",                               # L6
])


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        d = self.tmp / "corpus/extracted/story"
        d.mkdir(parents=True)
        (d / "story_x.txt").write_text(SRC + "\n", encoding="utf-8")
        (d / "act17mini_熔炉“还魂”记.md").write_text("甲\n乙\n", encoding="utf-8")
        self.corpus = ec.Corpus(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def check(self, table: str):
        f = self.tmp / "e.md"
        f.write_text("| 節點 | 出處 | 內容 |\n|---|---|---|\n" + table, encoding="utf-8")
        return [r["status"] for r in ec.check_file(self.corpus, f)["rows"]][1:]  # 去掉表頭那列（skip）


class TestEvidence(Base):
    def test_ok_and_speaker_tag(self):
        self.assertEqual(self.check("| a | `story_x.txt` L1-L2 | 「老法官」說「罪不至死」 |\n"), ["ok"])

    def test_same_file_inherit_and_variants(self):
        # 第二列沒寫檔名＝沿用；「什麼」不能被原文轉壞；帳/账 異體
        rows = self.check("| a | `story_x.txt` L1 | x |\n| b | 同檔 L3-4 | 「由不得我去天真什麼」「帳一筆勾銷」 |\n")
        self.assertEqual(rows, ["ok", "ok"])

    def test_out_of_bounds(self):
        self.assertEqual(self.check("| a | `story_x.txt` L5-L99 | x |\n"), ["超界"])

    def test_missing_file_and_no_file(self):
        self.assertEqual(self.check("| a | `nope.txt` L1 | x |\n"), ["檔不存在"])
        self.assertEqual(self.check("| a | L1 | x |\n"), ["無檔名"])

    def test_quote_outside_range_and_missing(self):
        self.assertEqual(self.check("| a | `story_x.txt` L1 | 「一笔勾销」 |\n"), ["引文在範圍外"])
        self.assertEqual(self.check("| a | `story_x.txt` L1-L6 | 「完全沒有的話」 |\n"), ["引文找不到"])

    def test_near_quote_across_lines(self):
        # 跨行時中間夾著下一行的 speaker「米莎」，逐字比不到，落在「近似」
        self.assertEqual(self.check("| a | `story_x.txt` L5-L6 | 「我一定會讓碎骨活過來」 |\n"), ["引文近似"])
        self.assertEqual(self.check("| a | `story_x.txt` L6 | 「讓碎骨活過來」 |\n"), ["ok"])
        self.assertEqual(self.check("| a | `story_x.txt` L6 | 「一定會讓碎骨活過來」 |\n"), ["引文近似"])

    def test_bare_continuation_ranges_and_link_ignored(self):
        rows = self.check("| W（另建檔`W.md`） | x | `story_x.txt` L1-2, 5-6 |\n")
        self.assertEqual(rows, ["ok"])
        groups, _ = ec.parse_citations("`story_x.txt` L1-2, 5-6", self.corpus, None)
        self.assertEqual(groups, [("story_x.txt", [(1, 2), (5, 6)])])

    def test_ascii_quotes_in_filename(self):
        self.assertEqual(self.check('| a | act17mini_熔炉"还魂"记.md L1-2 | x |\n'), ["ok"])

    def test_skip_rows_without_line_numbers(self):
        self.assertEqual(self.check("| a | 沒有行號 | x |\n"), ["skip"])


class TestMech(unittest.TestCase):
    def test_whitespace(self):
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / "a.md"
            f.write_text("好 \n\n", encoding="utf-8")
            ok, msg = mech_check.check_whitespace([f])
            self.assertFalse(ok)
            self.assertIn("行尾空白", msg)
            self.assertIn("檔尾多餘空行", msg)
            f.write_text("好\n", encoding="utf-8")
            self.assertTrue(mech_check.check_whitespace([f])[0])


class TestJudgeParse(unittest.TestCase):
    def test_parse(self):
        d = judge.parse_scores('前言 {"coverage":2,"no_invention":1,"boundary":2,"citation":0,"reason":"x"} 後記')
        self.assertEqual(d["total"], 5)
        with self.assertRaises(ValueError):
            judge.parse_scores('{"coverage":3,"no_invention":1,"boundary":2,"citation":0}')


class TestMetrics(unittest.TestCase):
    def test_team_dir(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t) / "run1" / "team"
            log = root / "members" / "w1" / "log"
            log.mkdir(parents=True)
            (log / "usage.1.jsonl").write_text(json.dumps({"at": "2026-09-25T10:00:00+08:00", "model": "m", "ms": 1000,
                                                           "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12}}) + "\n")
            (log / "usage.jsonl").write_text(json.dumps({"at": "2026-09-25T10:00:30+08:00", "model": "m", "ms": 500, "usage": None}) + "\n壞行\n")
            (log / "events.jsonl").write_text("\n".join(json.dumps(e) for e in [
                {"at": "2026-09-25T10:00:01+08:00", "ev": "think_end", "id": "a", "ms": 900},
                {"at": "2026-09-25T10:00:01+08:00", "ev": "think_end", "id": "a", "ms": 900},  # 重複要去掉
                {"at": "2026-09-25T10:00:02+08:00", "ev": "act_end", "id": "b", "ms": 300}]) + "\n")
            tasks = root / "team" / "tasks"
            tasks.mkdir(parents=True)
            (tasks / "t-0001.json").write_text(json.dumps({"status": "done", "created_at": "2026-09-25T09:59:50+08:00",
                                                          "history": [{"at": "2026-09-25T10:01:00+08:00"}]}))
            m = run_metrics.measure(Path(t))
            self.assertEqual((m["calls"], m["total_tokens"], m["calls_without_usage"]), (2, 12, 1))
            self.assertEqual((m["think_ms"], m["act_ms"], m["tasks"]), (900, 300, 1))
            self.assertEqual(m["wall_s"], 70.0)


class TestGolden(unittest.TestCase):
    def test_golden_files_present(self):
        spec = json.loads((HERE / "golden.json").read_text(encoding="utf-8"))
        n = sum(len(b["characters"]) for b in spec["batches"])
        self.assertEqual((len(spec["batches"]), n), (5, 15))
        for f in ec.golden_files():
            self.assertTrue(f.exists(), f)


if __name__ == "__main__":
    unittest.main()
