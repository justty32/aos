"""作者第一刀驗收：需求、候選、發布恢復、真執行與有界清理。"""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from unittest import mock

PACK = Path(__file__).resolve().parents[1]
TOP = PACK.parents[1]
EXAMPLE = PACK / "examples/csv-request"
CSV = TOP / "packs/step/examples/csv"
AUTHOR = PACK / "bin/aos7-author"
STEP = TOP / "packs/step/bin/aos7-step"
sys.path[:0] = [str(TOP / "tests"), str(PACK)]
from base import CoreCase, DaemonCase  # noqa: E402
from aos7_fs import edit_json, read_json, write_json  # noqa: E402
import aos7_author as author  # noqa: E402
import aos7_author_pub as pub  # noqa: E402


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def regular_files(root):
    return sorted(str(Path(d, f).relative_to(root)) for d, _, fs in os.walk(root)
                  for f in fs if Path(d, f).is_file())


class TestAuthorHelpers(CoreCase):
    """所有檔案與子程序都侷限在測試空間。"""

    def source(self, name, doc):
        p = Path(self.root, name)
        p.write_bytes(json.dumps(doc, ensure_ascii=False).encode("utf-8"))
        return p

    def request(self, node, rid="csv1", **changes):
        shutil.copyfile(CSV / "data.csv", Path(node, "data.csv"))
        doc = json.loads((EXAMPLE / "request.json").read_bytes())
        doc.update(rid=rid, **changes)
        return self.source("request-source.json", doc)

    def register(self, node, rid="csv1"):
        path = self.request(node, rid)
        self.good(author.register_request(node, str(path)))
        return path

    def good(self, r):
        self.assertTrue(r["ok"], r)
        self.assertIsNone(r["why"], r)
        return r

    def refused(self, r, why):
        self.assertFalse(r["ok"], r)
        self.assertEqual(r["why"], why, r)
        return r

    def cli(self, node, *args, rc=0, crash=None, why=None):
        env = dict(os.environ)
        env.pop("AOS7_TEST_CRASH", None)
        if crash:
            env["AOS7_TEST_CRASH"] = "author:" + crash
        p = subprocess.run([sys.executable, str(AUTHOR), *map(str, args)], cwd=node,
                           env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, rc, (p.stdout, p.stderr))
        if rc == -9:
            return None
        r = json.loads(p.stdout)
        self.assertEqual(r["ok"], rc == 0, r)
        self.assertEqual(r["why"], why or {0: None, 1: "conflict", 2: "invalid", 3: "unknown"}[rc], r)
        return r

    def propose(self, node, rid="csv1", candidate=None, auto=False):
        p = EXAMPLE / "valid.json" if candidate is None else self.source("candidate-source.json", candidate)
        return self.good(author.propose(node, rid, candidate_path=str(p), auto=auto))

    def prepared(self, nid="a", rid="csv1"):
        node = self.mknode(nid)
        self.register(node, rid)
        return node, self.propose(node, rid)

    def doc(self, node, rid, name):
        return read_json(str(Path(node, "author/req", rid, name + ".json")))

    def table_path(self, node):
        return Path(node, ".aos/tasks.json")

    def version_counts(self, node, rid, v, count=1):
        mine = [t for t in self.tasks(node) if t["name"] == "author-" + v["job"]]
        self.assertEqual(len(mine), count)
        rc = self.doc(node, rid, "receipt")
        self.assertEqual(set(rc["versions"]), {v["candidate_sha"]})
        return rc

    def crash_publish(self, node, rid, point):
        self.cli(node, "publish", rid, rc=-9, crash=point)

    def remove_task(self, node, name):
        edit_json(str(self.table_path(node)),
                  lambda t: dict(t, tasks=[i for i in t["tasks"] if i["name"] != name]))

    def frame(self, node, job):
        return read_json(str(Path(node, "jobs", job, "frame.json")), {}) or {}

    def wait_job(self, node, job):
        self.wait_for(lambda: self.frame(node, job).get("phase") == "ended", timeout=30,
                      msg="工作未 ended：" + job)
        fr = self.frame(node, job)
        self.assertEqual(fr["end"], "ok", fr)
        return fr

    def step_close(self, node, job):
        p = subprocess.run([sys.executable, str(STEP), "close", "jobs/" + job], cwd=node,
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 0, (p.stdout, p.stderr))
        self.assertTrue(self.frame(node, job)["closed"])

    def check_answer(self, node, job, ok=True):
        p = subprocess.run([sys.executable, str(EXAMPLE / "check_answer.py"), "jobs/" + job,
                            "data.csv"], cwd=node, capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 0 if ok else 1, (p.stdout, p.stderr))
        result = json.loads(p.stdout)
        self.assertEqual(result["ok"], ok, result)
        return result

    def assert_closed(self, node, rid):
        folder = Path(node, "author/req", rid)
        self.assertEqual(sorted(p.name for p in folder.iterdir()), ["receipt.json", "request.json"])
        receipt = self.doc(node, rid, "receipt")
        self.assertTrue(receipt["closed"])
        self.assertTrue(all(v["closed"] for v in receipt["versions"].values()))


class TestAuthorCore(TestAuthorHelpers):
    """需求、驗證與發布契約。"""

    def test_request_identity_and_limits(self):
        """同文重送、異文衝突與固定帳檔。"""
        node = self.mknode()
        path = self.request(node)
        first = self.cli(node, "register", path)
        before = regular_files(Path(node, "author"))
        stored = Path(node, "author/req/csv1/request.json").read_bytes()
        again = self.cli(node, "register", path)
        self.assertFalse(first["dup"])
        self.assertTrue(again["dup"])
        self.assertEqual(before, regular_files(Path(node, "author")))
        doc = json.loads(path.read_bytes())
        doc["goal"] += "另文"
        self.cli(node, "register", self.source("changed.json", doc), rc=1)
        self.assertEqual(Path(node, "author/req/csv1/request.json").read_bytes(), stored)
        self.propose(node)
        self.good(pub.publish(node, "csv1"))
        files = regular_files(Path(node, "author"))
        self.assertEqual(files, ["author.lock"] + ["req/csv1/" + n for n in sorted(author.FILES)])
        self.assertLessEqual(len(list(Path(node, "author/req/csv1").iterdir())), 5)

    def test_invalid_requests(self):
        """拒絕輸入雜湊錯誤與路徑型識別碼。"""
        node = self.mknode()
        original = json.loads(self.request(node).read_bytes())
        for rid in ("a/b", "..", "a\0b", "a" * 24):
            with self.subTest(rid=rid):
                doc = dict(original, rid=rid)
                self.cli(node, "register", self.source("invalid.json", doc), rc=2)
        original["inputs"][0]["sha256"] = "0" * 64
        self.cli(node, "register", self.source("invalid.json", original), rc=2)
        self.assertFalse(Path(node, "author/req").exists())

    def reject_candidate(self, node, rid, path, rule, preexisting=False):
        raw = Path(path).read_bytes()
        sha = digest(raw)
        before = self.table_path(node).read_bytes()
        r = author.propose(node, rid, candidate_path=str(path))
        self.refused(r, "invalid")
        self.assertIn(rule, {i["rule"] for i in r["issues"]}, r)
        self.assertEqual(self.table_path(node).read_bytes(), before)
        job = Path(node, "jobs", rid + "_" + sha[:8])
        if preexisting:
            self.assertFalse((job / "steps.json").exists())
        else:
            self.assertFalse(job.exists())
        entry = self.doc(node, rid, "candidate")["versions"][sha]
        self.assertEqual(author.candidate_raw(entry), raw)

    def test_seven_fixtures(self):
        """七候選恰一合法，六壞依規則拒絕。"""
        cases = (("valid", None), ("bad-json", "json"), ("bad-params", "param"),
                 ("bad-dependency", "dep"), ("bad-mode", "mode"),
                 ("bad-idempotent", "attr"), ("bad-path", "path"))
        for k, (name, rule) in enumerate(cases):
            with self.subTest(fixture=name):
                node = self.mknode("n" + str(k))
                self.register(node)
                path = EXAMPLE / (name + ".json")
                if rule:
                    self.reject_candidate(node, "csv1", path, rule)
                else:
                    self.good(author.propose(node, "csv1", candidate_path=str(path)))

    def test_candidate_variants(self):
        """拒絕環、錯參數、假屬性與寫路徑逃逸。"""
        valid = json.loads((EXAMPLE / "valid.json").read_bytes())
        changes = [
            ("cycle", "dep", lambda c: c["steps"][1].update(ok="convert")),
            ("type", "param", lambda c: c["steps"][0]["args"].update(src=42)),
            ("extra", "param", lambda c: c["steps"][0]["args"].update(extra="x")),
            ("missing", "param", lambda c: c["steps"][0]["args"].pop("src")),
            ("tool", "tool", lambda c: c["steps"][0].update(tool="unknown")),
            ("once", "mode", lambda c: c.update(mode="once")),
            ("idempotent", "attr", lambda c: c["steps"][0].update(idempotent=False)),
            ("argv", "attr", lambda c: c["steps"][0].update(argv=["true"])),
            ("absolute", "path", lambda c: c["steps"][1]["args"].update(dst="/tmp/x")),
            ("parent", "path", lambda c: c["steps"][1]["args"].update(dst="${out}/../x")),
            ("symlink", "path", lambda c: c["steps"][1]["args"].update(dst="${out}/esc/report.json")),
        ]
        for name, rule, change in changes:
            with self.subTest(variant=name):
                node = self.mknode(name)
                self.register(node)
                c = copy.deepcopy(valid)
                change(c)
                path = self.source("variant.json", c)
                if name == "symlink":
                    job = "csv1_" + digest(path.read_bytes())[:8]
                    out = Path(node, "jobs", job, "out")
                    out.mkdir(parents=True)
                    outside = Path(self.root, "outside")
                    outside.mkdir()
                    (out / "esc").symlink_to(outside, target_is_directory=True)
                self.reject_candidate(node, "csv1", path, rule, name == "symlink")

    def test_tool_tmp_symlink_at_propose(self):
        """審查拒絕工具暫存寫路徑外連。"""
        node = self.mknode("propose")
        self.register(node)
        path = EXAMPLE / "valid.json"
        job = "csv1_" + digest(path.read_bytes())[:8]
        out = Path(node, "jobs", job, "out")
        out.mkdir(parents=True)
        outside = Path(self.root, "outside.json")
        outside.write_bytes(b"untouched")
        (out / "report.json.tmp").symlink_to(outside)
        self.reject_candidate(node, "csv1", path, "path", preexisting=True)
        self.assertEqual(outside.read_bytes(), b"untouched")

    def test_tool_tmp_symlink_at_publish(self):
        """審查之後新增的工具暫存 symlink 在發布時拒絕。"""
        node, v = self.prepared()
        outside = Path(self.root, "outside.json")
        outside.write_bytes(b"untouched")
        out = Path(node, "jobs", v["job"], "out")
        self.assertFalse(out.exists())
        out.mkdir()
        (out / "data.json.tmp").symlink_to(outside)
        before = self.table_path(node).read_bytes()
        r = self.cli(node, "publish", "csv1", rc=2)
        self.assertIn("symlink", r["error"])
        self.assertEqual(self.table_path(node).read_bytes(), before)
        self.assertIsNone(self.doc(node, "csv1", "intent"))
        self.assertEqual(outside.read_bytes(), b"untouched")

    def test_out_dir_symlink_at_publish(self):
        """out/ 本身外連到 node 外：發布拒絕，表與外部目錄不變。"""
        node, v = self.prepared()
        outside = Path(self.root, "outside-dir")
        outside.mkdir()
        Path(node, "jobs", v["job"], "out").symlink_to(outside, target_is_directory=True)
        before = self.table_path(node).read_bytes()
        r = self.cli(node, "publish", "csv1", rc=2)
        self.assertIn("symlink", r["error"])
        self.assertEqual(self.table_path(node).read_bytes(), before)
        self.assertEqual(list(outside.iterdir()), [])

    def test_frame_recovery_binds_fixed_sources(self):
        """相符 frame 可補回條，但資料快照改動使證據失效。"""
        for changed in (False, True):
            with self.subTest(changed=changed):
                node, v = self.prepared("changed" if changed else "same")
                self.crash_publish(node, "csv1", "after-intent")
                job = Path(node, "jobs", v["job"])
                write_json(str(job / "frame.json"),
                           {"job": v["job"], "table": author.aos7_step.table_rev((job / "steps.json").read_bytes())})
                if changed:
                    (job / "data.csv").write_bytes((job / "data.csv").read_bytes() + b"\n")
                before = self.table_path(node).read_bytes()
                r = self.cli(node, "publish", "csv1", rc=3 if changed else 0)
                self.assertEqual(self.table_path(node).read_bytes(), before)
                self.assertEqual(self.tasks(node), [])
                if changed:
                    self.assertIsNone(self.doc(node, "csv1", "receipt"))
                else:
                    self.assertEqual(r["receipt"]["evidence"], "frame")
                    self.version_counts(node, "csv1", v, count=0)

    def test_input_cannot_shadow_step_control(self):
        """輸入 basename 不得覆寫 step 的 frame 控制檔。"""
        node = self.mknode()
        control = Path(node, "frame.json")
        control.write_bytes(b'{"job": "input"}')
        request = json.loads(self.request(node).read_bytes())
        request["inputs"].append({"path": "frame.json", "sha256": digest(control.read_bytes())})
        path = self.source("control-request.json", request)
        registered = author.register_request(node, str(path))
        if not registered["ok"]:
            self.refused(registered, "invalid")
            self.assertFalse(Path(node, "jobs").exists())
            return
        self.reject_candidate(node, "csv1", EXAMPLE / "valid.json", "source")

    def test_replace_candidate_without_verdict_cleans_job(self):
        """編譯後未存 verdict 的殘留會被換候選清理，且不能結案。"""
        node, old = self.prepared()
        verdict_path = Path(node, "author/req/csv1/verdict.json")
        edit_json(str(verdict_path),
                  lambda d: dict(d, versions={k: v for k, v in d["versions"].items()
                                              if k != old["candidate_sha"]}))
        self.assertTrue(Path(node, "jobs", old["job"]).exists())
        self.cli(node, "close", "csv1", rc=1)
        candidate = json.loads((EXAMPLE / "valid.json").read_bytes())
        candidate["intent"] = "換待審候選"
        new = self.propose(node, candidate=candidate)
        self.assertNotEqual(old["job"], new["job"])
        self.assertFalse(Path(node, "jobs", old["job"]).exists())
        self.assertTrue(Path(node, "jobs", new["job"], "steps.json").exists())
        self.assertEqual(set(self.doc(node, "csv1", "candidate")["versions"]), {new["candidate_sha"]})
        self.assertEqual(set(self.doc(node, "csv1", "verdict")["versions"]), {new["candidate_sha"]})

    def test_close_refuses_active_without_verdict(self):
        """第一版已可結案，但第二版待審候選的 verdict 不見：close 必須 conflict、帳一檔不刪。"""
        node, v1 = self.prepared()
        self.good(pub.publish(node, "csv1"))
        write_json(str(Path(node, "jobs", v1["job"], "frame.json")), {"v": 1, "job": v1["job"], "phase": "ended",
                                                                      "end": "ok", "closed": True})
        edit_json(str(Path(node, "author/req/csv1/verdict.json")),
                  lambda d: (d["versions"][v1["candidate_sha"]].update(answer={"ok": True, "issues": []}), d)[1])
        candidate = json.loads((EXAMPLE / "valid.json").read_bytes())
        candidate["intent"] = "第二版"
        v2 = self.propose(node, candidate=candidate)
        edit_json(str(Path(node, "author/req/csv1/verdict.json")),
                  lambda d: dict(d, versions={k: x for k, x in d["versions"].items() if k != v2["candidate_sha"]}))
        folder = Path(node, "author/req/csv1")
        before = {p.name: p.read_bytes() for p in folder.iterdir()}
        r = self.cli(node, "close", "csv1", rc=1)
        self.assertIn("待審", r["error"])
        self.assertEqual({p.name: p.read_bytes() for p in folder.iterdir()}, before)

    def test_candidate_list_fields_are_schema_errors(self):
        """tool/start 陣列是 schema 錯誤，CLI 必須回 JSON 而非 traceback。"""
        for field in ("tool", "start"):
            with self.subTest(field=field):
                node = self.mknode(field)
                self.register(node)
                candidate = json.loads((EXAMPLE / "valid.json").read_bytes())
                target = candidate["steps"][0] if field == "tool" else candidate
                target[field] = []
                path = self.source("list-field.json", candidate)
                r = self.cli(node, "propose", "csv1", "--candidate", path, rc=2)
                self.assertIn("schema", {i["rule"] for i in r["issues"]})
                self.assertFalse(Path(node, "jobs", "csv1_" + digest(path.read_bytes())[:8]).exists())

    def test_pending_candidate_prefix_collision(self):
        """待審 sha 前八碼相同時拒絕覆寫候選與 job。"""
        node, old = self.prepared()
        path = EXAMPLE / "valid.json"
        sha = digest(path.read_bytes())
        fake = sha[:8] + ("0" if sha[8] != "0" else "1") + sha[9:]
        folder = Path(node, "author/req/csv1")
        cdoc = self.doc(node, "csv1", "candidate")
        cdoc["active"] = fake
        cdoc["versions"] = {fake: cdoc["versions"][sha]}
        write_json(str(folder / "candidate.json"), cdoc)
        vdoc = self.doc(node, "csv1", "verdict")
        verdict = vdoc["versions"][sha]
        verdict["candidate_sha"] = fake
        vdoc["versions"] = {fake: verdict}
        write_json(str(folder / "verdict.json"), vdoc)
        before = {p.name: p.read_bytes() for p in folder.iterdir()}
        steps = Path(node, "jobs", old["job"], "steps.json").read_bytes()
        self.cli(node, "propose", "csv1", "--candidate", path, rc=1)
        self.assertEqual({p.name: p.read_bytes() for p in folder.iterdir()}, before)
        self.assertEqual(Path(node, "jobs", old["job"], "steps.json").read_bytes(), steps)

    def test_propose_default_and_auto(self):
        """預設只審查，明示自動才發布。"""
        node = self.mknode()
        self.register(node)
        before = self.table_path(node).read_bytes()
        v = self.cli(node, "propose", "csv1", "--candidate", EXAMPLE / "valid.json")
        self.assertEqual(self.table_path(node).read_bytes(), before)
        self.assertIsNone(self.doc(node, "csv1", "receipt"))
        self.cli(node, "propose", "csv1", "--candidate", EXAMPLE / "valid.json", "--auto")
        self.version_counts(node, "csv1", v)
        status = self.cli(node, "status", "csv1")
        self.assertEqual(status["active"], v["candidate_sha"])
        self.assertTrue(status["versions"][v["candidate_sha"]]["receipt"])

    def test_compile_determinism_and_cards(self):
        """跨空間編譯一致，重編雜湊與工具來源相符。"""
        n1, v1 = self.prepared("a")
        n2, v2 = self.prepared("b")
        p1 = Path(n1, "jobs", v1["job"])
        p2 = Path(n2, "jobs", v2["job"])
        self.assertEqual((p1 / "steps.json").read_bytes(), (p2 / "steps.json").read_bytes())
        vd = self.doc(n1, "csv1", "verdict")["versions"][v1["candidate_sha"]]
        self.assertEqual(vd["steps_sha256"], digest((p1 / "steps.json").read_bytes()))
        nd = author.Node(n1)
        with nd.lock():
            rebuilt = author.validate_compile(nd, "csv1", v1["candidate_sha"])
        self.assertEqual(rebuilt["payload_sha"], v1["payload_sha"])
        self.assertEqual(self.propose(n1), v1)
        cards = author.load_toolcards()
        for c in cards["tools"].values():
            sc = c["script"]
            source = TOP / "packs" / sc["src"]
            self.assertEqual(digest(source.read_bytes()), sc["sha256"])
            self.assertEqual((p1 / sc["as"]).read_bytes(), source.read_bytes())
        self.assertEqual((p1 / "data.csv").read_bytes(), (CSV / "data.csv").read_bytes())
        self.assertFalse(read_json(str(p1 / "steps.json"))["options"]["restart_on_end"])

    def test_payload_changes_refuse_publish(self):
        """步驟、腳本、資料與工具卡改動皆拒發布。"""
        for k, name in enumerate(("steps.json", "convert.py", "stats.py", "data.csv", "card")):
            with self.subTest(source=name):
                node, v = self.prepared("n" + str(k))
                before = self.table_path(node).read_bytes()
                vd = self.doc(node, "csv1", "verdict")["versions"][v["candidate_sha"]]
                if name == "card":
                    cards = author.load_toolcards()
                    cards["sha256"] = digest(Path(author.CARDS).read_bytes() + b" ")
                    context = mock.patch.object(author, "load_toolcards", return_value=cards)
                else:
                    p = Path(node, "jobs", v["job"], name)
                    p.write_bytes(p.read_bytes() + b" \n")
                    context = mock.patch.object(author, "CARDS", author.CARDS)
                with context:
                    self.assertNotEqual(author.recompute_payload(author.Node(node), "csv1", vd), v["payload_sha"])
                    r = self.cli(node, "publish", "csv1", rc=2) if name != "card" else pub.publish(node, "csv1")
                self.refused(r, "invalid")
                self.assertIn("payload_changed", r["error"])
                self.assertEqual(self.table_path(node).read_bytes(), before)
                self.assertIsNone(self.doc(node, "csv1", "intent"))

    def test_publish_crash_matrix(self):
        """三個發布中斷點各殺三次，恢復不重複登記。"""
        for point in ("after-merge", "after-receipt", "after-intent"):
            for repeat in range(3):
                with self.subTest(point=point, repeat=repeat):
                    node, v = self.prepared(point + str(repeat))
                    self.crash_publish(node, "csv1", point)
                    if point == "after-intent":
                        before = self.table_path(node).read_bytes()
                        self.cli(node, "publish", "csv1", rc=3)
                        self.assertEqual(self.tasks(node), [])
                        self.assertEqual(self.table_path(node).read_bytes(), before)
                        self.assertIsNone(self.doc(node, "csv1", "receipt"))
                        self.cli(node, "publish", "csv1", "--resend")
                    else:
                        self.cli(node, "publish", "csv1")
                    self.version_counts(node, "csv1", v)
                    before = self.table_path(node).read_bytes()
                    self.good(pub.recover(node, "csv1"))
                    self.assertEqual(self.table_path(node).read_bytes(), before)

    def test_missing_table_item_and_birth_evidence(self):
        """表項消失回不明，有出生證據才補回條。"""
        node, v = self.prepared()
        self.crash_publish(node, "csv1", "after-merge")
        task = self.tasks(node)[0]
        self.remove_task(node, task["name"])
        before = self.table_path(node).read_bytes()
        self.cli(node, "publish", "csv1", rc=3)
        self.assertEqual(self.table_path(node).read_bytes(), before)
        self.assertIsNone(self.doc(node, "csv1", "receipt"))
        birth = {k: task[k] for k in ("name", "argv", "x")}
        write_json(str(Path(node, ".aos/tasks", task["name"], "birth.json")), birth)
        r = self.cli(node, "publish", "csv1")
        self.assertEqual(r["receipt"]["evidence"], "birth")
        self.assertEqual(self.table_path(node).read_bytes(), before)
        self.version_counts(node, "csv1", v, count=0)

    def test_changed_items_conflict(self):
        """未有回條時停用或改指令均衝突且不覆寫。"""
        for name in ("disabled", "argv"):
            with self.subTest(change=name):
                node, _ = self.prepared(name)
                self.crash_publish(node, "csv1", "after-merge")
                def change(t):
                    if name == "disabled":
                        t["tasks"][0]["enabled"] = False
                    else:
                        t["tasks"][0]["argv"] = ["true"]
                    return t
                edit_json(str(self.table_path(node)), change)
                before = self.table_path(node).read_bytes()
                self.cli(node, "publish", "csv1", rc=1)
                self.assertEqual(self.table_path(node).read_bytes(), before)
                self.assertIsNone(self.doc(node, "csv1", "receipt"))

    def test_receipt_wins_over_disabled_item(self):
        """成功回條重送不復活已停用或移除的項目。"""
        node, v = self.prepared()
        original = self.good(pub.publish(node, "csv1"))["receipt"]
        edit_json(str(self.table_path(node)),
                  lambda t: dict(t, tasks=[dict(i, enabled=False) for i in t["tasks"]]))
        before = self.table_path(node).read_bytes()
        r = self.cli(node, "publish", "csv1")
        self.assertTrue(r["dup"])
        self.assertEqual(r["receipt"], original)
        self.assertEqual(self.table_path(node).read_bytes(), before)
        self.remove_task(node, "author-" + v["job"])
        before = self.table_path(node).read_bytes()
        self.assertEqual(self.cli(node, "publish", "csv1")["receipt"], original)
        self.assertEqual(self.table_path(node).read_bytes(), before)

    def test_merge_preserves_concurrent_edits(self):
        """發布前他人改表，合併保留別項與頂層設定。"""
        node, _ = self.prepared()
        other = {"name": "other", "mode": "keep", "argv": ["sleep", "1"], "x": {"note": "保留"}}
        def concurrent_edit(point):
            if point == "author:after-intent":
                edit_json(str(self.table_path(node)),
                          lambda t: dict(t, tasks=t["tasks"] + [other], mount_allow=["/srv/example"], launch={"limit": 7}))
        with mock.patch.object(pub, "test_point", side_effect=concurrent_edit):
            self.good(pub.publish(node, "csv1"))
        table = read_json(str(self.table_path(node)))
        self.assertEqual(table["tasks"][0], other)
        self.assertEqual(len(table["tasks"]), 2)
        self.assertEqual(table["mount_allow"], ["/srv/example"])
        self.assertEqual(table["launch"], {"limit": 7})

    def test_corrupt_tasks_not_overwritten(self):
        """壞任務表回不明並保留原始位元組。"""
        node, _ = self.prepared()
        raw = b'{"tasks": [broken\n'
        self.table_path(node).write_bytes(raw)
        self.cli(node, "publish", "csv1", rc=3)
        self.assertEqual(self.table_path(node).read_bytes(), raw)
        self.refused(pub.recover(node, "csv1"), "unknown")
        self.assertEqual(self.table_path(node).read_bytes(), raw)

    def test_null_tasks_not_overwritten(self):
        """JSON null 不代表空任務表；發布回 unknown 並保留 bytes。"""
        node, _ = self.prepared()
        self.table_path(node).write_bytes(b"null")
        self.cli(node, "publish", "csv1", rc=3)
        self.assertEqual(self.table_path(node).read_bytes(), b"null")
        self.assertIsNone(self.doc(node, "csv1", "receipt"))

    def test_two_versions_and_full(self):
        """同需求兩版並存，第三版超額拒絕。"""
        node, v1 = self.prepared()
        self.good(pub.publish(node, "csv1"))
        j1 = Path(node, "jobs", v1["job"])
        (j1 / "out").mkdir()
        (j1 / "out" / "probe").write_text(v1["candidate_sha"])     # 第二版編譯／發布之前就有第一版產物
        snap = {p.name: p.read_bytes() for p in j1.iterdir() if p.is_file()}
        candidate = json.loads((EXAMPLE / "valid.json").read_bytes())
        candidate["intent"] = "第二版"
        v2 = self.propose(node, candidate=candidate)
        self.assertEqual({p.name: p.read_bytes() for p in j1.iterdir() if p.is_file()}, snap)
        self.cli(node, "publish", "csv1", "--sha", v2["candidate_sha"])
        self.assertEqual({p.name: p.read_bytes() for p in j1.iterdir() if p.is_file()}, snap)
        self.assertNotEqual(v1["job"], v2["job"])
        self.assertEqual({i["name"] for i in self.tasks(node)}, {"author-" + v["job"] for v in (v1, v2)})
        out = Path(node, "jobs", v2["job"], "out")
        out.mkdir()
        (out / "probe").write_text(v2["candidate_sha"])
        self.assertEqual(len(self.doc(node, "csv1", "receipt")["versions"]), 2)
        candidate["intent"] = "第三版"
        before = self.table_path(node).read_bytes()
        self.cli(node, "propose", "csv1", "--candidate", self.source("third.json", candidate), rc=1, why="full")
        self.assertEqual(self.table_path(node).read_bytes(), before)
        for v in (v1, v2):
            self.assertEqual(Path(node, "jobs", v["job"], "out/probe").read_text(), v["candidate_sha"])

    def test_unresolved_close_preserves_evidence(self):
        """不明發布不得結案或刪除證據。"""
        node, _ = self.prepared()
        self.crash_publish(node, "csv1", "after-intent")
        folder = Path(node, "author/req/csv1")
        before = {p.name: p.read_bytes() for p in folder.iterdir()}
        self.cli(node, "close", "csv1", rc=3)
        self.assertEqual({p.name: p.read_bytes() for p in folder.iterdir()}, before)


class TestAuthorDaemon(TestAuthorHelpers, DaemonCase):
    """真 daemon 執行、驗答案與清理帳。"""

    def running(self):
        node = self.mknode(interval_ms=50)
        self.start_daemon(register=["a"])
        return node

    def executed(self, node, rid):
        self.register(node, rid)
        v = self.propose(node, rid, auto=True)
        self.wait_job(node, v["job"])
        return v

    def test_answer_and_close(self):
        """真跑兩步各一次，壞答案拒絕，結案只留雙檔。"""
        node = self.running()
        self.register(node)
        candidate = json.loads((EXAMPLE / "valid.json").read_bytes())
        candidate["start"] = "c"
        candidate["steps"][0].update(id="c", ok="s")
        candidate["steps"][1]["id"] = "s"
        candidate["steps"][1]["args"]["request"] = "${req:c}"
        v = self.propose(node, candidate=candidate, auto=True)
        self.wait_job(node, v["job"])
        job = Path(node, "jobs", v["job"])
        frame = self.frame(node, v["job"])
        self.cli(node, "close", "csv1", rc=1)
        for step in ("c", "s"):
            self.assertEqual(len(list((job / "results" / step).glob("*.json"))), 1)
        self.cli(node, "answer", "csv1")
        self.assertTrue(self.doc(node, "csv1", "verdict")["versions"][v["candidate_sha"]]["answer"]["ok"])
        self.wait_round(self.node_round() + 3)
        self.assertEqual(self.frame(node, v["job"])["inst"], frame["inst"])
        report = job / "out/report.json"
        saved = report.read_bytes()
        doc = json.loads(saved)
        self.assertEqual(doc["rows"], 5)
        self.assertEqual(doc["by_dept"], {"eng": {"n": 2, "sum": 200, "avg": 100},
                                         "ops": {"n": 2, "sum": 120, "avg": 60},
                                         "sales": {"n": 1, "sum": 200, "avg": 200}})
        doc["by_dept"]["eng"]["sum"] += 1
        report.write_text(json.dumps(doc))
        checked = self.check_answer(node, v["job"], ok=False)
        self.assertFalse(checked["ok"], checked)
        self.assertIn("eng: sum 不符", checked["issues"])
        report.write_bytes(saved)
        self.check_answer(node, v["job"])
        self.step_close(node, v["job"])
        self.cli(node, "close", "csv1")
        self.assert_closed(node, "csv1")
        self.cli(node, "close", "csv1")
        self.assert_closed(node, "csv1")

    def test_checker_rejects_bad_evidence(self):
        """答案、來源、結果數與產物雜湊異常皆拒絕。"""
        node = self.running()
        v = self.executed(node, "evidence")
        job = Path(node, "jobs", v["job"])
        self.check_answer(node, v["job"])
        report = job / "out/report.json"
        saved = report.read_bytes()
        bad = json.loads(saved)
        bad["from"] = "wrong-request"
        report.write_text(json.dumps(bad))
        self.check_answer(node, v["job"], ok=False)
        report.write_bytes(saved)
        for step in ("convert", "stats"):
            result = next((job / "results" / step).glob("*.json"))
            original = result.read_bytes()
            with self.subTest(step=step, change="missing"):
                result.unlink()
                self.check_answer(node, v["job"], ok=False)
                result.write_bytes(original)
            with self.subTest(step=step, change="extra"):
                extra = result.with_name("extra.json")
                extra.write_bytes(original)
                self.check_answer(node, v["job"], ok=False)
                extra.unlink()
            with self.subTest(step=step, change="identity"):
                doc = json.loads(original)
                doc["attempt"] = "wrong-attempt"
                result.write_text(json.dumps(doc))
                self.check_answer(node, v["job"], ok=False)
                result.write_bytes(original)
        output = job / "out/data.json"
        original = output.read_bytes()
        output.write_bytes(original + b" ")
        self.check_answer(node, v["job"], ok=False)
        output.write_bytes(original)
        self.check_answer(node, v["job"])
        # answer 必須讀 job 的固定快照；node 原始輸入事後改掉無關。
        source = Path(node, "data.csv")
        saved_source = source.read_bytes()
        source.write_bytes(saved_source.replace(b"120", b"999"))
        self.cli(node, "answer", "evidence")
        snapshot = job / "data.csv"
        saved_snapshot = snapshot.read_bytes()
        snapshot.write_bytes(saved_snapshot + b"\n")
        r = self.cli(node, "answer", "evidence", rc=2)
        self.assertFalse(r["answer"]["ok"])
        self.assertTrue(any("manifest" in issue for issue in r["answer"]["issues"]), r)
        snapshot.write_bytes(saved_snapshot)
        self.cli(node, "answer", "evidence")
        source.write_bytes(saved_source)
        self.step_close(node, v["job"])
        self.good(author.close_request(node, "evidence"))

    def test_close_requires_answer(self):
        """步驟已結案但未驗答案，仍拒絕作者結案。"""
        node = self.running()
        v = self.executed(node, "pending")
        self.step_close(node, v["job"])
        folder = Path(node, "author/req/pending")
        before = {p.name: p.read_bytes() for p in folder.iterdir()}
        self.cli(node, "close", "pending", rc=1)
        self.assertEqual({p.name: p.read_bytes() for p in folder.iterdir()}, before)

    def test_closed_publish_returns_receipt(self):
        """結案清候選後發布重送仍回原成功回條。"""
        node = self.running()
        v = self.executed(node, "closed")
        self.good(author.answer(node, "closed"))
        self.step_close(node, v["job"])
        self.good(author.close_request(node, "closed"))
        before = self.table_path(node).read_bytes()
        r = self.cli(node, "publish", "closed", "--sha", v["candidate_sha"])
        self.assertTrue(r["dup"], r)
        self.assertEqual(r["receipt"], self.doc(node, "closed", "receipt")["versions"][v["candidate_sha"]])
        self.assertEqual(self.table_path(node).read_bytes(), before)
        self.assert_closed(node, "closed")

    def test_close_crash_recovery(self):
        """結案三個清理中斷點重送均能收乾淨。"""
        node = self.running()
        for k, point in enumerate(("close-after-receipt", "close-after-candidate", "close-after-verdict")):
            with self.subTest(point=point):
                rid = "close" + str(k)
                v = self.executed(node, rid)
                self.good(author.answer(node, rid))
                self.step_close(node, v["job"])
                self.cli(node, "close", rid, rc=-9, crash=point)
                self.assertTrue(self.doc(node, rid, "receipt")["closed"])
                self.cli(node, "close", rid)
                self.assert_closed(node, rid)

    def test_100_requests_bounded_files(self):
        """較慢：百需求分批完成後帳檔恰二百加一。"""
        node = self.running()
        for batch in range(5):
            versions = []
            for k in range(batch * 20, (batch + 1) * 20):
                rid = "r%03d" % k
                self.register(node, rid)
                v = self.propose(node, rid, auto=True)
                versions.append((rid, v))
            self.wait_for(lambda: all(self.frame(node, v["job"]).get("phase") == "ended"
                                     for _, v in versions), timeout=60, msg="批次未結束")
            for rid, v in versions:
                self.assertEqual(self.frame(node, v["job"])["end"], "ok")
                self.good(author.answer(node, rid))
                self.step_close(node, v["job"])
                self.good(author.close_request(node, rid))
                self.assert_closed(node, rid)
            names = {"author-" + v["job"] for _, v in versions}
            edit_json(str(self.table_path(node)),
                      lambda t: dict(t, tasks=[i for i in t["tasks"] if i["name"] not in names]))
        files = regular_files(Path(node, "author"))
        self.assertEqual(len(files), 201, files)
        self.assertEqual(files, sorted(["author.lock"] + ["req/r%03d/%s.json" % (k, name)
                                                         for k in range(100) for name in ("request", "receipt")]))
