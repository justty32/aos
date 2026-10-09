"""索引、選擇去重與掛載的端到端驗證。"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

TOP = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(TOP / "tests"), str(TOP / "modules/skills")]
from base import CoreCase
import _proc
from aos7_fs import read_json, write_json
from aos7_skills import build, parse_answer

CLI = TOP / "modules/skills/aos7-skills"
BUDGET = TOP / "packs/budget/bin/aos7-budget"


class TestSkills(CoreCase):
    def setUp(self):
        super().setUp()
        self.node = Path(self.mknode(tasks=[{"name": "work", "argv": ["true"], "x": {"keep": 7}}]))
        (Path(self.root) / ".aosd").mkdir()
        self.skills = self.node / "skills"

    def skill(self, name, description="資料", text=None, parent=None):
        directory = (parent or self.skills) / name
        directory.mkdir(parents=True)
        (directory / "SKILL.md").write_text(text or f'---\nname: {name}\ndescription: "{description}"\n---\n正文祕密\n')
        return directory

    def runcli(self, *args, binary=CLI, cwd=None):
        p = subprocess.Popen([sys.executable, str(binary), *map(str, args)], cwd=cwd,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
        _proc.track(self, p, group=True)
        out, err = p.communicate(timeout=20)
        return p.returncode, out.strip(), err

    def test_index_mixed_and_good(self):
        self.skill("beta", "英文 tests")
        self.skill("alpha", "中文資料")
        (self.skills / "beta/scripts").mkdir()
        for name, text in {"bad-front": "正文", "bad-desc": "---\nname: bad-desc\n---",
                           "bad-name": "---\nname: other\ndescription: 有\n---"}.items():
            self.skill(name, text=text)
        self.skill(".hidden")
        (self.skills / "file").write_text("略過")
        result = build(self.node)
        self.assertFalse((self.skills / "index.json").exists())
        rc, out, err = self.runcli("index", self.node)
        self.assertEqual(rc, 1, err)
        self.assertEqual(out.splitlines(), ["- alpha: 中文資料", "- beta: 英文 tests"])
        obj = read_json(self.skills / "index.json")
        self.assertEqual(obj, result)
        self.assertEqual(obj["lines"], out.splitlines())
        self.assertEqual(set(obj["rejected"]), {"bad-front", "bad-desc", "bad-name"})
        self.assertEqual(err.count("拒收"), 3)
        self.assertTrue(obj["skills"]["beta"]["scripts"])
        self.assertFalse(obj["skills"]["alpha"]["scripts"])
        good = Path(self.mknode("good"))
        self.skill("alpha", parent=good / "skills")
        self.assertEqual(self.runcli("index", good)[0], 0)

    def test_symlink_and_must(self):
        outside = self.skill("linked", parent=Path(self.root) / "shared")
        self.skills.mkdir()
        (self.skills / "linked").symlink_to(outside, target_is_directory=True)
        write_json(str(self.skills / "must.json"), {"派單": "linked", "壞單": ["linked", "missing"]})
        self.assertEqual(self.runcli("index", self.node)[0], 1)
        obj = read_json(self.skills / "index.json")
        self.assertIn("linked", obj["skills"])
        self.assertIn("missing", obj["rejected"]["must.json"])
        md = (self.skills / "MUST.md").read_text()
        self.assertIn("| 任務類型 | 必用 skill | SKILL.md |", md)
        self.assertIn("| 派單 | linked | skills/linked/SKILL.md |", md)
        self.assertNotIn("壞單", md)
        (self.skills / "must.json").unlink()
        self.assertEqual(self.runcli("index", self.node)[0], 0)
        self.assertFalse((self.skills / "MUST.md").exists())

    def test_missing_skills(self):
        self.assertEqual(self.runcli("index", self.node)[0], 2)
        self.assertEqual(self.runcli("index", self.node / "missing")[0], 2)

    def test_pick_fake_reuses_receipt(self):
        wanted = self.skill("coding", "python tests") / "SKILL.md"
        self.skill("writing", "中文文章")
        write_json(str(self.skills / "index.json"), {"lines": ["過期索引"]})
        write_json(str(self.node / ".aos/round.json"), {"round": 5, "open": False})
        bd = self.node / "budget/llm"
        write_json(str(bd / "grant.json"), {"v": 1, "grant": "g1", "budget": "llm", "holder": "skills",
                   "resource": "llm.tokens", "gateway": "llm.fake", "amount": 100000,
                   "clock": "completed_tock", "from": 0, "until": 1000, "delegate": False})
        self.assertEqual(self.runcli("init", "budget/llm", binary=BUDGET, cwd=self.node)[0], 0)
        rc, out, err = self.runcli("pick", self.node, "python tests")
        self.assertEqual((rc, out), (3, ""))
        self.assertIn("帳任務沒在跑", err)
        self.assertFalse((self.node / "llmcall").exists())
        (self.skills / ".pick/log.jsonl").unlink()
        p = subprocess.Popen([sys.executable, str(BUDGET), "ledger", "budget/llm"], cwd=self.node,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        _proc.track(self, p, group=True)
        self.wait_for(lambda: (bd / "ledger.lock").exists())
        for _ in range(2):
            rc, out, err = self.runcli("pick", self.node, "python tests")
            self.assertEqual((rc, out), (0, str(wanted.absolute())), err)
        logs = [json.loads(s) for s in (self.skills / ".pick/log.jsonl").read_text().splitlines()]
        self.assertEqual(len(logs), 2)
        self.assertEqual(logs[0]["call"], logs[1]["call"])
        self.assertEqual(read_json(self.node / "llmcall/fake-remote.json")["sends"][logs[0]["call"]], 1)
        self.assertEqual(set(logs[0]), {"at", "via", "call", "q", "answer", "picked", "used", "rc", "elapsed"})
        self.assertEqual(logs[0]["via"], "llmcall")
        self.assertGreater(logs[0]["used"], 0)
        self.assertEqual(logs[1]["picked"], "coding")
        self.assertGreater(logs[0]["elapsed"], 0)
        self.assertEqual(self.runcli("pick", self.node, "zzzz")[0:2], (1, "none"))

    def test_pick_local_without_budget(self):
        """第一次跑：沒有 budget/llm 就本機關鍵字挑，不碰帳與 llmcall；明給 --budget 仍要帳。"""
        wanted = self.skill("coding", "python tests") / "SKILL.md"
        self.skill("writing", "中文文章")
        rc, out, err = self.runcli("pick", self.node, "python tests")
        self.assertEqual((rc, out), (0, str(wanted.absolute())), err)
        self.assertIn("本機挑選", err)
        self.assertEqual(self.runcli("pick", self.node, "zzzz")[0:2], (1, "none"))
        self.assertFalse((self.node / "llmcall").exists())
        self.assertFalse((self.node / "budget").exists())
        logs = [json.loads(s) for s in (self.skills / ".pick/log.jsonl").read_text().splitlines()]
        self.assertEqual([(g["via"], g["picked"], g["rc"]) for g in logs], [("local", "coding", 0), ("local", None, 1)])
        self.assertTrue(logs[0]["call"].startswith("local-"))
        self.assertNotEqual(logs[0]["call"], logs[1]["call"])
        rc, out, err = self.runcli("pick", self.node, "python tests", "--budget", "budget/llm")
        self.assertEqual((rc, out), (2, ""))
        self.assertIn("grant", err)
        (self.node / "budget/llm").mkdir(parents=True)
        self.assertEqual(self.runcli("pick", self.node, "python tests")[0], 2)

    def test_parse_answer(self):
        for text in ('`ALPHA`', '"Alpha"', "'alpha'", "alpha\nbeta", "ALPHA extra", "```alpha```", " none "):
            with self.subTest(text=text):
                self.assertEqual(parse_answer(text, {"alpha"}), "none" if text.strip() == "none" else "alpha")
        for text in ("unknown", ""):
            with self.assertRaisesRegex(ValueError, "索引外"):
                parse_answer(text, {"alpha"})

    def test_mount_preserves_tasks_and_refuses(self):
        self.skill("alpha")
        path = self.node / ".aos/tasks.json"
        before = read_json(path)
        self.assertEqual(self.runcli("mount", self.node, "alpha", "work")[0:2], (0, "skill-alpha"))
        before["tasks"][0]["mounts"] = {"skill-alpha": "a/skills/alpha"}
        self.assertEqual(read_json(path), before)
        snapshot = path.read_bytes()
        self.assertEqual(self.runcli("mount", self.node, "alpha", "absent")[0], 2)
        self.assertEqual(path.read_bytes(), snapshot)
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        external = self.skill("external", parent=Path(outside.name))
        (self.skills / "external").symlink_to(external, target_is_directory=True)
        self.assertIn("external", build(self.node)["skills"])
        rc, _, err = self.runcli("mount", self.node, "external", "work")
        self.assertEqual(rc, 2)
        self.assertIn("skill 在空間外", err)
        self.assertEqual(path.read_bytes(), snapshot)
        path.write_text("broken")
        self.assertEqual(self.runcli("mount", self.node, "alpha", "work")[0], 3)
        self.assertEqual(path.read_text(), "broken")
