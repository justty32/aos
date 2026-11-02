"""test_nia - agent-round 落地第 6、7 步：範本 demo/agent-nia（parts.json 手寫相對路徑指 lib 的格）與 aos-ai spawn 的 parts.json 範本。

範本（10-30 起題目經 queue 格 push 進 $AOS_STACK/queue/、答案看 history，agent-lifecycle 第 3 步）：aos-exec 跑一題（假腦叫 clock 再答）、
  § 5 的檔在 stack、loop 的 state 窗收工是 done；loop.json 叫 aos-fsm 跑 lib/agent/round 的表，trace 是 fsm 的一格一行
  （idle → think → act → think → finish → idle 退 10）；兩題＝finish 兩次、最後 idle 退 10 正常停；
  沒題＝loop 第一次就停、結束碼 0；loop.json 是 aos-fsm fsm-stop.json、cwd 指 lib/agent/round、開 ctl／state 窗；
  parts.json（11-01 起 aos-exec 格式）／tools.json 只用相對路徑、每格 lib/agent/parts.py 找得到。
spawn：--from agent-nia 後 parts.json、tools.json、loop.json 的 cwd 指出範本的相對路徑改成絕對、搬到 agents/<名>/agent/ 後經 queue 放一題、
  aos-exec 跑起來答得出來（10-30 起不經 aos-ai ask／run：那兩個還照舊協議放 new/、等 out/）；
  沒有 parts.json 的範本（agent-eve；11-02 晚前是 agent-dan）tools.json 一個字不動。
ask_round（lib/aos，第 11 步：round 當外部接口；10-30 起放進 queue、答案看 history，agent-lifecycle 第 5 步）：
  登記進 tools.json、aos-tools call 拿到假腦答案、agent 不常駐（工作區在工具小格、只有 .stack、queue 收乾淨）；
  工具小資料夾的 _entry 是 JSON argv 陣列 [ask_round, --agent …] 固定一隻（11-01 起旗標取代環境變數，舊的不再讀）；
  一格一格叫 aos-exec <agent>/loop.json#/exec：--max-steps 用完＝AnswerMissing、再叫（同一個 --ws）接著做；
  被問的 agent 的表是 fsm-idle.json 也答完就停（看信不見了）；那格失敗、沒有 loop.json＝RoundFailed；參數錯。
設計：proto8/thinking/2026-10-28-agent-round.md § 1、§ 6、§ 7 第 6、7、11 步、文末 39～。"""
import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path

from aos_bins import ROOT, EXEC, path_with  # noqa: E402
from test_ai_tools import ai  # noqa: E402
from round_common import absolute  # noqa: E402
sys.path.insert(0, str(ROOT / "lib" / "agent"))
import parts as lib_parts  # noqa: E402

NIA = ROOT / "demo" / "agent-nia"
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_CF", "AOS_CD", "AOS_CO", "AOS_BRAIN_URL", "AOS_BRAIN_MODEL",
         "AOS_BRAIN_KEY", "AOS_AI_ROOT")


def env():
    e = {k: v for k, v in os.environ.items() if k not in CLEAR}
    e["PATH"] = path_with(e.get("PATH", ""))
    return e


def push(agent, ws, text):
    """經 agent 的 queue 格（aos-exec <agent>/parts.json#/queue）放一則 user 進 <ws>/.stack/queue/；回信號。"""
    e = dict(env(), AOS_WS=str(ws))
    r = subprocess.run([EXEC, str(Path(agent) / "parts.json") + "#/queue", str(agent), "push"],
                       input=json.dumps({"role": "user", "content": text}, ensure_ascii=False),
                       capture_output=True, text=True, env=e, timeout=60)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def leaves(table):
    """parts.json（aos-exec 格式）裡的路徑：字串槽值與 _entry（.env 不算）。"""
    if isinstance(table, str):
        return [table]
    return [p for k, v in table.items() if k != ".env" for p in leaves(v)] if isinstance(table, dict) else []


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

    def states(self):
        """fsm trace 的 (state, code)：一格一行（10-30 起，原本看 round 的 unit 行）。"""
        return [(t["state"], t["code"]) for t in map(json.loads, (self.ws / ".stack" / "trace.jsonl").read_text().splitlines())]

    def test_one_question(self):
        self.put("現在幾點？")
        r = self.run_nia()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(len(answers(self.ws)), 1)
        self.assertRegex(answers(self.ws)[0], r"^FAKE ANSWER to: 現在幾點？（clock said: \d{4}-.*Z）$")
        self.assertEqual(sorted(p.name for p in (self.ws / ".stack").iterdir()),
                         ["history.jsonl", "live.jsonl", "queue", "state.json", "state.txt", "tools", "trace.jsonl"])   # tools/clock＝工具的小格（P-17；11-02 進 tools/）；state.txt＝fsm 的
        self.assertEqual(sorted(p.name for p in self.ws.iterdir()), [".stack"])           # 工作區不長 new/ out/ 這些
        self.assertEqual((queue_ls(self.ws, "new"), queue_ls(self.ws, "cur")), ([], []))
        self.assertEqual(json.loads((self.ws / ".stack" / "state.json").read_text())["phase"], "done")   # loop 的 state 窗
        self.assertEqual([m["role"] for m in history(self.ws)], ["user", "assistant", "tool", "assistant"])
        self.assertEqual(self.states(), [("idle", 0), ("think", 0), ("act", 0), ("think", 10), ("finish", 0), ("idle", 10)])
        self.assertEqual((self.ws / ".stack" / "state.txt").read_text().strip(), "idle")   # 一題答完、停在起點

    def test_two_questions_loop_calls_round_again(self):
        self.put("幾點？")
        self.put("1+1？")
        r = self.run_nia()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        got = answers(self.ws)
        self.assertEqual(len(got), 2)
        self.assertTrue(got[0].startswith("FAKE ANSWER to: 幾點？") and got[1].startswith("FAKE ANSWER to: 1+1？"), got)   # 照放的順序
        self.assertEqual((queue_ls(self.ws, "new"), queue_ls(self.ws, "cur")), ([], []))
        self.assertEqual([x for x, _ in self.states()].count("finish"), 2)       # 一題交卷一次；finish → idle 接著認下一題
        self.assertEqual(self.states()[-1], ("idle", 10))

    def test_no_question_loop_stops_ok(self):
        r = self.run_nia()
        self.assertEqual((r.returncode, r.stderr), (0, ""))                      # idle 退 10、表沒接＝fsm 退 10＝loop 正常停
        self.assertEqual(history(self.ws), [])
        self.assertEqual(self.states(), [("idle", 10)])

    def test_registries_relative_and_found(self):
        parts = json.loads((NIA / "parts.json").read_text())
        tools = json.loads((NIA / "tools.json").read_text())["tools"]
        for path in leaves(parts) + [row["path"] for row in tools.values()]:
            self.assertFalse(os.path.isabs(path), path)                         # 手寫相對路徑：repo 搬家不斷
        self.assertNotIn("parts", parts)                                         # 11-01 起整份就是槽表
        self.assertEqual(parts["endpoint"]["default"], "../../lib/endpoint/fake")
        self.assertNotIn("round", parts)                                              # 11-01 起 round 槽沒了：停法走 argv
        loop = json.loads((NIA / "loop.json").read_text())
        self.assertEqual((loop["ctl"], loop["state"]), ("ctl.json", "state.json"))   # 窗開在 $AOS_STACK
        self.assertEqual(loop["exec"], {"argv": ["aos-fsm", "fsm-stop.json"], "cwd": "../../lib/agent/round",
                                        "timeout_ms": 600000})                     # 射後不理；timeout_ms 管一格
        self.assertTrue((NIA / loop["exec"]["cwd"] / "fsm-stop.json").is_file())
        self.assertEqual(parts["hook"]["pre_think"], "../../lib/agent/compact")      # compact 預設掛在 pre_think（門檻用預設、不帶 argv）
        for slot in ("queue", "history", "act", "hook/pre_think", "endpoint/default", "endpoint/litellm"):
            self.assertEqual(lib_parts.find(str(NIA), slot), "%s/parts.json#/%s" % (NIA, slot))
        for path in leaves(absolute(parts, NIA)):
            self.assertTrue(os.path.isdir(path), path)


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
        paths = leaves(json.loads((agent / "parts.json").read_text()))
        paths += [row["path"] for row in json.loads((agent / "tools.json").read_text())["tools"].values()]
        paths.append(json.loads((agent / "loop.json").read_text())["exec"]["cwd"])   # lib/agent/round
        for path in paths:
            self.assertTrue(os.path.isabs(path) and os.path.isdir(path), path)
        env_litellm = json.loads((agent / "parts.json").read_text())["endpoint"]["litellm"][".env"]
        self.assertEqual(env_litellm["AOS_BRAIN_URL"], "http://localhost:4000/v1")   # env 照抄
        ws = Path(res["ws"])
        push(agent, ws, "現在幾點？")
        r = subprocess.run([EXEC, "--ws", str(ws), str(agent)], capture_output=True, text=True, env=env(), timeout=120)
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        got = answers(ws)
        self.assertEqual(len(got), 1)
        self.assertTrue(got[0].startswith("FAKE ANSWER to: 現在幾點？（clock said:"), got)

    def test_spawn_without_parts_unchanged(self):
        code, res, err = ai(self.root, "spawn", "d1", "--from", "agent-eve")
        self.assertEqual(code, 0, err)
        agent = Path(res["agent"])
        self.assertEqual((agent / "tools.json").read_bytes(), (ROOT / "demo" / "agent-eve" / "tools.json").read_bytes())
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

    def cell(self, name, *flags):
        """工具小資料夾 boss/tools/<name>：_entry＝不加 +x 的 JSON argv 陣列 [ask_round, 旗標...]（aos-exec 插 aos-exec、stdin 照接），
        _tooldef.json／_metainfo 捷徑指 ask_round 的；登記進 tools.json。"""
        cell = self.boss / "tools" / name
        cell.mkdir(parents=True)
        (cell / "_entry").write_text(json.dumps([str(ASK)] + list(flags)))
        for f in ("_tooldef.json", "_metainfo"):
            (cell / f).symlink_to(ASK / f)
        self.add(cell)
        return name

    def code(self, r):
        last = r.stderr.strip().splitlines()[-1]
        self.assertTrue(last.startswith("ask_round: "), r.stderr)
        self.assertEqual(r.stdout.strip().splitlines()[-1], last)                 # 錯也印在 stdout（給腦看）
        return (r.returncode, last.split()[1])

    def own_agent(self):
        """agent-nia 的格（絕對路徑）；loop.json 同 nia、cwd 改絕對。"""
        a = self.tmp / "agent"
        a.mkdir()
        loop = json.loads((NIA / "loop.json").read_text())
        loop["exec"]["cwd"] = os.path.normpath(os.path.join(NIA, loop["exec"]["cwd"]))
        (a / "loop.json").write_text(json.dumps(loop))
        (a / "parts.json").write_text(json.dumps(absolute(json.loads((NIA / "parts.json").read_text()), NIA)))
        (a / "tools.json").write_text(json.dumps({"tools": {"clock": {"path": str(ROOT / "lib" / "base" / "clock")}}}))
        return a

    def test_registered_and_called(self):
        self.add(ASK)
        r = self.call("ask_round", {"question": "現在幾點？", "agent": str(NIA)})
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertRegex(r.stdout, r"^FAKE ANSWER to: 現在幾點？（clock said: \d{4}-.*Z）\n$")
        ws = self.stack / "ask_round" / "tools" / "agent-nia"                                   # 工作區＝工具的小格（P-17）
        self.assertEqual(sorted(p.name for p in ws.iterdir()), [".stack"])            # 不長 new/ out/
        self.assertEqual([m["role"] for m in history(ws)], ["user", "assistant", "tool", "assistant"])
        self.assertEqual((queue_ls(ws, "new"), queue_ls(ws, "cur")), ([], []))        # 答完就停、不常駐

    def test_fixed_agent_by_cell_argv(self):
        r = self.call(self.cell("ask_nia", "--agent", str(NIA)), {"question": "1+1？"})
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertTrue(r.stdout.startswith("FAKE ANSWER to: 1+1？"), r.stdout)
        self.assertTrue((self.stack / "ask_nia" / "tools" / "agent-nia" / ".stack").is_dir())

    def test_old_env_ignored(self):
        """11-01 起舊的三個環境變數不再讀：沒給 agent＝AgentMissing；上限 0、別的工作區都不作用（照樣答、工作區在工具小格）。"""
        self.add(ASK)
        self.assertEqual(self.code(self.call("ask_round", {"question": "q"}, {"AOS_ASK_AGENT": str(NIA)})), (1, "AgentMissing"))
        other = self.tmp / "other"
        r = self.call("ask_round", {"question": "幾點？", "agent": str(NIA)},
                      {"AOS_ASK_MAX_STEPS": "0", "AOS_ASK_WS": str(other)})
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertFalse(other.exists())
        self.assertTrue((self.stack / "ask_round" / "tools" / "agent-nia" / ".stack").is_dir())

    def test_step_limit_then_resume(self):
        """--max-steps 1：只走一格（idle 認領）就 AnswerMissing、信留在 cur/；再叫一次（同一個 --ws、不設上限）從 state.txt 接著做、答得出來。"""
        agent = self.own_agent()
        ws = self.tmp / "asked"
        r = self.call(self.cell("ask1", "--max-steps", "1", "--ws", str(ws)), {"question": "幾點？", "agent": str(agent)})
        self.assertEqual(self.code(r), (1, "AnswerMissing"))
        self.assertEqual(len(queue_ls(ws, "cur")), 1)                                   # 沒答完：信留在 cur/
        self.assertEqual((ws / ".stack" / "state.txt").read_text().strip(), "think")
        r = self.call(self.cell("ask_ws", "--ws", str(ws)), {"question": "再一次", "agent": str(agent)})
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertTrue(r.stdout.startswith("FAKE ANSWER to: 再一次"), r.stdout)
        self.assertTrue(answers(ws)[0].startswith("FAKE ANSWER to: 幾點？"), answers(ws))  # 卡著的那題先接著答完
        self.assertEqual((queue_ls(ws, "new"), queue_ls(ws, "cur")), ([], []))
        for name, flags, want in (("ask0", ("--max-steps", "0"), "ArgumentsBad"), ("askx", ("--max-steps", "x"), "ArgumentsBad"),
                                  ("asknone", ("--max-steps",), "ArgumentsBad"), ("askpos", ("extra",), "ArgumentsBad"),
                                  ("asknope", ("--nope", "1"), "FlagUnknown")):
            self.assertEqual(self.code(self.call(self.cell(name, *flags), {"question": "q", "agent": str(agent)})), (1, want), name)

    def test_idle_agent_does_not_hang(self):
        """被問的 agent 的 loop.json 指 fsm-idle.json（常駐用，queue 空 fsm 也退 0）：ask_round 看信不見了就停手、不叫到次數用完。"""
        agent = self.own_agent()
        (agent / "loop.json").write_text(json.dumps({"exec": {"argv": ["aos-fsm", "fsm-idle.json"], "cwd": str(ROOT / "lib" / "agent" / "round")},
                                                     "interval_ms": 100}))
        r = self.call(self.cell("ask8", "--max-steps", "8"), {"question": "幾點？", "agent": str(agent)})
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertTrue(r.stdout.startswith("FAKE ANSWER to: 幾點？"), r.stdout)
        trace = (self.stack / "ask8" / "tools" / "agent" / ".stack" / "trace.jsonl").read_text().splitlines()
        self.assertEqual([json.loads(l)["state"] for l in trace], ["idle", "think", "act", "think", "finish"])

    def test_round_failed_and_argument_errors(self):
        agent = self.own_agent()
        parts = json.loads((agent / "parts.json").read_text())
        parts["endpoint"]["default"] = str(ROOT / "lib" / "endpoint" / "openai")   # 沒 AOS_BRAIN_URL＝UrlMissing
        (agent / "parts.json").write_text(json.dumps(parts))
        self.add(ASK)
        r = self.call("ask_round", {"question": "q", "agent": str(agent)})
        self.assertEqual(self.code(r), (1, "RoundFailed"))
        self.assertIn("endpoint: UrlMissing", r.stderr)                                 # 下層自己說、不轉述
        (agent / "loop.json").unlink()                                                   # 沒有 loop.json：aos-exec 自己報、照 RoundFailed 收
        r = self.call("ask_round", {"question": "q", "agent": str(agent)})
        self.assertEqual(self.code(r), (1, "RoundFailed"))
        self.assertIn("aos-exec: ", r.stderr)
        self.assertEqual(self.code(self.call("ask_round", {"question": "q"})), (1, "AgentMissing"))
        self.assertEqual(self.code(self.call("ask_round", {"question": "q", "agent": "agent"})), (1, "AgentBad"))
        self.assertEqual(self.code(self.call("ask_round", {"agent": str(agent)})), (1, "ArgumentsBad"))
        self.assertEqual(self.code(self.call("ask_round", {"question": "q", "agent": str(agent), "timeout_s": 0})),
                         (1, "ArgumentsBad"))


if __name__ == "__main__":
    unittest.main()
