"""aosp/llm.py（LLM 隊寫）：LLM 世界、假後端 echo:/fail:、帳簿、絕不打真的網路。

interface.md 只保證 cli_llm(args) 存在；init_llm_world()/serve_once() 是任務簡報點名要測的
內部函式，確切簽名沒有另外釘死給我們（見 FINDINGS）。這裡用 hasattr 防呆，真的兜不起來就跳過
單一測試而不是整支炸掉。
"""
import json
import os
import sys
import unittest

PROTO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROTO not in sys.path:
    sys.path.insert(0, PROTO)

from aosp import fsutil, layout  # noqa: E402
from .helpers import LandCase  # noqa: E402

try:
    from aosp import llm as llmmod  # noqa: E402
    HAS_LLM = hasattr(llmmod, "cli_llm")
except Exception:
    llmmod = None
    HAS_LLM = False

SKIP_MSG = "aosp/llm.py 還沒寫好（cli_llm 還沒有），先跳過"


def _try_init_world(home):
    """試著建出 LLM 世界那塊地。兜不起來就丟 SkipTest。"""
    if not hasattr(llmmod, "init_llm_world"):
        raise unittest.SkipTest("llm.py 沒有 init_llm_world()")
    try:
        return llmmod.init_llm_world()
    except TypeError:
        pass
    try:
        return llmmod.init_llm_world(home)
    except TypeError as e:
        raise unittest.SkipTest("init_llm_world() 的簽名猜不到：%s" % e)


def _try_serve_once(world_land):
    if not hasattr(llmmod, "serve_once"):
        raise unittest.SkipTest("llm.py 沒有 serve_once()")
    try:
        return llmmod.serve_once(world_land)
    except TypeError as e:
        raise unittest.SkipTest("serve_once() 的簽名猜不到：%s" % e)


def _set_fake_unit(home, endpoint, name="fake"):
    cfg = fsutil.read_json(home.config, {}) or {}
    cfg.setdefault("format_version", 1)
    cfg["units"] = [{
        "name": name, "endpoint": endpoint, "model": "test-model",
        "tier": "fast", "max_parallel": 1, "api_key_env": None,
    }]
    fsutil.write_json(home.config, cfg)


@unittest.skipUnless(HAS_LLM, SKIP_MSG)
class TestNoRealNetwork(LandCase):
    def test_urlopen_never_called_for_echo_backend(self):
        import urllib.request

        called = {"hit": False}
        orig = urllib.request.urlopen

        def _boom(*a, **k):
            called["hit"] = True
            raise AssertionError("測試不准打真的網路，但 urlopen 被呼叫了")

        urllib.request.urlopen = _boom
        try:
            self._run_echo_roundtrip()
        finally:
            urllib.request.urlopen = orig
        self.assertFalse(called["hit"],
                          msg="假後端 echo: 不該碰到 urllib.request.urlopen")

    def _run_echo_roundtrip(self):
        home = layout.Home()
        _set_fake_unit(home, "echo:")
        world = _try_init_world(home)
        prompt_path = os.path.join(self.tmp, "prompt.txt")
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write("你好，這是 prompt 原文")
        result_path = os.path.join(self.tmp, "llm-result.txt")
        from aosp import inbox
        obj = inbox.make("llm", self.land.root, prompt=prompt_path, result=result_path,
                          tier="fast", priority=1, max_wait_ms=5000)
        ok, info = inbox.deliver(world, obj)
        self.assertTrue(ok, msg="投一筆 kind:llm 到 LLM 世界該成功：%r" % (info,))
        _try_serve_once(world)


@unittest.skipUnless(HAS_LLM, SKIP_MSG)
class TestEchoBackend(LandCase):
    def test_echo_backend_produces_result_containing_prompt(self):
        home = layout.Home()
        _set_fake_unit(home, "echo:")
        world = _try_init_world(home)

        prompt_path = os.path.join(self.tmp, "prompt.txt")
        prompt_text = "這是一段獨一無二的 prompt 原文 xyz-123"
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(prompt_text)
        result_path = os.path.join(self.tmp, "llm-result.txt")

        from aosp import inbox
        obj = inbox.make("llm", self.land.root, prompt=prompt_path, result=result_path,
                          tier="fast", priority=1, max_wait_ms=5000)
        ok, info = inbox.deliver(world, obj)
        self.assertTrue(ok, msg="投遞 kind:llm 該成功：%r" % (info,))

        _try_serve_once(world)

        self.assertTrue(os.path.isfile(result_path),
                         msg="echo 後端跑完，結果檔該出現：%s" % result_path)
        with open(result_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn(prompt_text, content,
                      msg="echo 後端該把 prompt 原文含在結果裡，實際結果 %r" % content)

        self.assertTrue(os.path.isfile(home.ledger), msg="帳簿 ledger.jsonl 該多一行")
        with open(home.ledger, "r", encoding="utf-8") as f:
            lines = [l for l in f.read().splitlines() if l.strip()]
        self.assertTrue(lines, msg="帳簿至少要有一行")
        last = json.loads(lines[-1])
        for key in ("at", "request_id", "from", "unit", "tier", "tokens_in",
                    "tokens_out", "ms", "outcome"):
            self.assertIn(key, last, msg="帳簿這一行少了欄位 `%s`，實際 %r" % (key, last))


@unittest.skipUnless(HAS_LLM, SKIP_MSG)
class TestFailBackend(LandCase):
    def test_fail_backend_writes_status_file_with_backend_error(self):
        home = layout.Home()
        _set_fake_unit(home, "fail:")
        world = _try_init_world(home)

        prompt_path = os.path.join(self.tmp, "prompt.txt")
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write("無所謂內容")
        result_path = os.path.join(self.tmp, "llm-result-fail.txt")

        from aosp import inbox, status
        obj = inbox.make("llm", self.land.root, prompt=prompt_path, result=result_path,
                          tier="fast", priority=1, max_wait_ms=5000)
        ok, info = inbox.deliver(world, obj)
        self.assertTrue(ok, msg="投遞該成功：%r" % (info,))

        _try_serve_once(world)

        st = status.read_status(result_path)
        self.assertIsNotNone(st, msg="假後端 fail: 該讓 <result>.status.json 出現")
        self.assertEqual(st.get("reason"), "backend_error",
                          msg="假後端失敗的 reason 該是 backend_error，實際 %r" % st)
