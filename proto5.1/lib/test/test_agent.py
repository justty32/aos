"""aos-agent：新 inst／exec 入口、waits 門、三格、自癒、寫檔順序與命令列。

工具用真的 sh／Python；模型沿用 test_llm_ask.FakeLLM，在本機假 HTTP 伺服器跑，不打真模型。
既有案例保留，連敗計數的斷言隨新契約調整；每條獨立暫存資料夾。
"""
import contextlib
import io
import json
import os
import subprocess
import time
import unittest
from unittest import mock

from _util import AgentCase, Base, LIB, PY, fmt
from test_llm_ask import FakeLLM

import aos_agent
import aos_agent_info
import aos_exec
import aos_inst
import aos_tool_cpu
import aos_llm_cpu
from aos_agent_info import AgentError

AGENT = os.path.join(os.path.dirname(LIB), "cli", "aos-agent")
HISTORY = "prompts/history.json"


def call(name="echo", arguments="{}", id="c1"):
    """一個工具呼叫，arguments 保留原型別供測試。"""
    return {"id": id, "type": "function", "function": {"name": name, "arguments": arguments}}


def assistant(*calls):
    return {"role": "assistant", "content": None, "tool_calls": list(calls)}


def tool(name="echo", **meta):
    return {"type": "function", "function": {"name": name},
            "_meta": dict({"argv": ["sh", "-c", "cat"]}, **meta)}


class StepCase(AgentCase):
    """寫原始 state 與 JSON、走一格、讀結果；不改既有 AgentCase 的 load/bad 語意。"""

    def setUp(self):
        super().setUp()
        self.agent()

    def put(self, path, obj):
        return self.write(path, json.dumps(obj, ensure_ascii=False))

    def state(self, **kw):
        return self.put("state.json", kw)

    def get(self, path="state.json"):
        return json.loads(self.read(path))

    def step(self, **kw):
        return aos_agent.step(self.d, **kw)

    def cli(self, *args, cwd=None, env=None):
        return subprocess.run([AGENT, *args], capture_output=True, text=True,
                              cwd=cwd, env=env, timeout=15)

    def snapshot(self):
        """連原始 bytes 一起比，讀驗失败不能改排版、建 tmp 或 rename。"""
        out = {}
        for root, dirs, files in os.walk(self.d):
            for name in files:
                path = os.path.join(root, name)
                with open(path, "rb") as f:
                    out[os.path.relpath(path, self.d)] = f.read()
        return out

    def rejected(self, code, **kw):
        before = self.snapshot()
        with self.assertRaises(AgentError) as cm:
            self.step(**kw)
        self.assertEqual(cm.exception.code, code, str(cm.exception))
        self.assertEqual(self.snapshot(), before)
        return str(cm.exception)


# ---------------------------------------------------------------- 新的 inst／exec 入口 ----

class TestLoadObj(Base):

    def test_same_as_file(self):
        obj = {"argv": ["sh", {"$env": "ARG"}], "cwd": "sub", "envs": {"A": "中"},
               "stderr": {"$opt": ["mkdir", "append"], "$val": "logs/err"}, "exit": "code"}
        self.assertEqual(aos_inst.load_obj(obj, self.d, env={"ARG": "-c"}),
                         aos_inst.load(self.inst(obj), self.d, env={"ARG": "-c"}))

    def test_memory_self_reference_and_physical_position(self):
        obj = {"argv": ["echo", {"$ref": "#../../text"}], "text": "記憶體"}
        self.assertEqual(aos_inst.load_obj(obj, self.d)["argv"], ["echo", "記憶體"])
        self.assertEqual(obj["argv"][1], {"$ref": "#../../text"})

    def test_memory_reference_cycle(self):
        with self.assertRaises(aos_inst.InstError) as cm:
            aos_inst.load_obj({"argv": [{"$ref": "#."}]}, self.d)
        self.assertEqual(cm.exception.code, "ReferenceCycle")

    def test_external_reference_center_is_cwd(self):
        self.write("sub/args.json", '["echo", "ok"]')
        inst = aos_inst.load_obj({"cwd": "sub", "argv": {"$ref": "args.json"}}, self.d)
        self.assertEqual(inst["argv"], ["echo", "ok"])

    def test_error_codes(self):
        for obj, code in (({}, "EmptyArgv"), ([], "NotAnObject"),
                          ({"argv": ["echo", {"$env": "NO"}]}, "EnvironmentVariableMissing"),
                          ({"argv": [1]}, "FieldTypeMismatch")):
            with self.subTest(code=code), self.assertRaises(aos_inst.InstError) as cm:
                aos_inst.load_obj(obj, self.d, env={})
            self.assertEqual(cm.exception.code, code)


class TestRunInst(Base):

    def run_inst(self, argv=None, text="", timeout_ms=0, **kw):
        inst = aos_inst.load_obj(dict({"argv": argv or ["sh", "-c", "cat"]}, **kw), self.d)
        self.errors = io.StringIO()
        with contextlib.redirect_stderr(self.errors):
            return aos_exec.run_inst(inst, text, timeout_ms=timeout_ms)

    def test_utf8_stdin_stdout(self):
        self.assertEqual(self.run_inst(text="第一行\n$字面\n"), (0, "child", "第一行\n$字面\n"))

    def test_large_bidirectional_pipes(self):
        text = "中文\n" * 100000
        self.assertEqual(self.run_inst(text=text, timeout_ms=5000), (0, "child", text))

    def test_non_utf8_stdout_replaced(self):
        self.assertEqual(self.run_inst([PY, "-c", "import os; os.write(1,b'\\xff')"]),
                         (0, "child", "\ufffd"))

    def test_nonzero_exit_keeps_stdout(self):
        self.assertEqual(self.run_inst(["sh", "-c", "printf result; exit 7"], exit="code"),
                         (7, "child", "result"))
        self.assertEqual(self.read("code"), "7\n")

    def test_program_missing_127_writes_exit(self):
        self.assertEqual(self.run_inst(["/no-such-aos-program"], exit="code"), (127, "child", ""))
        self.assertEqual(self.read("code"), "127\n")

    def test_not_executable_126(self):
        path = self.write("plain", "hello")
        self.assertEqual(self.run_inst([path]), (126, "child", ""))

    def test_cwd_missing_is_aos(self):
        self.assertEqual(self.run_inst(cwd="missing", exit=os.path.join(self.d, "code")), (1, "aos", ""))
        self.assertIn("cwd 不是資料夾", self.errors.getvalue())
        self.assertFalse(self.exists("code"))

    def test_cwd_file_is_aos(self):
        self.write("file", "x")
        self.assertEqual(self.run_inst(cwd="file"), (1, "aos", ""))

    def test_mkdir_failure_is_aos(self):
        self.write("file", "x")
        self.assertEqual(self.run_inst(cwd={"$opt": "mkdir", "$val": "file/sub"}), (1, "aos", ""))
        self.assertIn("mkdir", self.errors.getvalue())

    def test_redirect_failure_is_aos(self):
        self.assertEqual(self.run_inst(stderr="missing/err", exit="code"), (1, "aos", ""))
        self.assertFalse(self.exists("code"))

    def test_exit_parent_missing_is_aos(self):
        self.assertEqual(self.run_inst(exit="missing/code"), (1, "aos", ""))

    def test_cwd_env_stderr_exit_options(self):
        kw = {"cwd": {"$opt": "mkdir", "$val": "sub"},
              "envs": {"$opt": "clear", "$val": {"TEXT": "環境"}},
              "stderr": {"$opt": ["mkdir", "append"], "$val": "logs/err"},
              "exit": {"$opt": ["mkdir", "append"], "$val": "logs/code"}}
        for _ in range(2):
            self.assertEqual(self.run_inst(["sh", "-c", 'printf "$TEXT"; printf err >&2'], **kw),
                             (0, "child", "環境"))
        self.assertEqual(self.read("sub/logs/err"), "errerr")
        self.assertEqual(self.read("sub/logs/code"), "0\n0\n")

    def test_stderr_default_and_merge(self):
        argv = ["sh", "-c", "printf out; printf err >&2"]
        self.assertEqual(self.run_inst(argv), (0, "child", "out"))
        self.assertEqual(self.run_inst(argv, stderr={"$opt": "merge"}), (0, "child", "outerr"))

    def test_timeout_term_keeps_output(self):
        self.assertEqual(self.run_inst(["sh", "-c", "printf before; exec sleep 20"], timeout_ms=150),
                         (143, "child", "before"))

    def test_timeout_kill(self):
        self.assertEqual(self.run_inst(["sh", "-c", "trap '' TERM; printf ready; exec sleep 20"], timeout_ms=150),
                         (137, "child", "ready"))

    def test_timeout_kills_group_after_parent_exits(self):
        """父行程先離開，孫行程握著 stdout 且不理 TERM；仍要砍整組，不永遠卡在 communicate。"""
        script = ("import os, signal, time; pid=os.fork(); "
                  "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                  "os._exit(0) if pid else None; time.sleep(1); open('leak','w').write('bad')")
        with mock.patch.object(aos_exec, "GRACE", 0.1):
            start = time.monotonic()
            result = self.run_inst([PY, "-c", script], timeout_ms=150)
        self.assertEqual(result, (0, "child", ""))
        self.assertLess(time.monotonic() - start, 0.9)
        time.sleep(1.1)
        self.assertFalse(self.exists("leak"))


# ---------------------------------------------------------------- 讀驗 state ----

class TestState(StepCase):

    def test_bad_json(self):
        self.write("state.json", "{bad")
        self.rejected("JsonSyntax")

    def test_not_object(self):
        self.put("state.json", [])
        self.rejected("NotAnObject")

    def test_state_must_be_literal(self):
        for state in ("wait", "", 1, None, {"$env": "STATE"}):
            with self.subTest(state=state):
                self.state(state=state)
                self.rejected("StateInvalid", env={"STATE": "idle"})

    def test_top_level_directive_forbidden(self):
        self.put("state.json", {"$ref": "other.json"})
        self.rejected("FieldTypeMismatch")

    def test_input_type(self):
        for inputs in (None, 5, ["ok", False], {}):
            with self.subTest(inputs=inputs):
                self.state(input=inputs)
                self.rejected("FieldTypeMismatch")

    def test_waits_whole_directive_forbidden(self):
        for waits in ({"$ref": "other.json"}, {"$env": "P"}, fmt("p"), None, 1):
            with self.subTest(waits=waits):
                self.state(waits=waits)
                self.rejected("FieldTypeMismatch")

    def test_wait_value_types(self):
        for value in (1, None, [False], {}):
            self.state(waits=[{"$opt": "any", "$val": value}])
            self.rejected("FieldTypeMismatch")

    def test_mtime_since_required_number(self):
        for extra in ({}, {"since": "1"}, {"since": True}, {"since": {"$ref": "n.json"}}):
            self.state(waits=[dict({"$opt": "mtime", "$val": "x"}, **extra)])
            self.rejected("FieldTypeMismatch")

    def test_unknown_option(self):
        self.state(waits=[{"$opt": "later", "$val": "x"}])
        self.rejected("UnknownOption")

    def test_option_conflicts(self):
        for opt in (["any", "all"], ["exists", "mtime"]):
            self.state(waits=[{"$opt": opt, "$val": "x", "since": 1}])
            self.rejected("OptionConflict")

    def test_options_need_value(self):
        for opt in ("exists", "mtime", "consume", "any", "all"):
            self.state(waits=[{"$opt": opt}])
            self.rejected("OptionConflict")

    def test_input_does_not_accept_options(self):
        self.state(input={"$opt": "consume", "$val": "x"})
        self.rejected("UnknownOption")

    def test_nested_val_does_not_accept_options(self):
        self.state(waits=[{"$opt": "consume", "$val": {"$opt": "exists", "$val": "x"}}])
        self.rejected("UnknownOption")

    def test_directive_error_contains_state_filename(self):
        self.state(input={"$env": "NO_SUCH_VAR"})
        self.assertIn("state.json", self.rejected("EnvironmentVariableMissing", env={}))

    def test_reference_cycle(self):
        self.state(input={"$ref": "#."})
        self.rejected("ReferenceCycle")

    def test_validate_all_waits_before_consume(self):
        self.put("ready.json", {})
        self.state(waits=[{"$opt": "consume", "$val": "ready.json"}, {"$opt": "bad", "$val": "x"}])
        self.rejected("UnknownOption")


# ---------------------------------------------------------------- 門 ----

class TestWaits(StepCase):

    def test_missing_file_waits(self):
        self.state(waits=["missing.json"])
        self.assertEqual(self.step(), 101)
        self.assertEqual(self.get(), {"waits": ["missing.json"]})

    def test_exists_opens_and_runs_one_step(self):
        self.put("input.json", "來了")
        self.state(waits=[{"$opt": "exists", "$val": "input.json"}])
        self.assertEqual(self.step(), 0)
        self.assertEqual(self.get(), {"waits": [], "state": "think"})
        self.assertTrue(self.exists("input.json.done"))

    def test_directory_requires_json_files_not_done(self):
        self.put("inbox/a.json.done", "old")
        self.put("inbox/a.txt", "other")
        os.mkdir(os.path.join(self.d, "inbox/fake.json"))
        self.state(waits=["inbox"])
        self.assertEqual(self.step(), 101)
        self.assertEqual(self.get()["waits"], ["inbox"])
        self.put("inbox/a.json", [])
        self.assertEqual(self.step(), 101)
        self.assertEqual(self.get()["waits"], [])

    def test_mtime_strictly_greater(self):
        p = self.put("ready.json", {})
        os.utime(p, (10, 10))
        self.state(waits=[{"$opt": "mtime", "$val": "ready.json", "since": 10}])
        self.assertEqual(self.step(), 101)
        self.assertTrue(self.get()["waits"])
        os.utime(p, (11, 11))
        self.assertEqual(self.step(), 101)
        self.assertEqual(self.get()["waits"], [])

    def test_mtime_directory_any_file_and_consume_all(self):
        for name, mtime in (("old.json", 5), ("new.json", 15)):
            p = self.put("inbox/" + name, {})
            os.utime(p, (mtime, mtime))
        self.state(waits=[{"$opt": ["mtime", "consume"], "$val": "inbox", "since": 10.5}])
        self.assertEqual(self.step(), 101)
        self.assertEqual(self.get()["waits"], [])
        self.assertTrue(self.exists("inbox/old.json.done"))
        self.assertTrue(self.exists("inbox/new.json.done"))

    def test_all_waits_for_every_path(self):
        self.put("a.json", {})
        self.state(waits=[{"$opt": "all", "$val": ["a.json", "b.json"]}])
        self.assertEqual(self.step(), 101)
        self.assertTrue(self.get()["waits"])
        self.put("b.json", {})
        self.assertEqual(self.step(), 101)
        self.assertEqual(self.get()["waits"], [])

    def test_default_array_is_all(self):
        self.put("a.json", {})
        self.state(waits=[{"$opt": "consume", "$val": ["a.json", "b.json"]}])
        self.assertEqual(self.step(), 101)
        self.assertTrue(self.exists("a.json"))
        self.assertFalse(self.exists("a.json.done"))

    def test_any_consumes_only_arrived_paths(self):
        a = self.put("a.json", {})
        b = self.put("b.json", {})
        os.utime(a, (20, 20))
        os.utime(b, (5, 5))
        self.state(waits=[{"$opt": ["any", "mtime", "consume"],
                           "$val": ["a.json", "b.json", "missing.json"], "since": 10}])
        self.assertEqual(self.step(), 101)
        self.assertTrue(self.exists("a.json.done"))
        self.assertTrue(self.exists("b.json"))
        self.assertFalse(self.exists("b.json.done"))
        self.assertEqual(self.get()["waits"], [])

    def test_consume_replaces_old_done(self):
        self.put("ready.json", "新")
        self.put("ready.json.done", "舊")
        self.state(waits={"$opt": "consume", "$val": "ready.json"})
        self.assertEqual(self.step(), 101)
        self.assertEqual(self.get("ready.json.done"), "新")
        self.assertFalse(self.exists("ready.json"))

    def test_partial_preserves_raw_other_fields_and_remaining_indices(self):
        self.put("yes.json", {})
        raw = {"state": "think", "input": {"$env": "INPUT"}, "extra": {"$unused": "kept"},
               "waits": ["missing.json", {"$opt": "consume", "$val": "yes.json"}, "last.json"]}
        self.put("state.json", raw)
        self.assertEqual(self.step(env={"INPUT": "in.json"}), 101)
        raw["waits"] = ["missing.json", "last.json"]
        self.assertEqual(self.get(), raw)
        self.assertFalse(self.exists(HISTORY))

    def test_single_literal_path(self):
        self.put("ready", "hi")
        self.state(waits="ready")
        self.assertEqual(self.step(), 101)
        self.assertEqual(self.get(), {"waits": []})

    def test_each_entry_resolves_fmt_and_ref_at_agent_base(self):
        self.put("cfg/wait.json", {"$opt": "exists", "$val": {"$ref": "paths.json#/p"}})
        self.put("paths.json", {"p": "ready.json"})
        self.put("ready.json", {})
        self.state(waits=[fmt("${p}.json", p={"$env": "NAME"}), {"$ref": "cfg/wait.json"}])
        self.assertEqual(self.step(env={"NAME": "ready"}), 101)
        self.assertEqual(self.get()["waits"], [])

    def test_val_ref_container_keeps_document_and_physical_positions(self):
        self.put("cfg.json", {"paths": [{"$ref": "#../../p"}], "p": "ready.json"})
        self.put("ready.json", {})
        self.state(waits=[{"$opt": "all", "$val": {"$ref": "cfg.json#/paths"}}])
        self.assertEqual(self.step(), 101)
        self.assertEqual(self.get()["waits"], [])

    def test_single_option_val_relative_position(self):
        self.put("ready.json", {})
        self.state(waits={"$opt": "exists", "$val": {"$ref": "#../p"}, "p": "ready.json"})
        self.assertEqual(self.step(), 101)
        self.assertEqual(self.get()["waits"], [])

    def test_shared_wait_input_without_consume(self):
        self.put("input.json", "hi")
        self.state(waits=["input.json"])
        self.assertEqual(self.step(), 0)
        self.assertEqual(self.get(HISTORY), [{"role": "user", "content": "hi"}])

    def test_shared_wait_input_with_consume(self):
        self.put("input.json", "hi")
        self.state(waits=[{"$opt": "consume", "$val": "input.json"}])
        self.assertEqual(self.step(), 101)
        self.assertFalse(self.exists(HISTORY))
        self.assertTrue(self.exists("input.json.done"))

    def test_repeated_wait_observes_prior_consume(self):
        self.put("ready.json", {})
        self.state(waits=[{"$opt": "consume", "$val": "ready.json"}, "ready.json"])
        self.assertEqual(self.step(), 101)
        self.assertEqual(self.get()["waits"], ["ready.json"])

    def test_empty_all_arrives_empty_any_waits(self):
        self.state(waits=[{"$opt": "all", "$val": []}, {"$opt": "any", "$val": []}])
        self.assertEqual(self.step(), 101)
        self.assertEqual(self.get()["waits"], [{"$opt": "any", "$val": []}])


# ---------------------------------------------------------------- idle ----

class TestIdle(StepCase):

    def test_missing_input_does_not_write(self):
        before = self.snapshot()
        self.assertEqual(self.step(), 101)
        self.assertEqual(self.snapshot(), before)

    def test_empty_array_does_not_write_or_consume(self):
        self.put("input.json", [])
        before = self.snapshot()
        self.assertEqual(self.step(), 101)
        self.assertEqual(self.snapshot(), before)

    def test_string_and_first_state_creation(self):
        self.put("input.json", "中文 ${x}")
        self.assertEqual(self.step(), 0)
        self.assertEqual(self.get(), {"state": "think"})
        self.assertEqual(self.get(HISTORY), [{"role": "user", "content": "中文 ${x}"}])
        self.assertTrue(self.read(HISTORY).endswith("\n"))
        self.assertIn("中文", self.read(HISTORY))
        self.assertFalse(self.exists("input.json"))
        self.assertTrue(self.exists("input.json.done"))

    def test_single_message_preserved(self):
        msg = {"role": "tool", "tool_call_id": "c", "content": "result", "$extra": {"$env": "NO"}}
        self.put("input.json", msg)
        self.assertEqual(self.step(env={}), 0)
        self.assertEqual(self.get(HISTORY), [msg])

    def test_message_array_appends_to_history(self):
        old = [{"role": "user", "content": "old"}]
        msgs = [{"role": "user", "content": "new"}, {"role": "assistant", "content": "ok"}]
        self.agent(history=old)
        self.put("input.json", msgs)
        self.assertEqual(self.step(), 0)
        self.assertEqual(self.get(HISTORY), old + msgs)

    def test_input_paths_order_and_directory_sort(self):
        self.state(input=["inbox", "last.json"])
        self.put("inbox/z.json", "z")
        self.put("inbox/a.json", "a")
        self.put("inbox/skip.json.done", "skip")
        self.put("last.json", "last")
        self.assertEqual(self.step(), 0)
        self.assertEqual([m["content"] for m in self.get(HISTORY)], ["a", "z", "last"])
        self.assertTrue(self.exists("inbox/skip.json.done"))

    def test_input_directives_and_raw_preservation(self):
        self.put("paths.json", {"paths": [{"$ref": "#../../p"}], "p": "in.json"})
        raw = {"input": {"$ref": "paths.json#/paths"}, "note": {"$env": "ignored"}}
        self.put("state.json", raw)
        self.put("in.json", "hi")
        self.assertEqual(self.step(), 0)
        self.assertEqual(self.get(), dict(raw, state="think"))

    def test_bad_message_does_not_write(self):
        for msg in (42, None, {"role": "system", "content": "bad"}, ["bad"],
                    {"role": "tool", "content": "missing id"}):
            self.put("input.json", msg)
            self.rejected("MessageInvalid")

    def test_later_bad_file_does_not_consume_earlier(self):
        self.state(input=["first.json", "bad.json"], waits=["ready.json"])
        self.put("ready.json", {})
        self.put("first.json", "good")
        self.put("bad.json", {"role": "other"})
        self.rejected("MessageInvalid")

    def test_bad_input_does_not_consume_open_gate(self):
        self.state(waits=[{"$opt": "consume", "$val": "ready.json"}])
        self.put("ready.json", {})
        self.put("input.json", False)
        self.rejected("MessageInvalid")

    def test_input_bad_json(self):
        self.write("input.json", "{broken")
        self.rejected("JsonSyntax")

    def test_empty_file_also_consumed_if_other_input_exists(self):
        self.state(input=["empty.json", "input.json"])
        self.put("empty.json", [])
        self.put("input.json", "hi")
        self.assertEqual(self.step(), 0)
        self.assertTrue(self.exists("empty.json.done"))

    def test_repeated_input_path_consumed_once(self):
        self.state(input=["input.json", "input.json"])
        self.put("input.json", "hi")
        self.assertEqual(self.step(), 0)
        self.assertEqual(len(self.get(HISTORY)), 1)


# ---------------------------------------------------------------- think（真的 HTTP、假的模型）----

class TestThink(StepCase):

    def setUp(self):
        super().setUp()
        self.llm = FakeLLM()
        self.addCleanup(self.llm.close)
        self.agent(info={"engine": {"cpu": "cpu", "model": "fake"}},
                   system={"content": "人格"}, history=[{"role": "user", "content": "hi"}])
        self.put("cpu/info.json", {"_metainfo": {"_type": "llm_cpu", "_version": 1},
                                    "models": {"fake": {"endpoint": self.llm.endpoint, "model": "real-fake"}}})
        self.state(state="think")

    def think_round(self, **kw):
        result = self.step(**kw)
        if result == 0 and self.get().get("waits") == ["ask-result.json"]:
            self.assertEqual(aos_llm_cpu.tick(os.path.join(self.d, "cpu")), 0)
            return self.step(**kw)
        return result

    def test_reply_goes_idle(self):
        self.assertEqual(self.think_round(), 0)
        self.assertEqual(self.get()["state"], "idle")
        self.assertEqual(self.get(HISTORY)[-1], self.llm.message)
        self.assertEqual(self.llm.last["body"]["messages"],
                         [{"role": "system", "content": "人格"}, {"role": "user", "content": "hi"}])

    def test_tool_calls_go_act_verbatim(self):
        self.llm.message = dict(assistant(call()), reasoning_content="想一下", extra={"$x": 1})
        self.assertEqual(self.think_round(), 0)
        self.assertEqual(self.get()["state"], "act")
        self.assertEqual(self.get(HISTORY)[-1], self.llm.message)

    def test_null_content_without_calls_becomes_empty(self):
        self.llm.message = {"role": "assistant", "content": None}
        self.assertEqual(self.think_round(), 0)
        self.assertEqual(self.get(HISTORY)[-1]["content"], "")
        aos_agent_info.load(self.d)                 # 下一次確實讀得回來

    def test_empty_tool_calls_go_idle(self):
        self.llm.message = assistant()
        self.assertEqual(self.think_round(), 0)
        self.assertEqual(self.get()["state"], "idle")
        aos_agent_info.load(self.d)

    def test_http_500_preserves_history_and_counts_failure(self):
        self.llm.mode = "500"
        self.engine_failure("500")

    def test_disconnect_preserves_history_and_counts_failure(self):
        self.llm.mode = "truncated"
        self.engine_failure("engine:")

    def engine_failure(self, hint):
        before = self.read(HISTORY)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(self.think_round(), 0)
        self.assertEqual(self.get(), {"state": "think", "errors": 1, "waits": []})
        self.assertEqual(self.read(HISTORY), before)
        self.assertTrue(err.getvalue().startswith("aos-agent: engine: "))
        self.assertIn(hint, err.getvalue())
        self.assertEqual(len(err.getvalue().splitlines()), 1)

    def test_self_heal_does_not_call_model_or_write_history(self):
        self.put(HISTORY, [assistant(call())])
        before = self.read(HISTORY)
        self.assertEqual(self.think_round(), 0)
        self.assertEqual(self.get()["state"], "act")
        self.assertEqual(self.read(HISTORY), before)
        self.assertEqual(self.llm.requests, [])

    def test_waits_block_model(self):
        self.state(state="think", waits=["missing.json"])
        self.assertEqual(self.think_round(), 101)
        self.assertEqual(self.llm.requests, [])

    def test_gate_progress_survives_engine_failure(self):
        self.put("ready.json", {})
        self.state(state="think", waits=["ready.json"])
        self.llm.mode = "500"
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.think_round(), 0)
        self.assertEqual(self.get(), {"state": "think", "waits": [], "errors": 1})

    def test_three_failures_pause_touch_resumes_and_can_pause_again(self):
        self.llm.mode = "500"
        with contextlib.redirect_stderr(io.StringIO()) as err:
            for count in (1, 2, 0):
                self.assertEqual(self.think_round(), 0)
                self.assertEqual(self.get()["errors"], count)
            self.assertEqual(self.get()["waits"], [{"$opt": "consume", "$val": "continue.json"}])
            self.assertEqual(self.think_round(), 101)
            self.assertEqual(len(self.llm.requests), 3)
            self.write("continue.json", "")
            for count in (1, 2, 0):
                self.assertEqual(self.think_round(), 0)
                self.assertEqual(self.get()["errors"], count)
            self.assertEqual(self.think_round(), 101)
        self.assertEqual(err.getvalue().count("aos-agent: stuck:"), 2)
        self.assertFalse(self.exists("continue.json"))
        self.assertTrue(self.exists("continue.json.done"))
        self.assertEqual(len(self.llm.requests), 6)

    def test_success_resets_consecutive_errors(self):
        self.state(state="think", errors=2, note={"$env": "untouched"})
        self.assertEqual(self.think_round(), 0)
        self.assertEqual(self.get(), {"state": "idle", "errors": 0, "waits": [], "note": {"$env": "untouched"}})

    def test_invalid_error_counter_does_not_consume_gate(self):
        self.put("ready.json", {})
        for value in (True, -1, 1.5, "1", None, {"$env": "COUNT"}):
            with self.subTest(value=value):
                self.state(state="think", errors=value,
                           waits=[{"$opt": "consume", "$val": "ready.json"}])
                self.rejected("FieldTypeMismatch")


# ---------------------------------------------------------------- think 丟給 cpu ----

class TestThinkCpu(StepCase):

    def setUp(self):
        super().setUp()
        self.agent(info={"engine": {"model": "fake", "cpu": "cpu"}},
                   history=[{"role": "user", "content": "hi"}])
        self.put("cpu/info.json", {"_metainfo": {"_type": "llm_cpu", "_version": 1},
                                    "models": {"fake": {"endpoint": "http://unused.invalid/v1", "model": "real-fake"}}})
        self.state(state="think")

    def requests(self):
        folder = os.path.join(self.d, "cpu", "requests")
        return sorted(n for n in os.listdir(folder) if n.endswith(".json"))

    def result(self, message=None, error=None):
        if error is None:
            return self.put("ask-result.json", {"ok": True, "message": message or
                                                {"role": "assistant", "content": "answer"}})
        return self.put("ask-result.json", {"ok": False, "code": "EngineFailed", "msg": error})

    def test_send_body_engine_absolute_result_and_wait(self):
        with mock.patch.object(aos_agent.aos_llm_ask, "call", side_effect=AssertionError("不能同步問")):
            self.assertEqual(self.step(), 0)
            self.assertEqual(self.step(), 101)
        names = self.requests()
        self.assertEqual(len(names), 1)
        self.assertRegex(names[0], r"^" + os.path.basename(self.d) + r"-\d+\.json$")
        request = self.get("cpu/requests/" + names[0])
        self.assertEqual(request["result"], os.path.join(self.d, "ask-result.json"))
        self.assertEqual(set(request), {"model", "body", "result"})
        self.assertEqual(request["model"], "fake")
        self.assertNotIn("model", request["body"])
        self.assertNotIn("cpu", request["body"])
        self.assertEqual(request["body"]["messages"], [{"role": "user", "content": "hi"}])
        self.assertEqual(self.get(), {"state": "think", "waits": ["ask-result.json"]})

    def test_model_credentials_resolve_only_in_cpu_environment(self):
        fake = FakeLLM()
        self.addCleanup(fake.close)
        self.put("cpu/info.json", {"_metainfo": {"_type": "llm_cpu", "_version": 1},
                 "models": {"fake": {"endpoint": fake.endpoint, "model": "real-fake",
                                     "api_key": {"$env": "CPU_KEY"}}}})
        self.assertEqual(self.step(env={}), 0)
        request = self.get("cpu/requests/" + self.requests()[0])
        self.assertNotIn("CPU_KEY", json.dumps(request))
        self.assertEqual(aos_llm_cpu.tick(os.path.join(self.d, "cpu"), env={"CPU_KEY": "secret"}), 0)
        self.assertEqual(fake.last["headers"]["Authorization"], "Bearer secret")
        self.assertEqual(fake.last["body"]["model"], "real-fake")
        self.assertEqual(self.step(env={}), 0)
        self.assertEqual(self.get()["state"], "idle")

    def test_success_goes_idle_and_result_is_done(self):
        self.state(state="think", waits=["ask-result.json"], errors=2)
        self.result()
        self.assertEqual(self.step(), 0)
        self.assertEqual(self.get(), {"state": "idle", "waits": [], "errors": 0})
        self.assertEqual(self.get(HISTORY)[-1], {"role": "assistant", "content": "answer"})
        self.assertFalse(self.exists("ask-result.json"))
        self.assertTrue(self.exists("ask-result.json.done"))
        self.assertEqual(self.step(), 101)

    def test_success_tool_calls_go_act_verbatim(self):
        message = dict(assistant(call()), reasoning_content="不要解 ${x}")
        self.result(message)
        self.assertEqual(self.step(), 0)
        self.assertEqual(self.get()["state"], "act")
        self.assertEqual(self.get(HISTORY)[-1], message)

    def test_null_content_is_normalized(self):
        self.result({"role": "assistant", "content": None})
        self.assertEqual(self.step(), 0)
        self.assertEqual(self.get(HISTORY)[-1]["content"], "")
        aos_agent_info.load(self.d)

    def test_failure_consumed_keeps_history_and_think_then_resubmits(self):
        self.state(state="think", waits=["ask-result.json"])
        self.result(error="引擎\n斷線")
        before = self.read(HISTORY)
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(self.step(), 0)
        self.assertEqual(err.getvalue(), "aos-agent: engine: 引擎 斷線\n")
        self.assertEqual(self.read(HISTORY), before)
        self.assertEqual(self.get(), {"state": "think", "waits": [], "errors": 1})
        self.assertTrue(self.exists("ask-result.json.done"))
        self.assertFalse(self.exists("ask-result.json"))
        self.assertEqual(self.step(), 0)
        self.assertEqual(len(self.requests()), 1)

    def test_third_async_failure_pauses_and_touch_submits_again(self):
        self.state(state="think", waits=["ask-result.json"], errors=2)
        self.result(error="故障")
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(self.step(), 0)
        self.assertIn("stuck: 引擎連敗 3 次", err.getvalue())
        self.assertEqual(self.get(), {"state": "think", "waits": [{"$opt": "consume", "$val": "continue.json"}], "errors": 0})
        self.assertEqual(self.step(), 101)
        self.write("continue.json", "")
        self.assertEqual(self.step(), 0)
        self.assertEqual(self.get()["waits"], ["ask-result.json"])
        self.assertEqual(len(self.requests()), 1)

    def test_continue_is_not_consumed_until_gate_opens(self):
        self.state(state="think", errors=2)
        self.write("continue.json", "")
        self.result(error="故障")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.step(), 0)
        self.assertTrue(self.exists("continue.json"))
        self.assertFalse(self.exists("continue.json.done"))
        self.assertEqual(self.step(), 0)
        self.assertFalse(self.exists("continue.json"))
        self.assertTrue(self.exists("continue.json.done"))
        self.assertEqual(self.get()["waits"], ["ask-result.json"])

    def test_self_heal_precedes_submission(self):
        self.put(HISTORY, [assistant(call())])
        before = self.read(HISTORY)
        self.assertEqual(self.step(), 0)
        self.assertEqual(self.get()["state"], "act")
        self.assertEqual(self.read(HISTORY), before)
        self.assertFalse(self.exists("cpu/requests"))

    def test_bad_result_does_not_change_gate_history_or_result(self):
        self.put("ready.json", {})
        cases = [(None, "NotAnObject"), ({"ok": 1}, "FieldTypeMismatch"),
                 ({"ok": False}, "FieldTypeMismatch"),
                 ({"ok": False, "error": 3}, "FieldTypeMismatch"),
                 ({"ok": True}, "MessageInvalid"),
                 ({"ok": True, "message": {"role": "user", "content": "wrong"}}, "MessageInvalid"),
                 ({"ok": True, "message": {"role": "assistant", "content": 4}}, "MessageInvalid"),
                 ({"ok": True, "message": {"role": "assistant", "content": "x",
                                           "tool_calls": {}}}, "MessageInvalid")]
        for result, code in cases:
            with self.subTest(result=result):
                self.state(state="think", waits=[{"$opt": "consume", "$val": "ready.json"},
                                                  "ask-result.json"])
                self.put("ask-result.json", result)
                self.rejected(code)

    def test_malformed_json_cli_returns_one_and_keeps_files(self):
        self.state(state="think", waits=["ask-result.json"])
        self.write("ask-result.json", "{broken")
        before = self.snapshot()
        process = self.cli(self.d)
        self.assertEqual(process.returncode, 1)
        self.assertIn("JsonSyntax", process.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_non_utf8_result_cli_is_one_line_error_and_keeps_files(self):
        self.state(state="think", waits=["ask-result.json"])
        with open(os.path.join(self.d, "ask-result.json"), "wb") as f:
            f.write(b"\xff")
        before = self.snapshot()
        process = self.cli(self.d)
        self.assertEqual(process.returncode, 1)
        self.assertIn("JsonSyntax", process.stderr)
        self.assertEqual(len(process.stderr.splitlines()), 1)
        self.assertEqual(self.snapshot(), before)

    def test_other_wait_still_blocks_valid_result(self):
        self.state(state="think", waits=["ask-result.json", "missing.json"])
        self.result()
        before = self.read(HISTORY)
        self.assertEqual(self.step(), 101)
        self.assertEqual(self.get()["waits"], ["missing.json"])
        self.assertTrue(self.exists("ask-result.json"))
        self.assertEqual(self.read(HISTORY), before)

    def test_closed_gate_defers_reading_bad_result(self):
        self.state(state="think", waits=["pause.json"])
        self.write("ask-result.json", "{bad")
        self.assertEqual(self.step(), 101)
        self.assertTrue(self.exists("ask-result.json"))
        self.put("pause.json", {})
        self.rejected("JsonSyntax")

    def test_bad_cpu_info_does_not_consume_gate(self):
        self.put("ready.json", {})
        self.state(state="think", waits=[{"$opt": "consume", "$val": "ready.json"}])
        self.write("cpu/info.json", "{bad")
        self.rejected("JsonSyntax")

    def test_duplicate_name_in_each_stage_is_not_overwritten(self):
        name = os.path.basename(self.d) + "-123.json"
        for stage in ("requests", "running", "done"):
            with self.subTest(stage=stage):
                path = "cpu/" + stage + "/" + name
                self.put(path, {"existing": stage})
                with mock.patch.object(aos_agent.time, "time_ns", return_value=123):
                    with self.assertRaises(AgentError) as cm:
                        self.step()
                self.assertEqual(cm.exception.code, "ReadFailed")
                self.assertEqual(self.get(path), {"existing": stage})
                self.assertEqual(self.get(), {"state": "think"})
                os.rename(os.path.join(self.d, path), os.path.join(self.d, path + ".saved"))

    def test_submit_then_waits_write_failure_leaves_queued_request(self):
        real_replace = os.replace

        def replace(src, dst):
            if dst == os.path.join(self.d, "state.json"):
                raise PermissionError("模擬請求送出後 state 寫失敗")
            real_replace(src, dst)

        with mock.patch.object(aos_agent.os, "replace", side_effect=replace):
            with self.assertRaises(PermissionError):
                self.step()
        self.assertEqual(len(self.requests()), 1)
        self.assertEqual(self.get(), {"state": "think"})

    def test_receipt_write_order_history_done_state(self):
        self.result()
        real_replace = os.replace
        destinations = []

        def replace(src, dst):
            destinations.append(os.path.relpath(dst, self.d))
            real_replace(src, dst)

        with mock.patch.object(aos_agent.os, "replace", side_effect=replace):
            self.assertEqual(self.step(), 0)
        self.assertEqual(destinations, [HISTORY, "ask-result.json.done", "state.json"])

    def test_failed_result_rename_leaves_history_ahead_and_result_unconsumed(self):
        message = assistant(call())
        self.result(message)
        real_replace = os.replace

        def replace(src, dst):
            if src == os.path.join(self.d, "ask-result.json"):
                raise PermissionError("模擬記憶寫好後結果 rename 失敗")
            real_replace(src, dst)

        with mock.patch.object(aos_agent.os, "replace", side_effect=replace):
            with self.assertRaises(PermissionError):
                self.step()
        self.assertEqual(self.get()["state"], "think")
        self.assertEqual(self.get(HISTORY)[-1], message)
        self.assertTrue(self.exists("ask-result.json"))
        # 帶工具的尾訊息與結果完全相同，足以判斷此結果已接進記憶。
        self.assertEqual(self.step(), 0)
        self.assertEqual(self.get()["state"], "act")
        self.assertFalse(self.exists("ask-result.json"))
        self.assertTrue(self.exists("ask-result.json.done"))
        self.assertEqual(self.get()["errors"], 0)
        self.assertEqual(self.step(), 0)  # 跑工具，回 think。
        self.assertEqual(self.step(), 0)  # 送新單，不再收舊 assistant。
        self.assertEqual(len(self.requests()), 1)

    def test_bad_result_does_not_block_tool_call_self_healing(self):
        self.put(HISTORY, [assistant(call())])
        self.write("ask-result.json", "{broken")
        self.assertEqual(self.step(), 0)
        self.assertEqual(self.get()["state"], "act")
        self.assertTrue(self.exists("ask-result.json"))


# ---------------------------------------------------------------- act ----

class TestAct(StepCase):

    def setup_act(self, calls, tools=None):
        self.agent(history=[assistant(*calls)], tools={"tools.json": tools or [tool()]})
        self.state(state="act")

    def test_shell_echo_and_tool_call_id(self):
        self.setup_act([call(arguments=' {"x": "中文"} \n')])
        self.assertEqual(self.step(), 0)
        self.assertEqual(self.get(HISTORY)[-1],
                         {"role": "tool", "tool_call_id": "c1", "content": ' {"x": "中文"} \n'})
        self.assertEqual(self.get()["state"], "think")

    def test_multiple_calls_in_order(self):
        self.setup_act([call(arguments="first", id="a"), call(arguments="second", id="b")])
        self.assertEqual(self.step(), 0)
        self.assertEqual([(m["tool_call_id"], m["content"]) for m in self.get(HISTORY)[1:]],
                         [("a", "first"), ("b", "second")])

    def test_arguments_non_string_are_json(self):
        self.setup_act([call(arguments={"中文": [1, True]})])
        self.assertEqual(self.step(), 0)
        self.assertEqual(self.get(HISTORY)[-1]["content"], json.dumps({"中文": [1, True]}))

    def test_missing_id_defaults_empty(self):
        c = call()
        del c["id"]
        self.setup_act([c])
        self.assertEqual(self.step(), 0)
        self.assertEqual(self.get(HISTORY)[-1]["tool_call_id"], "")

    def test_unknown_tool(self):
        self.setup_act([call("nope")])
        self.assertEqual(self.step(), 0)
        self.assertEqual(self.get(HISTORY)[-1]["content"], "沒有這個工具：nope")

    def test_nonzero_exit(self):
        self.setup_act([call()], [tool(argv=["sh", "-c", "printf oops; exit 9"])])
        self.assertEqual(self.step(), 0)
        self.assertEqual(self.get(HISTORY)[-1]["content"], "工具 echo 失敗（exit 9）：oops")

    def test_timeout_keeps_stdout_and_runs_next_call(self):
        slow = dict(tool("slow", argv=["sh", "-c", "printf before; exec sleep 20"]), _timeout_ms=150)
        self.setup_act([call("slow", id="a"), call(arguments="after", id="b")], [slow, tool()])
        self.assertEqual(self.step(), 0)
        self.assertEqual([m["content"] for m in self.get(HISTORY)[1:]],
                         ["工具 slow 逾時（150 ms）：before", "after"])
        self.assertEqual(self.get()["state"], "think")

    def test_default_timeout_is_sixty_seconds(self):
        self.setup_act([call(arguments="ok")])
        with mock.patch.object(aos_exec, "run_inst", wraps=aos_exec.run_inst) as run:
            self.assertEqual(self.step(), 0)
        self.assertEqual(run.call_args.kwargs["timeout_ms"], 60000)

    def test_exit_143_is_not_mistaken_for_timeout(self):
        self.setup_act([call()], [tool(argv=["sh", "-c", "printf own; exit 143"])])
        self.assertEqual(self.step(), 0)
        self.assertEqual(self.get(HISTORY)[-1]["content"], "工具 echo 失敗（exit 143）：own")

    def test_missing_program_is_tool_failure(self):
        self.setup_act([call()], [tool(argv=["/no-aos-program"])])
        self.assertEqual(self.step(), 0)
        self.assertEqual(self.get(HISTORY)[-1]["content"], "工具 echo 失敗（exit 127）：")

    def test_bad_meta_is_result_and_next_tool_still_runs(self):
        self.setup_act([call("bad", id="a"), call(arguments="ok", id="b")],
                       [tool("bad", argv=[]), tool()])
        self.assertEqual(self.step(), 0)
        msgs = self.get(HISTORY)
        self.assertTrue(msgs[1]["content"].startswith("工具 bad 跑不起來：EmptyArgv:"))
        self.assertEqual(msgs[2]["content"], "ok")

    def test_cwd_missing_is_result(self):
        self.setup_act([call()], [tool(cwd="missing")])
        self.assertEqual(self.step(), 0)
        msg = self.get(HISTORY)[-1]["content"]
        self.assertTrue(msg.startswith("工具 echo 跑不起來："))
        self.assertIn("cwd 不是資料夾", msg)
        self.assertEqual(len(msg.splitlines()), 1)

    def test_meta_directives_env_and_agent_base(self):
        self.put("args.json", ["sh", "-c", "cat"])
        self.setup_act([call(arguments="ok")], [tool(argv={"$ref": "args.json"}, envs={"X": {"$env": "X"}})])
        self.assertEqual(self.step(env={"X": "outer"}), 0)
        self.assertEqual(self.get(HISTORY)[-1]["content"], "ok")

    def test_meta_memory_self_reference(self):
        self.setup_act([call()], [tool(argv=["echo", {"$ref": "#/text"}], text="memory")])
        self.assertEqual(self.step(), 0)
        self.assertEqual(self.get(HISTORY)[-1]["content"], "memory\n")

    def test_self_heal_without_calls_does_not_repeat_tool(self):
        history = [assistant(call()), {"role": "tool", "tool_call_id": "c1", "content": "done"}]
        self.agent(history=history, tools={"tools.json": [tool(argv=["sh", "-c", "touch BAD"])]})
        self.state(state="act")
        before = self.read(HISTORY)
        self.assertEqual(self.step(), 0)
        self.assertEqual(self.get()["state"], "think")
        self.assertEqual(self.read(HISTORY), before)
        self.assertFalse(self.exists("BAD"))

    def test_empty_history_self_heals(self):
        self.state(state="act")
        self.assertEqual(self.step(), 0)
        self.assertEqual(self.get()["state"], "think")
        self.assertFalse(self.exists(HISTORY))

    def test_malformed_call_does_not_crash(self):
        self.setup_act([None, {"id": 2, "function": []}])
        self.assertEqual(self.step(), 0)
        self.assertEqual(len(self.get(HISTORY)), 3)
        aos_agent_info.load(self.d)


# ---------------------------------------------------------------- 寫檔順序與命令列 ----

class TestCpuAct(StepCase):

    def setup_cpu(self, calls=None, tools=None):
        self.agent(info={"tool_cpu": "T"}, history=[assistant(*(calls or [call()]))],
                   tools={"tools.json": tools or [dict(tool(), _run="cpu")]})
        self.put("T/info.json", {"_metainfo": {"_type": "tool_cpu", "_version": 1}})
        self.state(state="act")

    def tick(self):
        return aos_tool_cpu.tick(os.path.join(self.d, "T"))

    def results(self, i=0, **changes):
        result = dict(ok=True, code=0, kind="child", timed_out=False, stdout="done")
        result.update(changes)
        self.put("tool-results/%d.json" % i, result)

    def test_submit_wait_collect_real_tool(self):
        self.setup_cpu([call(arguments=' {"中文": 1} \n')])
        self.assertEqual(self.step(), 0)
        self.assertEqual(self.get(), {"state": "act", "waits": [{"$opt": "all", "$val": [
            os.path.join(self.d, "tool-results/0.json")]}]})
        self.assertEqual(len(self.get(HISTORY)), 1)
        self.assertEqual(self.step(), 101)
        request_names = os.listdir(os.path.join(self.d, "T/requests"))
        request = self.get("T/requests/" + request_names[0])
        self.assertEqual(request["inst"]["cwd"], self.d)
        self.assertNotIn("stdin", request["inst"])
        self.assertNotIn("stdout", request["inst"])
        self.assertEqual(request["timeout_ms"], 60000)
        self.assertEqual(request["stdin"], ' {"中文": 1} \n')
        self.assertEqual(self.tick(), 0)
        self.assertEqual(self.step(), 0)
        self.assertEqual(self.get(HISTORY)[-1]["content"], ' {"中文": 1} \n')
        self.assertEqual(self.get(), {"state": "think", "waits": []})
        self.assertTrue(self.exists("tool-results/0.json.done"))

    def test_mixed_all_submitted_before_sync_and_keeps_original_order(self):
        sync = tool("sync", argv=["sh", "-c", "touch SYNC; printf sync"])
        cpu = dict(tool("cpu"), _run="cpu")
        self.setup_cpu([call("sync", id="a"), call("cpu", "first", "b"),
                        call("cpu", "second", "c")], [sync, cpu])
        self.assertEqual(self.step(), 0)
        self.assertFalse(self.exists("SYNC"))
        self.assertEqual(len(os.listdir(os.path.join(self.d, "T/requests"))), 2)
        self.assertEqual(self.tick(), 0)
        self.assertEqual(self.step(), 101)
        self.assertFalse(self.exists("SYNC"))
        self.assertEqual(self.tick(), 0)
        self.assertEqual(self.step(), 0)
        self.assertTrue(self.exists("SYNC"))
        self.assertEqual([(m["tool_call_id"], m["content"]) for m in self.get(HISTORY)[1:]],
                         [("a", "sync"), ("b", "first"), ("c", "second")])
        self.assertFalse(self.exists("tool-results/0.json.done"))

    def test_cpu_result_text_contract(self):
        cases = [(dict(code=9, stdout="oops"), "工具 echo 失敗（exit 9）：oops"),
                 (dict(code=0, timed_out=True, stdout="partial"), "工具 echo 逾時"),
                 (dict(ok=False, code="EngineFailed", msg="broken"), "工具 echo 跑不起來：broken"),
                 (dict(ok=False, code="Reaped", msg="不同的收屍說明"),
                  '{"ok": false, "error": "結果不明：工具可能已經跑了，也可能沒有"}'),
                 (dict(ok=False, code="EngineFailed", msg="結果不明：工具可能已經跑了，也可能沒有"),
                  "工具 echo 跑不起來：結果不明：工具可能已經跑了，也可能沒有"),
                 (dict(code=143, stdout="own"), "工具 echo 失敗（exit 143）：own"),
                 (dict(code=1, kind="aos", stdout=""), "工具 echo 失敗（exit 1）：")]
        for result, expected in cases:
            with self.subTest(result=result):
                self.setup_cpu()
                self.results(**result)
                self.assertEqual(self.step(), 0)
                self.assertEqual(self.get(HISTORY)[-1]["content"], expected)

    def test_reaped_tool_is_exact_unknown_json_and_not_retried(self):
        self.setup_cpu()
        self.assertEqual(self.step(), 0)
        request_dir = os.path.join(self.d, "T", "requests")
        name = next(n for n in os.listdir(request_dir) if n.endswith(".json"))
        running = os.path.join(self.d, "T", "running", name)
        os.rename(os.path.join(request_dir, name), running)
        os.utime(running, (1, 1))
        self.assertEqual(self.tick(), 0)
        self.assertEqual(self.step(), 0)
        self.assertEqual(self.get(HISTORY)[-1]["content"],
                         '{"ok": false, "error": "結果不明：工具可能已經跑了，也可能沒有"}')
        self.assertEqual(self.get()["state"], "think")
        self.assertEqual(os.listdir(request_dir), [])
        self.assertEqual(self.tick(), 101)

    def test_real_cpu_timeout(self):
        self.setup_cpu(tools=[dict(tool(argv=["sh", "-c", "exec sleep 5"]),
                                   _run="cpu", _timeout_ms=30)])
        self.assertEqual(self.step(), 0)
        self.assertEqual(self.tick(), 0)
        self.assertTrue(self.get("tool-results/0.json")["timed_out"])
        self.assertEqual(self.step(), 0)
        self.assertEqual(self.get(HISTORY)[-1]["content"], "工具 echo 逾時")

    def test_bad_inst_becomes_failure_without_blocking_other_cpu(self):
        self.setup_cpu([call("bad", id="a"), call(id="b")],
                       [dict(tool("bad", argv=[]), _run="cpu"), dict(tool(), _run="cpu")])
        self.assertEqual(self.step(), 0)
        self.assertFalse(self.get("tool-results/0.json")["ok"])
        self.assertEqual(self.tick(), 0)
        self.assertEqual(self.step(), 0)
        self.assertIn("EmptyArgv", self.get(HISTORY)[1]["content"])
        self.assertEqual(self.get(HISTORY)[2]["content"], "{}")

    def test_result_read_validation_before_gate_or_sync(self):
        self.setup_cpu([call("sync", id="a"), call(id="b")],
                       [tool("sync", argv=["touch", "BAD"]), dict(tool(), _run="cpu")])
        self.put("ready", {})
        self.state(state="act", waits=[{"$opt": "consume", "$val": "ready"}])
        for value, code in [(None, "NotAnObject"), ({"ok": 1}, "FieldTypeMismatch"),
                            ({"ok": False}, "FieldTypeMismatch"),
                            ({"ok": True, "code": True, "kind": "child", "timed_out": False,
                              "stdout": "x"}, "FieldTypeMismatch")]:
            with self.subTest(value=value):
                self.put("tool-results/1.json", value)
                self.rejected(code)
        self.assertFalse(self.exists("BAD"))

    def test_invalid_utf8_is_one_line_cli_error(self):
        self.setup_cpu()
        path = self.put("tool-results/0.json", {})
        with open(path, "wb") as f:
            f.write(b"\xff")
        process = self.cli(self.d)
        self.assertEqual(process.returncode, 1)
        self.assertIn("JsonSyntax", process.stderr)
        self.assertEqual(len(process.stderr.splitlines()), 1)

    def test_bad_cpu_info_before_gate_mutation(self):
        self.setup_cpu()
        self.put("ready", {})
        self.state(state="act", waits=[{"$opt": "consume", "$val": "ready"}])
        self.write("T/info.json", "{broken")
        self.rejected("JsonSyntax")

    def test_receipt_does_not_need_cpu_info(self):
        self.setup_cpu()
        self.results()
        self.write("T/info.json", "{broken")
        self.assertEqual(self.step(), 0)

    def test_partial_results_without_waits_restore_all_gate(self):
        self.setup_cpu([call(id="a"), call(id="b")])
        self.results(1)
        self.assertEqual(self.step(), 0)
        self.assertEqual(len(self.get()["waits"][0]["$val"]), 2)
        self.assertEqual(self.step(), 101)
        self.assertFalse(self.exists("T/requests"))

    def test_previous_done_result_is_not_reused_for_new_batch(self):
        self.setup_cpu()
        self.put("tool-results/0.json.done", {"ok": True, "code": 0, "kind": "child",
                                              "timed_out": False, "stdout": "old"})
        self.assertEqual(self.step(), 0)
        self.assertEqual(len(self.get(HISTORY)), 1)
        self.assertEqual(len(os.listdir(os.path.join(self.d, "T/requests"))), 1)
        self.assertEqual(self.step(), 101)

    def test_closed_gate_defers_bad_tool_result(self):
        self.setup_cpu()
        self.state(state="act", waits=["pause"])
        self.write("tool-results/0.json", "{broken")
        self.assertEqual(self.step(), 101)
        self.put("pause", {})
        self.rejected("JsonSyntax")

    def test_partial_submission_failure_records_existing_work_without_sync(self):
        self.setup_cpu([call("sync", id="s"), call(id="a"), call(id="b")],
                       [tool("sync", argv=["touch", "BAD"]), dict(tool(), _run="cpu")])
        real_submit = aos_agent.aos_cpu.submit
        submitted = []

        def submit(cpu, name, request):
            if submitted:
                raise AgentError("ReadFailed", "第二份交件失敗")
            submitted.append(name)
            return real_submit(cpu, name, request)

        with mock.patch.object(aos_agent.aos_cpu, "submit", side_effect=submit):
            with self.assertRaises(AgentError):
                self.step()
        self.assertEqual(self.get(), {"state": "act"})
        self.assertFalse(self.exists("BAD"))
        self.assertEqual(self.tick(), 0)
        # D 不做 pending journal；第一份已有結果，就只能恢復 all 門。
        # 第二份尚未交件，因此這個已記 findings 的窗口仍可能永久等待。
        self.assertEqual(self.step(), 0)
        self.assertEqual(self.step(), 101)
        self.assertFalse(self.exists("BAD"))
        self.assertEqual(os.listdir(os.path.join(self.d, "T/requests")), [])

    def test_crash_after_history_before_rename_heals_and_discards_finished_results(self):
        self.setup_cpu([call(id="a"), call(id="b")])
        self.results(0, stdout="a")
        self.results(1, stdout="b")
        real_replace = os.replace

        def replace(src, dst):
            if src == os.path.join(self.d, "tool-results/1.json"):
                raise PermissionError("第二份結果封存中斷")
            return real_replace(src, dst)

        with mock.patch.object(aos_agent.os, "replace", side_effect=replace):
            with self.assertRaises(PermissionError):
                self.step()
        history = self.read(HISTORY)
        self.assertEqual(self.get()["state"], "act")
        self.assertTrue(self.exists("tool-results/0.json.done"))
        self.assertTrue(self.exists("tool-results/1.json"))
        self.assertEqual(self.step(), 0)
        self.assertEqual(self.read(HISTORY), history)
        self.assertEqual(self.get()["state"], "think")
        self.assertTrue(self.exists("tool-results/1.json.done"))
        self.assertFalse(self.exists("tool-results/1.json"))

    def test_crash_after_rename_before_state_does_not_repeat_sync(self):
        self.setup_cpu([call("sync", id="a"), call(id="b")],
                       [tool("sync", argv=["sh", "-c", "echo once >> side-effect"]),
                        dict(tool(), _run="cpu")])
        self.results(1)
        real_replace = os.replace

        def replace(src, dst):
            if dst == os.path.join(self.d, "state.json"):
                raise PermissionError("state 中斷")
            return real_replace(src, dst)

        with mock.patch.object(aos_agent.os, "replace", side_effect=replace):
            with self.assertRaises(PermissionError):
                self.step()
        self.assertEqual(self.step(), 0)
        self.assertEqual(self.read("side-effect"), "once\n")

    def test_inst_directives_resolved_on_agent_before_cpu(self):
        self.setup_cpu(tools=[dict(tool(argv=["printf", {"$env": "VALUE"}]), _run="cpu")])
        self.assertEqual(self.step(env={"VALUE": "literal $env"}), 0)
        self.assertEqual(self.tick(), 0)
        self.assertEqual(self.step(), 0)
        self.assertEqual(self.get(HISTORY)[-1]["content"], "literal $env")


class TestWrites(StepCase):

    def test_memory_input_state_replace_order(self):
        self.put("input.json", "hi")
        self.state(state="idle")
        real_replace = os.replace
        seen = []

        def replace(src, dst):
            seen.append((os.path.relpath(src, self.d), os.path.relpath(dst, self.d)))
            real_replace(src, dst)

        with mock.patch.object(aos_agent.os, "replace", side_effect=replace):
            self.assertEqual(self.step(), 0)
        self.assertEqual(seen, [(HISTORY + ".tmp", HISTORY), ("input.json", "input.json.done"),
                                ("state.json.tmp", "state.json")])

    def test_failed_state_replace_leaves_written_memory_and_consumed_input(self):
        self.put("input.json", "hi")
        self.state(state="idle")
        before = self.read("state.json")
        real_replace = os.replace

        def replace(src, dst):
            if dst == os.path.join(self.d, "state.json"):
                raise PermissionError("模擬 state 無法替換")
            real_replace(src, dst)

        with mock.patch.object(aos_agent.os, "replace", side_effect=replace), self.assertRaises(PermissionError):
            self.step()
        self.assertEqual(self.read("state.json"), before)
        self.assertEqual(self.get(HISTORY), [{"role": "user", "content": "hi"}])
        self.assertTrue(self.exists("input.json.done"))

    def test_failed_history_replace_leaves_input_and_state_untouched(self):
        self.put("input.json", "hi")
        self.state(state="idle")
        before = self.read("state.json")
        with mock.patch.object(aos_agent.os, "replace", side_effect=PermissionError("模擬記憶無法替換")), \
                self.assertRaises(PermissionError):
            self.step()
        self.assertEqual(self.read("state.json"), before)
        self.assertTrue(self.exists("input.json"))
        self.assertFalse(self.exists(HISTORY))


class TestCli(StepCase):

    def test_exit_zero(self):
        self.put("input.json", "hi")
        r = self.cli(self.d)
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))

    def test_wait_101(self):
        r = self.cli(self.d)
        self.assertEqual((r.returncode, r.stdout, r.stderr), (101, "", ""))

    def test_read_error_1(self):
        self.state(state="bad")
        r = self.cli(self.d)
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stderr.startswith("aos-agent: StateInvalid: "))
        self.assertEqual(len(r.stderr.splitlines()), 1)

    def test_not_agent_1(self):
        os.mkdir(os.path.join(self.d, "empty"))
        r = self.cli(os.path.join(self.d, "empty"))
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stderr.startswith("aos-agent: NotAnAgent: "))

    def test_usage_2(self):
        for args in ((self.d, "--bad"), (self.d, "extra"), ("--help",),
                     (os.path.join(self.d, "missing"),), (os.path.join(self.d, "info.json"),)):
            with self.subTest(args=args):
                r = self.cli(*args)
                self.assertEqual(r.returncode, 2)
                self.assertTrue(r.stderr.startswith("aos-agent: usage: "))
                self.assertEqual(len(r.stderr.splitlines()), 1)

    def test_default_dir(self):
        self.put("input.json", "hi")
        self.assertEqual(self.cli(cwd=self.d).returncode, 0)
        self.assertEqual(self.get()["state"], "think")

    def test_process_env(self):
        self.state(input={"$env": "AGENT_INPUT"})
        self.put("elsewhere.json", "hi")
        r = self.cli(self.d, env=dict(os.environ, AGENT_INPUT="elsewhere.json"))
        self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
