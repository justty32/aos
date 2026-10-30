"""test_nia - agent-round 落地第 6、7 步：範本 demo/agent-nia（parts.json 手寫相對路徑指 lib 的格）與 aos-ai spawn 的 parts.json 範本。

範本（10-30 起題目經 queue 格 push 進 $AOS_STACK/queue/、答案看 history，agent-lifecycle 第 3 步）：aos-exec 跑一題（假腦叫 clock 再答）、
  § 5 的檔在 stack、trace 有 compact 那格、loop 的 state 窗收工是 done；兩題＝round 退 0 後 loop 再叫、答完退 10 正常停；
  沒題＝loop 第一次就停、結束碼 0；parts.json 的 round 給 ROUND_ON_EMPTY=stop、loop.json 開 ctl／state 窗；
  parts.json／tools.json 只用相對路徑、每格 aos-parts which 找得到。
spawn：--from agent-nia 後 parts.json、tools.json 指出範本的相對路徑改成絕對、搬到 agents/<名>/agent/ 後經 queue 放一題、
  aos-exec 跑起來答得出來（10-30 起不經 aos-ai ask／run：那兩個還照舊協議放 new/、等 out/）；
  沒有 parts.json 的範本（agent-dan）tools.json 一個字不動。
ask_round（lib/aos，第 11 步：round 當外部接口；10-30 起放進 queue、答案看 history，agent-lifecycle 第 5 步）：
  登記進 tools.json、aos-tools call 拿到假腦答案、agent 不常駐（工作區在工具小格、只有 .stack、queue 收乾淨）；
  工具小資料夾 .env 固定 ASK_AGENT；round 中途 yield 時重叫到答完、ASK_MAX_ROUNDS 用完＝AnswerMissing；round 失敗＝RoundFailed；參數錯。
設計：proto8/thinking/2026-10-28-agent-round.md § 1、§ 6、§ 7 第 6、7、11 步、文末 39～。"""
import json, os, subprocess, tempfile, unittest
from pathlib import Path

from aos_bins import ROOT, EXEC, path_with  # noqa: E402
from test_ai_tools import ai  # noqa: E402

NIA = ROOT / "demo" / "agent-nia"
PARTS = str(ROOT / "bin" / "aos-parts")
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_CF", "AOS_CD", "AOS_CO", "AOS_BRAIN_URL", "AOS_BRAIN_MODEL",
         "AOS_BRAIN_KEY", "AOS_AI_ROOT", "MAX_BYTES", "MAX_RETRIES", "MAX_PARALLEL", "ENDPOINT_NAME", "ROUND_ON_EMPTY")


def env():
    e = {k: v for k, v in os.environ.items() if k not in CLEAR}
    e["PATH"] = path_with(e.get("PATH", ""))
    return e


def push(agent, ws, text):
    """經 agent 的 queue 格（aos-parts run queue）放一則 user 進 <ws>/.stack/queue/；回信號。"""
    e = dict(env(), AOS_WS=str(ws))
    r = subprocess.run([PARTS, "--file", str(Path(agent) / "parts.json"), "run", "queue", str(agent), "push"],
                       input=json.dumps({"role": "user", "content": text}, ensure_ascii=False),
                       capture_output=True, text=True, env=e, timeout=60)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def history(ws):
    p = Path(ws) / ".stack" / "history.jsonl"
    return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []


def answers(ws):
    """history 裡每則沒有 tool_calls 的 assistant 的 content（一題一個答案）。"""
    return [m["content"] for m in history(ws) if m["role"] == "assistant" and not m.get("tool_calls")]


def queue_ls(ws, stage):
    d = Path(ws) / ".stack" / "queue" / stage
    return sorted(p.name for p in d.iterdir()) if d.is_dir() else []


class Template(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.ws = Path(t.name)

    def put(self, text):
        return push(NIA, self.ws, text)

    def run_nia(self):
        return subprocess.run([EXEC, str(NIA)], capture_output=True, text=True, env=env(), cwd=self.ws, timeout=120)

    def units(self):
        return [json.loads(l)["unit"] for l in (self.ws / ".stack" / "trace.jsonl").read_text().splitlines()]

    def test_one_question(self):
        self.put("現在幾點？")
        r = self.run_nia()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(len(answers(self.ws)), 1)
        self.assertRegex(answers(self.ws)[0], r"^FAKE ANSWER to: 現在幾點？（clock said: \d{4}-.*Z）$")
        self.assertEqual(sorted(p.name for p in (self.ws / ".stack").iterdir()),
                         ["clock", "history.jsonl", "live.jsonl", "queue", "state.json", "trace.jsonl"])   # clock＝工具的小格（P-17）
        self.assertEqual(sorted(p.name for p in self.ws.iterdir()), [".stack"])           # 工作區不長 new/ out/ 這些
        self.assertEqual((queue_ls(self.ws, "new"), queue_ls(self.ws, "cur")), ([], []))
        self.assertEqual(json.loads((self.ws / ".stack" / "state.json").read_text())["phase"], "done")   # loop 的 state 窗
        self.assertEqual([m["role"] for m in history(self.ws)], ["user", "assistant", "tool", "assistant"])
        u = self.units()
        self.assertEqual(u.count("hook/pre_think"), 2)                          # compact 預設掛在 pre_think、沒超過不動
        self.assertEqual((u[0], u[-1]), ("queue claim", "queue finish"))

    def test_two_questions_loop_calls_round_again(self):
        self.put("幾點？")
        self.put("1+1？")
        r = self.run_nia()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        got = answers(self.ws)
        self.assertEqual(len(got), 2)
        self.assertTrue(got[0].startswith("FAKE ANSWER to: 幾點？") and got[1].startswith("FAKE ANSWER to: 1+1？"), got)   # 照放的順序
        self.assertEqual((queue_ls(self.ws, "new"), queue_ls(self.ws, "cur")), ([], []))
        self.assertEqual(self.units().count("queue claim"), 2)                   # 一題一輪：round 退 0 → loop 再叫

    def test_no_question_loop_stops_ok(self):
        r = self.run_nia()
        self.assertEqual((r.returncode, r.stderr), (0, ""))                      # round 退 10＝loop 正常停
        self.assertEqual(history(self.ws), [])

    def test_registries_relative_and_found(self):
        parts = json.loads((NIA / "parts.json").read_text())["parts"]
        tools = json.loads((NIA / "tools.json").read_text())["tools"]
        for row in list(parts.values()) + list(tools.values()):
            self.assertFalse(os.path.isabs(row["path"]), row)                    # 手寫相對路徑：repo 搬家不斷
        self.assertEqual(parts["endpoint/default"]["path"], "../../lib/endpoint/fake")
        self.assertEqual(parts["round"]["env"], {"ROUND_ON_EMPTY": "stop"})        # 範本預設射後不理
        loop = json.loads((NIA / "loop.json").read_text())
        self.assertEqual((loop["ctl"], loop["state"]), ("ctl.json", "state.json"))   # 窗開在 $AOS_STACK
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
        ws = Path(res["ws"])
        push(agent, ws, "現在幾點？")
        r = subprocess.run([EXEC, "--ws", str(ws), str(agent)], capture_output=True, text=True, env=env(), timeout=120)
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        got = answers(ws)
        self.assertEqual(len(got), 1)
        self.assertTrue(got[0].startswith("FAKE ANSWER to: 現在幾點？（clock said:"), got)

    def test_spawn_without_parts_unchanged(self):
        code, res, err = ai(self.root, "spawn", "d1", "--from", "agent-dan")
        self.assertEqual(code, 0, err)
        agent = Path(res["agent"])
        self.assertEqual((agent / "tools.json").read_bytes(), (ROOT / "demo" / "agent-dan" / "tools.json").read_bytes())
        self.assertFalse((agent / "parts.json").exists())


ASK = ROOT / "lib" / "aos" / "ask_round"
TOOLS = str(ROOT / "bin" / "aos-tools")


class AskRound(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.tmp = Path(t.name)
        self.boss = self.tmp / "boss"
        self.boss.mkdir()
        self.stack = self.tmp / "stack"

    def add(self, target):
        r = subprocess.run([TOOLS, "--file", str(self.boss / "tools.json"), "add", str(target)], capture_output=True,
                           text=True, env=env())
        self.assertEqual(r.returncode, 0, r.stderr)

    def call(self, name, args, extra=None):
        e = env()
        e.update({"AOS_WS": str(self.tmp), "AOS_STACK": str(self.stack / name) + "/"})
        e.update(extra or {})
        return subprocess.run([TOOLS, "--file", str(self.boss / "tools.json"), "call", name], input=json.dumps(args),
                              capture_output=True, text=True, env=e, cwd=self.tmp, timeout=120)

    def code(self, r):
        last = r.stderr.strip().splitlines()[-1]
        self.assertTrue(last.startswith("ask_round: "), r.stderr)
        self.assertEqual(r.stdout.strip().splitlines()[-1], last)                 # 錯也印在 stdout（給腦看）
        return (r.returncode, last.split()[1])

    def own_agent(self, pause=None):
        """agent-nia 的格（絕對路徑）＋可選的 hook/pause。"""
        a = self.tmp / "agent"
        a.mkdir()
        parts = json.loads((NIA / "parts.json").read_text())["parts"]
        for row in parts.values():
            row["path"] = os.path.normpath(os.path.join(NIA, row["path"]))
        if pause:
            h = self.tmp / "pause"
            h.mkdir()
            (h / "_entry").write_text("#!/bin/sh\n" + pause)
            (h / "_entry").chmod(0o755)
            parts["hook/pause"] = {"path": str(h)}
        (a / "parts.json").write_text(json.dumps({"parts": parts}))
        (a / "tools.json").write_text(json.dumps({"tools": {"clock": {"path": str(ROOT / "lib" / "base" / "clock")}}}))
        return a

    def test_registered_and_called(self):
        self.add(ASK)
        r = self.call("ask_round", {"question": "現在幾點？", "agent": str(NIA)})
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertRegex(r.stdout, r"^FAKE ANSWER to: 現在幾點？（clock said: \d{4}-.*Z）\n$")
        ws = self.stack / "ask_round" / "agent-nia"                                   # 工作區＝工具的小格（P-17）
        self.assertEqual(sorted(p.name for p in ws.iterdir()), [".stack"])            # 不長 new/ out/
        self.assertEqual([m["role"] for m in history(ws)], ["user", "assistant", "tool", "assistant"])
        self.assertEqual((queue_ls(ws, "new"), queue_ls(ws, "cur")), ([], []))        # 答完就停、不常駐

    def test_fixed_agent_by_cell_env(self):
        cell = self.boss / "tools" / "ask_nia"
        cell.mkdir(parents=True)
        for f in ("_entry", "_tooldef.json", "_metainfo"):
            (cell / f).symlink_to(ASK / f)
        (cell / ".env").write_text("ASK_AGENT=%s\n" % NIA)
        self.add(cell)
        r = self.call("ask_nia", {"question": "1+1？"})
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertTrue(r.stdout.startswith("FAKE ANSWER to: 1+1？"), r.stdout)

    def test_yield_rounds_until_answer_and_limit(self):
        agent = self.own_agent(pause="exit 10\n")                                    # 每批工具後 yield：要叫兩次 round
        self.add(ASK)
        r = self.call("ask_round", {"question": "幾點？", "agent": str(agent)})
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertTrue(r.stdout.startswith("FAKE ANSWER to: 幾點？"), r.stdout)
        r = self.call("ask_round", {"question": "再一次", "agent": str(agent)}, {"ASK_MAX_ROUNDS": "1"})
        self.assertEqual(self.code(r), (1, "AnswerMissing"))
        ws = self.stack / "ask_round" / "agent"
        self.assertEqual(len(queue_ls(ws, "cur")), 1)                                   # 沒答完：信留在 cur/，再叫會接著做

    def test_round_failed_and_argument_errors(self):
        agent = self.own_agent()
        parts = json.loads((agent / "parts.json").read_text())
        parts["parts"]["endpoint/default"] = {"path": str(ROOT / "lib" / "endpoint" / "openai")}   # 沒 AOS_BRAIN_URL＝UrlMissing
        (agent / "parts.json").write_text(json.dumps(parts))
        self.add(ASK)
        r = self.call("ask_round", {"question": "q", "agent": str(agent)})
        self.assertEqual(self.code(r), (1, "RoundFailed"))
        self.assertIn("endpoint: UrlMissing", r.stderr)                                 # 下層自己說、不轉述
        self.assertEqual(self.code(self.call("ask_round", {"question": "q"})), (1, "AgentMissing"))
        self.assertEqual(self.code(self.call("ask_round", {"question": "q", "agent": "agent"})), (1, "AgentBad"))
        self.assertEqual(self.code(self.call("ask_round", {"agent": str(agent)})), (1, "ArgumentsBad"))
        self.assertEqual(self.code(self.call("ask_round", {"question": "q", "agent": str(agent), "timeout_s": 0})),
                         (1, "ArgumentsBad"))


if __name__ == "__main__":
    unittest.main()
