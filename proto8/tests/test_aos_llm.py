"""test_aos_llm - bin/aos-llm（改定義裡的腦設定）與 agent-fsm 的 llm／tools 子介面（11-04 aos-agent 步 2、3；thinking 2026-11/04/aos-agent 03/02）：
aos-llm XXX show|set 叫 <XXX>/<宣告的 llm 資料夾> def …；agent-fsm 的 llm/llm.py（def＝../.env、stack＝$AOS_STACK/llm.json）；
brain.py／act.py 先看 $AOS_STACK/tools.json、brain.py 讀 $AOS_STACK/llm.json 蓋過 AOS_BRAIN_*。腦一律本機假端點（test_agent_fsm 的 FakeBrain）。"""
import json, os, shutil, subprocess, tempfile, unittest
from pathlib import Path
import own_error  # noqa: E402
own_error.install()

from aos_bins import ROOT, EXEC, tool, path_with  # noqa: E402
from test_agent_fsm import FakeBrain, CLEAR  # noqa: E402
from test_eca_llm import copy_demo  # noqa: E402
LLM = ROOT / "bin" / "aos-llm"
FSM = ROOT / "demo" / "agent-fsm"
CLOCK = ROOT / "lib" / "base" / "clock"


class AosLlm(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="aos-llm-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.fsm = self.tmp / "fsm"
        shutil.copytree(FSM, self.fsm)
        (self.fsm / "tools.json").write_text(json.dumps({"tools": {"clock": {"path": str(CLOCK)}}}))
        self.eca = copy_demo(self.tmp / "eca")
        self.ws = self.tmp / "ws"
        self.ws.mkdir()
        self.stack = self.tmp / "stack"
        self.stack.mkdir()

    def env(self, extra=None):
        e = {k: v for k, v in os.environ.items() if k not in CLEAR}
        e.update(PATH=path_with())
        e.update(extra or {})
        return e

    def run_(self, argv, extra=None, input=None):
        return subprocess.run([str(a) for a in argv], capture_output=True, text=True, env=self.env(extra), timeout=60,
                              input=input, stdin=None if input is not None else subprocess.DEVNULL)

    def code(self, r):
        return (r.returncode, (r.stderr.split() + ["", ""])[1])

    def test_show_set_both(self):
        """兩個範本各 show（fsm：url、model、key；eca：kind、model）；set model=x 改到定義（fsm 的 .env、eca 的 cli.json）、
        定義裡沒多出 .stack；沒給動作＝show。"""
        r = self.run_([LLM, self.fsm])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([l.split("=")[0] for l in r.stdout.splitlines()], ["url", "model", "key"])
        self.assertIn("model=chatgpt-gpt-6-luna-low", r.stdout.splitlines())
        r = self.run_([LLM, self.fsm, "set", "model=x"])
        self.assertEqual((r.returncode, r.stdout.splitlines()[1]), (0, "model=x"), r.stderr)
        self.assertIn("AOS_BRAIN_MODEL=x\n", (self.fsm / ".env").read_text())
        r = self.run_([LLM, self.eca, "show"])
        self.assertEqual((r.returncode, r.stdout), (0, "kind=claude\nmodel=sonnet\n"), r.stderr)
        r = self.run_([LLM, self.eca, "set", "model=x"])
        self.assertEqual((r.returncode, r.stdout), (0, "kind=claude\nmodel=x\n"), r.stderr)
        self.assertIn('"--model", "x"', (self.eca / "cli.json").read_text())
        self.assertFalse((self.fsm / ".stack").exists() or (self.eca / ".stack").exists())
        r = self.run_([LLM, self.fsm, "set", "zzz=1"])                       # 入口自己的錯：它自己說、結束碼照傳
        self.assertEqual((r.returncode, "KeyUnknown" in r.stderr), (1, True), r.stderr)

    def test_errors(self):
        """沒宣告（沒 interfaces.json、沒 aos-agent key）＝InterfaceMissing；沒宣告 llm＝LlmMissing；llm/ 沒宣告 aos-agent/llm＝LlmBad；
        interfaces.json 壞＝InterfaceBad；XXX 不是資料夾＝PathMissing；動作不認得＝ArgumentsBad。"""
        bare = self.tmp / "bare"
        bare.mkdir()
        self.assertEqual(self.code(self.run_([LLM, bare])), (1, "InterfaceMissing"))
        (bare / "interfaces.json").write_text('{"other": {}}')
        self.assertEqual(self.code(self.run_([LLM, bare])), (1, "InterfaceMissing"))
        (bare / "interfaces.json").write_text('{"aos-agent": {}}')
        self.assertEqual(self.code(self.run_([LLM, bare])), (1, "LlmMissing"))
        (bare / "interfaces.json").write_text("[壞")
        self.assertEqual(self.code(self.run_([LLM, bare])), (1, "InterfaceBad"))
        (self.fsm / "llm" / "interfaces.json").unlink()
        self.assertEqual(self.code(self.run_([LLM, self.fsm])), (1, "LlmBad"))
        self.assertEqual(self.code(self.run_([LLM, self.tmp / "none"])), (1, "PathMissing"))
        self.assertEqual(self.code(self.run_([LLM, self.eca, "reset"])), (1, "ArgumentsBad"))

    def fsm_llm(self, *args):
        return self.run_([EXEC, "--ws", self.ws, "--stack", self.stack, self.fsm / "llm"] + list(args))

    def test_fsm_llm_stack(self):
        """agent-fsm llm 入口 stack 對象：set model=x 寫 llm.json（.env 不動）、show 印副本值＋stderr「副本：model」；key 印 ***；reset 刪檔。"""
        env_before = (self.fsm / ".env").read_text()
        r = self.fsm_llm("stack", "set", "model=x", "key=sk-1")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.splitlines()[1:], ["model=x", "key=***"])
        self.assertIn("副本：model key", r.stderr)
        self.assertEqual(json.loads((self.stack / "llm.json").read_text()), {"model": "x", "key": "sk-1"})
        self.assertEqual((self.fsm / ".env").read_text(), env_before)
        self.assertEqual(self.fsm_llm("stack", "reset").returncode, 0)
        self.assertFalse((self.stack / "llm.json").exists())
        self.assertEqual(self.code(self.run_(["python3", self.fsm / "llm" / "llm.py", "stack", "show"])), (1, "StackMissing"))

    def think(self, brain, extra=None):
        """跑一次 think 格（brain.py，cwd＝範本），history 先放一則 user。"""
        (self.stack / "history.jsonl").write_text(json.dumps({"role": "user", "content": "幾點"}) + "\n")
        return subprocess.run(["python3", "brain.py", "--system", "system.txt"], cwd=str(self.fsm), capture_output=True, text=True,
                              timeout=60, stdin=subprocess.DEVNULL,
                              env=self.env(dict({"AOS_CD": str(self.fsm), "AOS_STACK": str(self.stack), "AOS_WS": str(self.ws),
                                                 "AOS_BRAIN_URL": brain.url, "AOS_BRAIN_MODEL": "m0"}, **(extra or {}))))

    def test_fsm_brain_copies(self):
        """stack 有 llm.json 的 model＝假端點收到的 model 是它（蓋過 AOS_BRAIN_MODEL）；stack 有 tools.json 登記第二個工具＝腦看得到它
        （副本整份取代定義的）；沒副本＝定義的 clock、環境的 m0；llm.json 壞＝CfgBad。"""
        brain = FakeBrain(self)
        r = self.think(brain)
        self.assertEqual(r.returncode, 0, r.stderr)
        req = brain.requests[-1]
        self.assertEqual((req["model"], [t["function"]["name"] for t in req["tools"]]), ("m0", ["clock"]))
        (self.stack / "llm.json").write_text('{"model": "x"}')
        (self.stack / "tools.json").write_text(json.dumps({"tools": {"tick": {"path": str(CLOCK)}, "clock": {"path": str(CLOCK)}}}))
        r = self.think(brain)
        self.assertEqual(r.returncode, 0, r.stderr)
        req = brain.requests[-1]
        self.assertEqual((req["model"], sorted(t["function"]["name"] for t in req["tools"])), ("x", ["clock", "tick"]))
        (self.stack / "llm.json").write_text("{壞")
        self.assertEqual(self.code(self.think(brain)), (1, "CfgBad"))


if __name__ == "__main__":
    unittest.main()
