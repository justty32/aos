"""索引、選擇去重與掛載的端到端驗證。"""
import contextlib
import fcntl
import hashlib
import io
import json
import os
import time
from unittest.mock import patch
import subprocess
import sys
import tempfile
from pathlib import Path

TOP = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(TOP / "tests"), str(TOP / "modules/skills")]
from base import CoreCase
import _proc
import bank
from aos7_fs import read_json, write_json
from aos7_skills import build, parse_answer, local_pick, main

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
        self.assertEqual(len(err.splitlines()), 1)
        for name in ("bad-front", "bad-desc", "bad-name"):
            self.assertIn(name, err)
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
        before = os.listdir(bd)
        start = time.monotonic()
        rc, out, err = self.runcli("pick", self.node, "用技能：python tests")
        self.assertLess(time.monotonic() - start, 1)
        self.assertEqual((rc, out), (1, ""))
        self.assertEqual(len(err.splitlines()), 1)
        self.assertIn("ledger", err)
        self.assertEqual(os.listdir(bd), before)
        self.assertFalse((bd / "ledger.lock").exists())
        self.assertFalse(list((self.skills / ".pick").glob("*.json")))
        self.assertIn("帳任務沒在跑", err)
        self.assertFalse((self.node / "llmcall").exists())
        (self.skills / ".pick/log.jsonl").unlink()
        p = subprocess.Popen([sys.executable, str(BUDGET), "ledger", "budget/llm"], cwd=self.node,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        _proc.track(self, p, group=True)
        self.wait_for(lambda: (bd / "ledger.lock").exists())
        for _ in range(2):
            rc, out, err = self.runcli("pick", self.node, "用技能：python tests")
            self.assertEqual((rc, out), (0, str(wanted.absolute())), err)
        logs = [json.loads(s) for s in (self.skills / ".pick/log.jsonl").read_text().splitlines()]
        self.assertEqual(len(logs), 2)
        self.assertEqual(logs[0]["call"], logs[1]["call"])
        self.assertEqual(read_json(self.node / "llmcall/fake-remote.json")["sends"][logs[0]["call"]], 1)
        self.assertEqual(set(logs[0]), {"at", "via", "call", "q", "answer", "picked", "used", "rc", "elapsed", "score", "why"})
        self.assertEqual(logs[0]["via"], "llmcall")
        self.assertGreater(logs[0]["used"], 0)
        self.assertEqual(logs[1]["picked"], "coding")
        self.assertEqual(err, "")
        self.assertFalse(list((self.skills / ".pick").glob("*.json")))
        self.assertGreater(logs[0]["elapsed"], 0)
        rc, out, err = self.runcli("pick", self.node, "zzzz")
        self.assertEqual((rc, out), (1, "none"))
        self.assertEqual(len(err.splitlines()), 1)
        self.assertIn("換個說法", err)

    def test_pick_local_without_budget(self):
        """第一次跑：沒有 budget/llm 就本機關鍵字挑，不碰帳與 llmcall；明給 --budget 仍要帳。"""
        wanted = self.skill("coding", "python tests") / "SKILL.md"
        self.skill("writing", "中文文章")
        rc, out, err = self.runcli("pick", self.node, "python tests")
        self.assertEqual((rc, out), (0, str(wanted.absolute())), err)
        self.assertEqual(err, "")
        rc, out, err = self.runcli("pick", self.node, "zzzz")
        self.assertEqual((rc, out), (1, "none"))
        self.assertEqual(len(err.splitlines()), 1)
        self.assertIn("換個說法", err)
        self.assertFalse((self.node / "llmcall").exists())
        self.assertFalse((self.node / "budget").exists())
        logs = [json.loads(s) for s in (self.skills / ".pick/log.jsonl").read_text().splitlines()]
        self.assertEqual([(g["via"], g["picked"], g["rc"]) for g in logs], [("local", "coding", 0), ("local", None, 1)])
        self.assertTrue(logs[0]["call"].startswith("local-"))
        self.assertNotEqual(logs[0]["call"], logs[1]["call"])
        rc, out, err = self.runcli("pick", self.node, "用技能：python tests", "--budget", "budget/llm")
        self.assertEqual((rc, out), (2, ""))
        self.assertIn("grant", err)
        (self.node / "budget/llm").mkdir(parents=True)
        self.assertEqual(self.runcli("pick", self.node, "用技能：python tests")[0], 2)

    def test_longtask_local(self):
        self.skills.mkdir()
        for path in (TOP / "modules/skills/library").iterdir():
            (self.skills / path.name).symlink_to(path, target_is_directory=True)
        questions = json.loads((TOP / "modules/skills/examples/bank/longtask.json").read_text())["questions"]
        correct, wrong = 0, 0
        for item in questions:
            rc, out, err = self.runcli("pick", self.node, item["q"])
            got = Path(out).parent.name if out.endswith("SKILL.md") else out
            correct += got == item["want"]
            wrong += got not in (item["want"], "none")
            self.assertEqual(rc, 1 if got == "none" else 0, err)
        self.assertGreaterEqual(correct, 16)
        self.assertEqual(wrong, 0)
        self.assertFalse((self.node / "llmcall").exists())
        logs = [json.loads(s) for s in (self.skills / ".pick/log.jsonl").read_text().splitlines()]
        self.assertTrue(all(g["via"] == "local" for g in logs))

    def test_ledger_routes(self):
        for name, phrase in (("alpha", "測試"), ("beta", "測試、信箱")):
            self.skill(name, text=f"---\nname: {name}\ndescription: 資料\ntriggers: {phrase}\n---\n")
        (self.node / "budget/llm").mkdir(parents=True)
        for q, calls, prefix in (("測試", 1, "平手，問 AI；"), ("用技能：信箱", 1, "題目明說用技能，問 AI；"), ("信箱", 0, "觸發詞："),
                                  ("不要用技能：信箱", 0, "觸發詞："), ("cause skill 信箱", 0, "觸發詞："), ("use skill: 信箱", 1, "題目")):
            with self.subTest(q=q), patch("aos7_skills.ask_ai", return_value=(0, None)) as ask, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["pick", str(self.node), q]), 0)
                self.assertEqual(ask.call_count, calls)
            log = json.loads((self.skills / ".pick/log.jsonl").read_text().splitlines()[-1])
            self.assertEqual(log["via"], "llmcall" if calls else "local")
            self.assertTrue(log["why"].startswith(prefix))
        self.assertFalse((self.node / "budget/llm/grant.json").exists())

    def test_local_rules_and_phrases(self):
        books = {"alpha": {"description": "資料", "triggers": ["test", "test"], "not_for": ["寫測試"]}}
        for q, answer in (("testing", "none"), ("TEST!", "alpha"), ("atest", "none"), ("test2", "none"), ("test 寫測試", "none")):
            with self.subTest(q=q):
                self.assertEqual(local_pick(q, books)["answer"], answer)
        self.assertEqual(local_pick("test test", books)["score"], 1)
        self.assertIn("不適用", local_pick("test 寫測試", books)["why"])
        self.assertEqual(local_pick("python", {"coding": {"description": "python tests"}})["answer"], "none")
        self.assertEqual(local_pick("python", {"python": {"description": "python tests"}})["score"], 2)
        for key in ("triggers", "not_for"):
            for i, value in enumerate(("x" * 65, ",".join(["x"] * 33))):
                name = f"bad-{key.replace('_', '-')}-{i}"
                self.skill(name, text=f"---\nname: {name}\ndescription: 資料\n{key}: {value}\n---\n")
        self.skill("good", text="---\nname: good\ndescription: 資料\ntriggers: test 、 測試,， , inbox\n---\n")
        result = build(self.node)
        self.assertEqual(result["skills"]["good"]["triggers"], ["test", "測試", "inbox"])
        self.assertEqual(result["skills"]["good"]["not_for"], [])
        self.assertEqual(len(result["rejected"]), 4)
        self.assertTrue(all("triggers／not_for 每項 ≤64 字、最多 32 項" in r for r in result["rejected"].values()))

    def test_log_keeps_latest_50(self):
        self.skill("coding", "python tests")
        path = self.skills / ".pick/log.jsonl"
        path.parent.mkdir()
        path.write_text("".join(json.dumps({"old": i}) + "\n" for i in range(60)))
        self.assertEqual(self.runcli("pick", self.node, "python tests")[0], 0)
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertEqual(len(rows), 50)
        self.assertEqual(rows[0], {"old": 11})
        self.assertEqual(rows[-1]["q"], "python tests")
        self.assertEqual(rows[-1]["rc"], 0)

    def test_llmcall_busy_is_unsure(self):
        self.skill("coding", "python tests")
        bd = self.node / "budget/llm"
        write_json(str(bd / "grant.json"), {"holder": "skills", "gateway": "llm.fake"})
        call = "pick-" + hashlib.sha256(
            ("用技能：python tests\n" + "\n".join(build(self.node)["lines"]) + "\nchatgpt-gpt-6-sol-high").encode()).hexdigest()[:16]
        lock = self.node / "llmcall/llm" / call / "request.json.lock"
        lock.parent.mkdir(parents=True)
        with (bd / "ledger.lock").open("w") as ledger, lock.open("w") as held:
            fcntl.flock(ledger, fcntl.LOCK_EX)
            fcntl.flock(held, fcntl.LOCK_EX)
            rc, out, err = self.runcli("pick", self.node, "用技能：python tests")
        self.assertEqual(rc, 3, err)
        self.assertEqual(out, "")
        self.assertEqual(len(err.splitlines()), 1)
        self.assertTrue(err.startswith("aos7-skills: 不確定："), err)
        self.assertIn("照原樣再跑一次會接續", err)
        self.assertFalse(list((self.skills / ".pick").glob("*.json")))
        self.assertFalse((lock.parent / "request.json").exists())

    def test_llmcall_codes_and_receipt_errors(self):
        self.skill("coding", "python tests")
        bd = self.node / "budget/llm"
        write_json(str(bd / "grant.json"), {"holder": "skills", "gateway": "llm.fake"})
        for code in (1, 2, 3, 4):
            for stderr in ("noise\naos7-llmcall: " + ("不確定：" if code == 3 else "") + "原因。處理\n", ""):
                with self.subTest(code=code, stderr=stderr), patch("aos7_skills.aos7_budget.ledger_running", return_value=True), patch(
                        "aos7_skills.subprocess.run", return_value=subprocess.CompletedProcess([], code,
                        json.dumps({"text": "coding", "used": 4}), stderr)):
                    out, err = io.StringIO(), io.StringIO()
                    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                        rc = main(["pick", str(self.node), "用技能：python tests"])
                    self.assertEqual(rc, 0 if code == 4 else code)
                    self.assertEqual(len(err.getvalue().splitlines()), 1)
                    self.assertTrue(err.getvalue().startswith("aos7-skills: " + ("不確定：" if code == 3 else "")))
                    if stderr:
                        self.assertIn("原因。處理", err.getvalue())
                    self.assertNotIn("noise", err.getvalue())
                    self.assertEqual(bool(out.getvalue()), code == 4)
                    self.assertFalse(list((self.skills / ".pick").glob("*.json")))
        for receipt, expected in (("broken", 3), ('{}', 3), ('{"text": null, "used": 0}', 3),
                                  ('{"text":"outside", "used": 0}', 1)):
            with self.subTest(receipt=receipt), patch("aos7_skills.aos7_budget.ledger_running", return_value=True), patch(
                    "aos7_skills.subprocess.run", return_value=subprocess.CompletedProcess([], 0, receipt, "")):
                with contextlib.redirect_stderr(io.StringIO()) as err:
                    rc = main(["pick", str(self.node), "用技能：python tests"])
                self.assertEqual(rc, expected)
                self.assertEqual(len(err.getvalue().splitlines()), 1)

    def test_review_fixes(self):
        """審查補：帳未清也要提醒、bad 參數不動檔、grant 讀不到算不確定、同題並行請求檔不互刪、記錄並行不丟行。"""
        self.skill("coding", "python tests")
        bd = self.node / "budget/llm"
        write_json(str(bd / "grant.json"), {"holder": "skills", "gateway": "llm.fake"})
        for text, rc in (("none", 1), ("outside", 1)):
            with self.subTest(text=text), patch("aos7_skills.aos7_budget.ledger_running", return_value=True), patch(
                    "aos7_skills.subprocess.run", return_value=subprocess.CompletedProcess(
                        [], 4, json.dumps({"text": text, "used": 4}), "aos7-llmcall: 帳沒清。對帳\n")):
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
                    self.assertEqual(main(["pick", str(self.node), "用技能：python tests"]), rc)
                self.assertEqual(len(err.getvalue().splitlines()), 1)
                self.assertIn("帳沒清。對帳", err.getvalue())
        before = sorted(p.relative_to(self.node) for p in self.node.rglob("*"))
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(main(["pick", str(self.node), "用技能：python tests", "--reserve", "0"]), 2)
        self.assertEqual(sorted(p.relative_to(self.node) for p in self.node.rglob("*")), before)
        (bd / "grant.json").unlink()
        (bd / "grant.json").mkdir()
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(main(["pick", str(self.node), "用技能：python tests"]), 3)
        self.assertTrue(err.getvalue().startswith("aos7-skills: 不確定："))
        (bd / "grant.json").rmdir()
        write_json(str(bd / "grant.json"), {"holder": "skills", "gateway": "llm.fake"})
        seen = []
        def run(argv, **kw):
            seen.append(argv[argv.index("--request") + 1])
            return subprocess.CompletedProcess([], 3, "", "")
        with patch("aos7_skills.aos7_budget.ledger_running", return_value=True), patch(
                "aos7_skills.subprocess.run", side_effect=run), contextlib.redirect_stderr(io.StringIO()):
            main(["pick", str(self.node), "用技能：python tests"])
        self.assertIn(str(os.getpid()), Path(seen[0]).name)
        log = self.skills / ".pick/log.jsonl"
        log.unlink(missing_ok=True)
        ps = [subprocess.Popen([sys.executable, "-c", "import sys; sys.path[:0]=%r; from pathlib import Path; "
                                "from aos7_skills import keep_last; [keep_last(Path(%r), {'i': i}) for i in range(20)]"
                                % ([str(TOP / "modules/skills"), str(TOP / "lib")], str(log))]) for _ in range(2)]
        for p in ps:
            p.wait(20)
        self.assertEqual(len(log.read_text().splitlines()), 40)

    def test_argparse_does_not_touch_files(self):
        self.skill("alpha")
        def snapshot():
            return sorted((str(p), p.stat().st_mtime_ns) for p in self.node.rglob("*"))
        for args in (("--no-such-option",), ("pick", self.node), ("index", self.node, "--no-such-option")):
            before = snapshot()
            rc, out, err = self.runcli(*args)
            self.assertEqual(rc, 2)
            self.assertEqual(out, "")
            self.assertEqual(len(err.splitlines()), 1)
            self.assertIn("。用法看 aos7-skills --help", err)
            self.assertEqual(snapshot(), before)
        rc, out, err = self.runcli("--help")
        self.assertEqual((rc, err), (0, ""))
        self.assertLessEqual(len(out.splitlines()), 30)

    def test_bank_cleans_temp_node_on_exception(self):
        wf = Path(self.root) / "workflow-skills"
        for name in json.loads((TOP / "modules/skills/examples/bank.json").read_text())["workflows"]:
            self.skill(name, parent=wf)
        for phase in ("setup", "pick"):
            node = Path(self.root) / ("bank-" + phase)
            node.mkdir()
            with self.subTest(phase=phase), patch("bank.tempfile.mkdtemp", return_value=str(node)), patch(
                    "bank.setup", side_effect=RuntimeError("setup failed") if phase == "setup" else None), patch(
                    "bank.subprocess.Popen") as ledger, patch("bank.subprocess.run", side_effect=RuntimeError("pick failed")), patch(
                    "aos7_budget.ledger_running", return_value=True):
                with self.assertRaises(RuntimeError):
                    bank.main(["--workflows", str(wf)])
                self.assertFalse(node.exists())
                if phase == "pick":
                    ledger.return_value.terminate.assert_called_once()
                    ledger.return_value.wait.assert_called_once()

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
