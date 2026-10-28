"""test_nia - agent-round 落地第 6、7 步：範本 demo/agent-nia（parts.json 手寫相對路徑指 lib 的格）與 aos-ai spawn 的 parts.json 範本。

範本：aos-exec 跑一題（假腦叫 clock 再答）、§ 5 的檔在 stack、trace 有 compact 那格；兩題＝round 退 0 後 loop 再叫、答完退 10 正常停；
  沒題＝loop 第一次就停、結束碼 0；parts.json／tools.json 只用相對路徑、每格 aos-parts which 找得到。
spawn：--from agent-nia 後 parts.json、tools.json 指出範本的相對路徑改成絕對、搬到 agents/<名>/agent/ 後跑一題答得出來；
  沒有 parts.json 的範本（agent-dan）tools.json 一個字不動。
設計：proto8/thinking/2026-10-28-agent-round.md § 1、§ 7 第 6、7 步、文末 39～。"""
import json, os, subprocess, tempfile, unittest
from pathlib import Path

from aos_bins import ROOT, EXEC, path_with  # noqa: E402
from test_ai_tools import ai  # noqa: E402

NIA = ROOT / "demo" / "agent-nia"
PARTS = str(ROOT / "bin" / "aos-parts")
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_CF", "AOS_CD", "AOS_CO", "AOS_BRAIN_URL", "AOS_BRAIN_MODEL",
         "AOS_BRAIN_KEY", "AOS_AI_ROOT", "MAX_BYTES", "MAX_RETRIES", "MAX_PARALLEL", "ENDPOINT_NAME")


def env():
    e = {k: v for k, v in os.environ.items() if k not in CLEAR}
    e["PATH"] = path_with(e.get("PATH", ""))
    return e


class Template(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.ws = Path(t.name)

    def put(self, name, text):
        (self.ws / "new").mkdir(exist_ok=True)
        (self.ws / "new" / name).write_text(text)

    def run_nia(self):
        return subprocess.run([EXEC, str(NIA)], capture_output=True, text=True, env=env(), cwd=self.ws, timeout=120)

    def units(self):
        return [json.loads(l)["unit"] for l in (self.ws / ".stack" / "trace.jsonl").read_text().splitlines()]

    def test_one_question(self):
        self.put("q1.txt", "現在幾點？")
        r = self.run_nia()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertRegex((self.ws / "out" / "q1.txt").read_text(), r"^FAKE ANSWER to: 現在幾點？（clock said: \d{4}-.*Z）\n$")
        self.assertEqual(sorted(p.name for p in (self.ws / ".stack").iterdir()), ["clock", "history.jsonl", "live.jsonl", "trace.jsonl"])   # clock＝工具的小格（P-17）
        roles = [json.loads(l)["role"] for l in (self.ws / ".stack" / "history.jsonl").read_text().splitlines()]
        self.assertEqual(roles, ["user", "assistant", "tool", "assistant"])
        u = self.units()
        self.assertEqual(u.count("hook/pre_think"), 2)                          # compact 預設掛在 pre_think、沒超過不動
        self.assertEqual((u[0], u[-1]), ("queue claim", "queue finish"))

    def test_two_questions_loop_calls_round_again(self):
        self.put("q1.txt", "幾點？")
        self.put("q2.txt", "1+1？")
        r = self.run_nia()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(sorted(p.name for p in (self.ws / "done").iterdir()), ["q1.txt", "q2.txt"])
        self.assertEqual(self.units().count("queue claim"), 2)                   # 一題一輪：round 退 0 → loop 再叫

    def test_no_question_loop_stops_ok(self):
        r = self.run_nia()
        self.assertEqual((r.returncode, r.stderr), (0, ""))                      # round 退 10＝loop 正常停
        self.assertFalse((self.ws / "out").exists())

    def test_registries_relative_and_found(self):
        parts = json.loads((NIA / "parts.json").read_text())["parts"]
        tools = json.loads((NIA / "tools.json").read_text())["tools"]
        for row in list(parts.values()) + list(tools.values()):
            self.assertFalse(os.path.isabs(row["path"]), row)                    # 手寫相對路徑：repo 搬家不斷
        self.assertEqual(parts["endpoint/default"]["path"], "../../lib/endpoint/fake")
        for slot in parts:
            r = subprocess.run([PARTS, "--file", str(NIA / "parts.json"), "which", slot], capture_output=True, text=True,
                               env=env(), cwd=self.ws)
            self.assertEqual(r.returncode, 0, (slot, r.stderr))
            self.assertTrue(os.path.isdir(r.stdout.strip()), slot)


class Spawn(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = t.name

    def test_spawn_nia_absolute_and_answers(self):
        code, res, err = ai(self.root, "spawn", "n1", "--from", "agent-nia")
        self.assertEqual(code, 0, err)
        self.assertEqual(res["tools"], ["clock", "math"])
        agent = Path(res["agent"])
        for reg, key in (("parts.json", "parts"), ("tools.json", "tools")):
            for name, row in json.loads((agent / reg).read_text())[key].items():
                self.assertTrue(os.path.isabs(row["path"]), (reg, name, row))
                self.assertTrue(os.path.isdir(row["path"]), (reg, name, row))
        env_litellm = json.loads((agent / "parts.json").read_text())["parts"]["endpoint/litellm"]["env"]
        self.assertEqual(env_litellm["AOS_BRAIN_URL"], "http://localhost:4000/v1")   # env 照抄
        code, q, err = ai(self.root, "ask", "n1", "--", "現在幾點？")
        self.assertEqual(code, 0, err)
        code, r, err = ai(self.root, "run", "n1", "--timeout", "60")
        self.assertEqual(code, 0, err)
        self.assertTrue(r["ok"], r)
        self.assertEqual([a["id"] for a in r["answers"]], [q["id"]])
        self.assertTrue(r["answers"][0]["text"].startswith("FAKE ANSWER to: 現在幾點？（clock said:"), r)

    def test_spawn_without_parts_unchanged(self):
        code, res, err = ai(self.root, "spawn", "d1", "--from", "agent-dan")
        self.assertEqual(code, 0, err)
        agent = Path(res["agent"])
        self.assertEqual((agent / "tools.json").read_bytes(), (ROOT / "demo" / "agent-dan" / "tools.json").read_bytes())
        self.assertFalse((agent / "parts.json").exists())


if __name__ == "__main__":
    unittest.main()
