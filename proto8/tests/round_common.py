"""round_common - test_round_*.py 共用的常數與底座（10-31 自 test_round.py 拆出，行為不變）：
EXEC／PARTS／FAKE／OPENAI／ACT／CLOCK 路徑、CLEAR、err_code、Base（tmp agent／ws、env、cell、lines）、req、user；
ROUND、AGENT_LIB 與 AgentCase（RoundFsm 與 AosRound 共用）。"""
import json, os, re, subprocess, tempfile, unittest
from pathlib import Path

from aos_bins import ROOT, tool, path_with  # noqa: E402

EXEC = tool("aos-exec")
PARTS = str(ROOT / "bin" / "aos-parts")
FAKE = str(ROOT / "lib" / "endpoint" / "fake")
OPENAI = str(ROOT / "lib" / "endpoint" / "openai")
ACT = str(ROOT / "lib" / "agent" / "act")
CLOCK = str(ROOT / "lib" / "base" / "clock")
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_CF", "AOS_CD", "AOS_CO", "AOS_BRAIN_URL", "AOS_BRAIN_MODEL",
         "AOS_BRAIN_KEY", "AOS_KERNEL_REPORT", "AOS_ENDPOINT_TIMEOUT_MS", "AOS_ENDPOINT_NAME", "AOS_ACT_MAX_PARALLEL", "AOS_ROUND_MAX_RETRIES", "AOS_ROUND_ON_EMPTY")


def err_code(prog, stderr):
    """stderr 最後一行要是「prog: 代號 原因」；回代號。"""
    last = stderr.strip().splitlines()[-1]
    m = re.match(r"%s: ([A-Z][A-Za-z]+) \S" % prog, last)
    assert m, "錯誤行格式不對：%r" % stderr
    return m.group(1)



class Base(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.addCleanup(self._t.cleanup)
        self.tmp = Path(self._t.name)
        self.agent = self.tmp / "agent"
        self.agent.mkdir()
        self.ws = self.tmp / "ws"
        self.ws.mkdir()
        self.stack = self.ws / ".stack"

    def env(self, extra=None):
        e = {k: v for k, v in os.environ.items() if k not in CLEAR}
        e["PATH"] = path_with(e.get("PATH", ""))
        e["AOS_WS"] = str(self.ws)
        e["AOS_STACK"] = str(self.stack) + "/"
        e.update(extra or {})
        return e

    def cell(self, path, stdin, env=None, args=None):
        args = [str(self.agent)] if args is None else args
        return subprocess.run([EXEC, path] + args, input=stdin, capture_output=True, text=True,
                              env=self.env(env), cwd=self.tmp, timeout=60)

    def lines(self, text):
        return [json.loads(l) for l in text.splitlines()]


def req(*messages, tools=None):
    body = {"messages": list(messages)}
    if tools is not None:
        body["tools"] = tools
    return json.dumps(body, ensure_ascii=False)


def user(text):
    return {"role": "user", "content": text}



ROUND = str(ROOT / "lib" / "agent" / "round")
AGENT_LIB = ROOT / "lib" / "agent"


class AgentCase(Base):
    """tmp agent（queue、history、act、fake 腦、tools.json 只有 clock）＋queue 裡一題；RoundFsm 與 AosRound 共用。"""

    def setUp(self):
        super().setUp()
        self.parts = {"queue": {"path": str(AGENT_LIB / "queue")},
                      "history": {"path": str(AGENT_LIB / "history")}, "act": {"path": ACT},
                      "endpoint/default": {"path": FAKE}}
        self.save()
        (self.agent / "tools.json").write_text(json.dumps({"tools": {"clock": {"path": CLOCK}}}))
        self.q1 = self.put("幾點？")

    def save(self):
        (self.agent / "parts.json").write_text(json.dumps({"parts": self.parts}, ensure_ascii=False))

    def put(self, text):
        """經 queue 格放一則 user（同 aos-say）；回信號。"""
        r = subprocess.run([EXEC, str(AGENT_LIB / "queue"), str(self.agent), "push"], input=json.dumps(user(text)),
                           capture_output=True, text=True, env=self.env(), cwd=self.tmp, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def answer(self):
        """history 最新那則沒有 tool_calls 的 assistant 的 content（答案）。"""
        for m in reversed(self.history()):
            if m["role"] == "assistant" and not m.get("tool_calls"):
                return m["content"]
        return None

    def script(self, name, body, sh=True):
        p = self.tmp / "scripts" / name
        p.mkdir(parents=True)
        (p / "_entry").write_text(("#!/bin/sh\n" if sh else "") + body)
        (p / "_entry").chmod(0o755)
        return str(p)

    def hook(self, point, body):
        self.parts["hook/" + point] = {"path": self.script("hook_" + point, body)}
        self.save()

    def history(self):
        p = self.stack / "history.jsonl"
        return self.lines(p.read_text()) if p.exists() else []

    def ls(self, stage):
        d = self.stack / "queue" / stage
        return sorted(x.name for x in d.iterdir()) if d.is_dir() else []
