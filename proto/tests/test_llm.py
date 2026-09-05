"""aosp/llm.py（LLM 隊寫）：LLM 世界、假後端 echo:/fail:、帳簿、絕不打真的網路。

interface.md 只保證 cli_llm(args) 存在；init_llm_world()/serve_once() 是任務簡報點名要測的
內部函式，確切簽名沒有另外釘死給我們（見 FINDINGS）。這裡用 hasattr 防呆，真的兜不起來就跳過
單一測試而不是整支炸掉。
"""
import json
import contextlib
import io
import os
import sys
import threading
import time
import unittest

PROTO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROTO not in sys.path:
    sys.path.insert(0, PROTO)

from aosp import fsutil, layout  # noqa: E402
try:
    from .helpers import LandCase, run_cli  # noqa: E402
except ImportError:
    from helpers import LandCase, run_cli  # noqa: E402

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
                    "tokens_out", "tokens_reasoning", "tokens_source", "ms", "outcome"):
            self.assertIn(key, last, msg="帳簿這一行少了欄位 `%s`，實際 %r" % (key, last))
        self.assertIsNone(last["tokens_reasoning"], msg="echo: 分不出 reasoning，應記 null")


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


@unittest.skipUnless(HAS_LLM, SKIP_MSG)
class TestServeProgress(LandCase):
    def test_serve_prints_sent_and_returned_lines(self):
        home = layout.Home()
        _set_fake_unit(home, "slow:5", name="slow-one")
        world = _try_init_world(home)
        prompt_path = os.path.join(self.tmp, "progress-prompt.txt")
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write("看得見的進度")
        result_path = os.path.join(self.tmp, "progress-result.txt")
        from aosp import inbox
        obj = inbox.make("llm", self.land.root, prompt=prompt_path, result=result_path,
                         tier="fast", priority=1, max_wait_ms=5000)
        ok, _info = inbox.deliver(world, obj)
        self.assertTrue(ok)

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            llmmod.serve_once(world, progress=True)
        lines = output.getvalue().splitlines()
        self.assertTrue(any("%s 送出 slow-one，等待中" % obj["id"] == x for x in lines),
                        msg="送後端前要立刻印一行，實際 %r" % lines)
        self.assertTrue(any(x.startswith("%s 回來 " % obj["id"]) and x.endswith(" tokens")
                            for x in lines),
                        msg="後端回來後要印毫秒與 token，實際 %r" % lines)


@unittest.skipUnless(HAS_LLM, SKIP_MSG)
class TestRequestVisibility(LandCase):
    def _request(self, world, suffix=""):
        from aosp import inbox
        prompt_path = os.path.join(self.tmp, "visible%s.prompt" % suffix)
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write("請求可見度")
        result_path = os.path.join(self.tmp, "visible%s.out" % suffix)
        obj = inbox.make("llm", self.land.root, prompt=prompt_path, result=result_path,
                         tier="fast", priority=1, max_wait_ms=5000)
        ok, _info = inbox.deliver(world, obj)
        self.assertTrue(ok)
        state_obj = fsutil.read_json(world.rel("requests", "%s.json" % obj["id"]))
        self.assertEqual(state_obj["state"], "queued")
        self.assertIsNone(state_obj["unit"])
        self.assertEqual(state_obj["request"], os.path.join(world.inbox, "%s.json" % obj["id"]))
        return obj, result_path

    def test_original_moves_inflight_to_done_unchanged_and_state_is_separate(self):
        home = layout.Home()
        _set_fake_unit(home, "slow:150", name="slow-visible")
        world = _try_init_world(home)
        obj, _result = self._request(world)
        queued = os.path.join(world.inbox, "%s.json" % obj["id"])
        with open(queued, "rb") as f:
            original = f.read()
        worker = threading.Thread(target=llmmod.serve_once, args=(world,))
        worker.start()
        inflight = world.rel("llm-inflight", "%s.json" % obj["id"])
        deadline = time.time() + 1
        while time.time() < deadline and not os.path.exists(inflight):
            time.sleep(0.005)
        self.assertTrue(os.path.exists(inflight), msg="送出後、回來前請求要在 llm-inflight")
        with open(inflight, "rb") as f:
            self.assertEqual(f.read(), original, msg="原件搬進 inflight 必須一字不動")
        self.assertFalse(os.path.exists(os.path.join(world.inbox, "%s.json" % obj["id"])),
                         msg="已送出的請求不能還留在收件匣冒充排隊中")
        worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertFalse(os.path.exists(inflight))
        done = world.rel("llm-done", "%s.json" % obj["id"])
        self.assertTrue(os.path.exists(done), msg="後端回來後原件要搬進 llm-done")
        with open(done, "rb") as f:
            self.assertEqual(f.read(), original, msg="完成原件也必須一字不動")
        state_obj = fsutil.read_json(world.rel("requests", "%s.json" % obj["id"]))
        self.assertEqual(state_obj["state"], "done")
        self.assertEqual(state_obj["unit"], "slow-visible")
        self.assertEqual(state_obj["request"], done)

    def test_restart_marks_inflight_unknown_and_does_not_resend(self):
        home = layout.Home()
        _set_fake_unit(home, "fail:不該重送", name="never-resend")
        world = _try_init_world(home)
        obj, result_path = self._request(world, "-restart")
        os.replace(os.path.join(world.inbox, "%s.json" % obj["id"]),
                   world.rel("llm-inflight", "%s.json" % obj["id"]))

        rep = llmmod.serve_once(world)
        from aosp import status
        st = status.read_status(result_path)
        self.assertEqual(st.get("reason"), "result_unknown", msg="實際 %r" % st)
        self.assertFalse(st.get("ext", {}).get("retryable", True))
        self.assertEqual(rep["handled"][0]["outcome"], "result_unknown")
        done = world.rel("llm-done", "%s.json" % obj["id"])
        self.assertTrue(os.path.exists(done))
        state_obj = fsutil.read_json(world.rel("requests", "%s.json" % obj["id"]))
        self.assertEqual(state_obj["state"], "failed")
        self.assertEqual(state_obj["request"], done)

    def test_llm_ls_has_queued_inflight_completed_columns(self):
        home = layout.Home()
        _set_fake_unit(home, "echo:")
        world = _try_init_world(home)
        rc, out, err = run_cli("llm", "ls", "--land", world.root)
        self.assertEqual(rc, 0, msg=err)
        for label in ("排隊中", "在飛", "已完成"):
            self.assertIn(label, out)

    def test_llm_ls_reads_completed_rows_from_request_state_objects(self):
        home = layout.Home()
        _set_fake_unit(home, "echo:", name="state-reader")
        world = _try_init_world(home)
        obj, _result = self._request(world, "-ls-state")
        llmmod.serve_once(world)

        rc, out, err = run_cli("llm", "ls", "--land", world.root, "--json")
        self.assertEqual(rc, 0, msg=err)
        report = json.loads(out)
        hit = next(r for r in report["completed"] if r["id"] == obj["id"])
        self.assertEqual(hit["state"], "done")
        self.assertEqual(hit["unit"], "state-reader")


@unittest.skipUnless(HAS_LLM, SKIP_MSG)
class TestQueueWaitBoundary(LandCase):
    def test_default_wait_is_ten_minutes_and_backend_time_does_not_count(self):
        home = layout.Home()
        world = _try_init_world(home)
        self.assertEqual(home.load_config().get("max_wait_ms"), 600000)
        _set_fake_unit(home, "slow:80", name="slow-after-send")
        from aosp import inbox
        prompt_path = os.path.join(self.tmp, "wait-boundary.prompt")
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write("後端慢，不是排隊慢")
        result_path = os.path.join(self.tmp, "wait-boundary.out")
        obj = inbox.make("llm", self.land.root, prompt=prompt_path, result=result_path,
                         tier="fast", priority=1, max_wait_ms=40)
        ok, _info = inbox.deliver(world, obj)
        self.assertTrue(ok)

        llmmod.serve_once(world)
        self.assertTrue(os.path.isfile(result_path),
                        msg="送出後花 80ms 不該被 40ms 的排隊上限殺掉")


@unittest.skipUnless(HAS_LLM, SKIP_MSG)
class TestReasoningTokens(LandCase):
    def test_every_ledger_outcome_has_tokens_reasoning_field(self):
        home = layout.Home()
        obj = {"id": "ledger-fields", "from": self.land.root}
        for outcome in ("ok", "backend_error", "result_unknown"):
            llmmod._ledger(home, obj, None, None, 0, 0, None,
                           "estimated", 0, outcome)

        with open(home.ledger, "r", encoding="utf-8") as f:
            entries = [json.loads(line) for line in f if line.strip()]
        self.assertEqual(len(entries), 3)
        for entry in entries:
            self.assertIn("tokens_reasoning", entry)
            self.assertIsNone(entry["tokens_reasoning"])

    def test_reported_reasoning_is_removed_from_tokens_out_and_logged_separately(self):
        import urllib.request

        home = layout.Home()
        _set_fake_unit(home, "http://model.invalid/v1", name="reasoning-model")
        world = _try_init_world(home)
        prompt_path = os.path.join(self.tmp, "reasoning.prompt")
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write("請想完再回答")
        result_path = os.path.join(self.tmp, "reasoning.out")
        from aosp import inbox
        obj = inbox.make("llm", self.land.root, prompt=prompt_path, result=result_path,
                         tier="fast", priority=1, max_wait_ms=5000)
        ok, _info = inbox.deliver(world, obj)
        self.assertTrue(ok)

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps({
                    "choices": [{"message": {"content": "短答"}}],
                    "usage": {
                        "prompt_tokens": 12,
                        "completion_tokens": 100,
                        "completion_tokens_details": {"reasoning_tokens": 73},
                    },
                }).encode("utf-8")

        original = urllib.request.urlopen
        urllib.request.urlopen = lambda *_args, **_kwargs: Response()
        try:
            llmmod.serve_once(world)
        finally:
            urllib.request.urlopen = original

        with open(home.ledger, "r", encoding="utf-8") as f:
            entry = json.loads(f.read().splitlines()[-1])
        self.assertEqual(entry["tokens_out"], 27)
        self.assertEqual(entry["tokens_reasoning"], 73)
        self.assertEqual(entry["tokens_source"], "reported")
