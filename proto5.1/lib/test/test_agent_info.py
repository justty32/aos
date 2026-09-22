"""aos_agent_info.load()：讀驗 agent 資料夾——照 spec/agent.md §1～§3、§5 ＋ spec/aos-llm-ask.md §2。全部在這個進程裡跑，不開子進程。

分幾群：預設值與回傳形狀、_metainfo 與 NotAnAgent、info.json 的指示詞（每格都解、位置、循環、
$opt 不吃）、人格檔、記憶檔（aos-llm-ask.md §2.3 每則怎麼驗）、工具檔（合併、去 _ key、ToolInvalid 各種）、engine。
"""
import json
import os
import unittest

from _util import OUTER, AgentCase, ENGINE, TOOL_SH, fmt

import aos_agent_info
from aos_agent_info import AgentError


def tool(name, **extra):
    """一個最小的合法工具元素，名字是 name。"""
    t = {"type": "function", "function": {"name": name}, "_meta": {"argv": ["true"]}}
    t.update(extra)
    return t


# ---------------------------------------------------------------- 預設值與回傳形狀 ----

class TestShape(AgentCase):

    def test_error_shape(self):
        e = AgentError("Foo", "白話")
        self.assertEqual((e.code, e.msg, str(e)), ("Foo", "白話", "Foo: 白話"))

    def test_minimal_agent_defaults(self):
        """只有 _metainfo 跟 engine：人格空、記憶空、沒工具、engine 補預設。"""
        r = self.load()
        self.assertEqual(r["dir"], self.d)
        self.assertEqual(r["metainfo"], {"_type": "llm_agent", "_version": 1})
        self.assertEqual(r["system"], "")
        self.assertEqual(r["system_path"], os.path.join(self.d, "prompts", "system.json"))
        self.assertEqual(r["history"], [])
        self.assertEqual(r["history_path"], os.path.join(self.d, "prompts", "history.json"))
        self.assertEqual((r["tools"], r["tools_raw"], r["tool_paths"]), ([], [], []))
        self.assertEqual(r["engine"], {"endpoint": ENGINE["endpoint"], "model": "test-model",
                                       "params": {}, "api_key": None, "timeout_ms": 120000, "cpu": None})

    def test_full_agent(self):
        """aos-llm-ask.md §2 那個範例：人格、記憶、兩份工具檔、engine 全寫。"""
        r = self.load(system={"content": "你是助手"},
                      history=[{"role": "user", "content": "hi"}],
                      tools={"tools/base.json": [TOOL_SH], "tools/team.json": [tool("mail")]},
                      info={"engine": {"endpoint": "http://x/v1", "model": "m", "params": {"temperature": 0.2},
                                       "api_key": "k", "timeout_ms": 5}})
        self.assertEqual(r["system"], "你是助手")
        self.assertEqual(r["history"], [{"role": "user", "content": "hi"}])
        self.assertEqual(r["tool_paths"], [os.path.join(self.d, "tools", "base.json"),
                                           os.path.join(self.d, "tools", "team.json")])
        self.assertEqual([t["function"]["name"] for t in r["tools"]], ["sh", "mail"])
        self.assertEqual(r["engine"], {"endpoint": "http://x/v1", "model": "m", "params": {"temperature": 0.2},
                                       "api_key": "k", "timeout_ms": 5, "cpu": None})

    def test_custom_paths_relative_to_agent_dir(self):
        """system／history／tools 的路徑相對於 agent 資料夾；絕對路徑照字面。"""
        self.write("p/s.json", json.dumps({"content": "S"}))
        self.write("p/h.json", "[]")
        abs_tool = self.write("elsewhere/t.json", json.dumps([tool("a")]))
        r = self.load(info={"system": "p/s.json", "history": "p/h.json", "tools": [abs_tool]})
        self.assertEqual(r["system"], "S")
        self.assertEqual(r["system_path"], os.path.join(self.d, "p", "s.json"))
        self.assertEqual(r["history_path"], os.path.join(self.d, "p", "h.json"))
        self.assertEqual(r["tool_paths"], [abs_tool])

    def test_unknown_top_level_keys_ignored(self):
        r = self.load(info={"state": "think", "note": 1, "x": [1]})
        self.assertNotIn("state", r)

    def test_state_json_is_not_touched(self):
        """state.json 壞掉也不管：這個模組不碰它。"""
        self.write("state.json", "{not json")
        self.load()
        self.assertEqual(self.read("state.json"), "{not json")

    def test_load_does_not_write_anything(self):
        d = self.agent(system={"content": "x"})
        before = sorted(os.listdir(d)), sorted(os.listdir(os.path.join(d, "prompts")))
        aos_agent_info.load(d)
        self.assertEqual((sorted(os.listdir(d)), sorted(os.listdir(os.path.join(d, "prompts")))), before)

    def test_strip_private(self):
        self.assertEqual(aos_agent_info.strip_private({"type": "f", "_meta": 1, "_note": 2, "x": {"_y": 3}}),
                         {"type": "f", "x": {"_y": 3}})


# ---------------------------------------------------------------- _metainfo／NotAnAgent ----

class TestMetainfo(AgentCase):

    def test_no_info_json(self):
        with self.assertRaises(AgentError) as cm:
            aos_agent_info.load(self.d)
        self.assertEqual(cm.exception.code, "NotAnAgent")
        self.assertIn("info.json", str(cm.exception))

    def test_dir_missing_is_also_not_an_agent(self):
        with self.assertRaises(AgentError) as cm:
            aos_agent_info.load(os.path.join(self.d, "nope"))
        self.assertEqual(cm.exception.code, "NotAnAgent")

    def test_info_not_json(self):
        self.bad("JsonSyntax", info="{oops")

    def test_info_not_object(self):
        self.bad("NotAnObject", info="[1, 2]")

    def test_info_unreadable(self):
        d = self.agent()
        os.chmod(os.path.join(d, "info.json"), 0)
        self.addCleanup(os.chmod, os.path.join(d, "info.json"), 0o644)
        if os.access(os.path.join(d, "info.json"), os.R_OK):
            self.skipTest("root 什麼都讀得到")
        with self.assertRaises(AgentError) as cm:
            aos_agent_info.load(d)
        self.assertEqual(cm.exception.code, "ReadFailed")

    def test_missing_metainfo(self):
        self.bad("NotAnAgent", info={}, metainfo=False)

    def test_metainfo_not_object(self):
        self.bad("MetainfoInvalid", info={"_metainfo": "llm_agent"})

    def test_metainfo_missing_type(self):
        self.bad("NotAnAgent", info={"_metainfo": {"_version": 1}})

    def test_wrong_type(self):
        e = self.bad("NotAnAgent", info={"_metainfo": {"_type": "posix", "_version": 1}})
        self.assertIn("posix", str(e))

    def test_type_not_string(self):
        self.bad("NotAnAgent", info={"_metainfo": {"_type": 1, "_version": 1}})

    def test_missing_version(self):
        self.bad("MetainfoInvalid", info={"_metainfo": {"_type": "llm_agent"}})

    def test_version_not_1(self):
        self.bad("UnsupportedVersion", info={"_metainfo": {"_type": "llm_agent", "_version": 2}})
        self.bad("UnsupportedVersion", info={"_metainfo": {"_type": "llm_agent", "_version": "1"}})
        self.bad("UnsupportedVersion", info={"_metainfo": {"_type": "llm_agent", "_version": True}})

    def test_metainfo_extra_keys_ignored(self):
        r = self.load(info={"_metainfo": {"_type": "llm_agent", "_version": 1, "_note": "x"}})
        self.assertEqual(r["metainfo"], {"_type": "llm_agent", "_version": 1})

    def test_metainfo_is_resolved(self):
        """跟 inst 不同：_metainfo 也解指示詞——整包 $ref、_type 用 $env。"""
        self.write("mi.json", json.dumps({"_type": "llm_agent", "_version": 1}))
        r = self.load(info={"_metainfo": {"$ref": "mi.json"}})
        self.assertEqual(r["metainfo"]["_type"], "llm_agent")
        r = self.load(info={"_metainfo": {"_type": {"$env": "T"}, "_version": 1}}, env={"T": "llm_agent"})
        self.assertEqual(r["metainfo"]["_type"], "llm_agent")
        self.bad("NotAnAgent", info={"_metainfo": {"_type": {"$env": "T"}, "_version": 1}}, env={"T": "posix"})

    def test_metainfo_directive_error_is_not_notanagent(self):
        """解不開是指示詞的錯，不是 NotAnAgent。"""
        self.bad("EnvironmentVariableMissing", info={"_metainfo": {"_type": {"$env": "NOPE"}, "_version": 1}},
                 env={})
        self.bad("ReferenceReadFailed", info={"_metainfo": {"$ref": "missing.json"}})


# ---------------------------------------------------------------- info.json 的指示詞 ----

class TestDirectives(AgentCase):

    def test_env_in_every_field(self):
        self.write("s.json", json.dumps({"content": "S"}))
        self.write("h.json", "[]")
        self.write("t.json", json.dumps([tool("a")]))
        r = self.load(info={"system": {"$env": "S"}, "history": {"$env": "H"}, "tools": [{"$env": "T"}],
                            "engine": {"endpoint": {"$env": "E"}, "model": {"$env": "M"}}},
                      env={"S": "s.json", "H": "h.json", "T": "t.json", "E": "http://e/v1", "M": "mm"})
        self.assertEqual(r["system"], "S")
        self.assertEqual(r["tool_paths"], [os.path.join(self.d, "t.json")])
        self.assertEqual((r["engine"]["endpoint"], r["engine"]["model"]), ("http://e/v1", "mm"))

    def test_env_reads_the_given_table_not_os_environ(self):
        self.bad("EnvironmentVariableMissing", info={"system": {"$env": "PATH"}}, env={})

    def test_env_default_is_os_environ(self):
        d = self.agent(info={"engine": {"endpoint": "http://e", "model": {"$env": "PATH"}}})
        self.assertEqual(aos_agent_info.load(d)["engine"]["model"], os.environ["PATH"])

    def test_fmt(self):
        r = self.load(info={"engine": {"endpoint": fmt("http://${h}:${p}/v1", h="127.0.0.1", p={"$env": "P"}),
                                       "model": "m"}}, env={"P": "1234"})
        self.assertEqual(r["engine"]["endpoint"], "http://127.0.0.1:1234/v1")

    def test_ref_relative_to_agent_dir_not_to_info_json(self):
        """$ref 的中心路徑＝agent 資料夾（info.json 就在那裡，所以一樣）；整包 engine 從別的檔拿。"""
        self.write("engines/lm.json", json.dumps({"endpoint": "http://lm/v1", "model": "q", "params": {"t": 1}}))
        r = self.load(info={"engine": {"$ref": "engines/lm.json"}})
        self.assertEqual(r["engine"]["endpoint"], "http://lm/v1")
        self.assertEqual(r["engine"]["params"], {"t": 1})

    def test_ref_with_at_and_hash(self):
        self.write("all.json", json.dumps({"eng": {"endpoint": "http://a/v1", "model": "m"}, "tools": ["t.json"]}))
        self.write("t.json", json.dumps([tool("a")]))
        r = self.load(info={"engine": {"$ref": "all.json", "$at": "/eng"}, "tools": {"$ref": "all.json#/tools"}})
        self.assertEqual(r["engine"]["model"], "m")
        self.assertEqual([t["function"]["name"] for t in r["tools"]], ["a"])

    def test_ref_self_relative_position_is_physical_path(self):
        """$ref:"" 相對 $at：位置是實體路徑（/engine/model 往上一層是 /engine）。"""
        r = self.load(info={"engine": {"endpoint": "http://a/v1", "model": {"$ref": "", "$at": "../name"},
                                       "name": "from-sibling"}})
        self.assertEqual(r["engine"]["model"], "from-sibling")

    def test_tools_array_elements_resolved_and_position_is_index(self):
        self.write("t1.json", json.dumps([tool("a")]))
        self.write("t2.json", json.dumps([tool("b")]))
        self.write("t3.json", json.dumps([tool("c")]))
        r = self.load(info={"tools": ["t1.json", {"$ref": "", "$at": "/alt"}, {"$ref": "", "$at": "../../third"}],
                            "alt": "t2.json", "third": "t3.json"}, tools=None)
        self.assertEqual([os.path.basename(p) for p in r["tool_paths"]], ["t1.json", "t2.json", "t3.json"])

    def test_container_from_other_file_resolves_inside_that_file(self):
        """走進 $ref 取回來的容器：裡面的 $ref:"" 指的是那份檔，不是 info.json。"""
        self.write("eng.json", json.dumps({"endpoint": {"$ref": "", "$at": "/real"}, "model": "m",
                                           "real": "http://from-eng-json/v1"}))
        r = self.load(info={"engine": {"$ref": "eng.json"}})
        self.assertEqual(r["engine"]["endpoint"], "http://from-eng-json/v1")

    def test_top_level_ref(self):
        """整份 info.json 可以是一個 $ref。"""
        self.write("real-info.json", json.dumps({"_metainfo": {"_type": "llm_agent", "_version": 1},
                                                 "engine": {"endpoint": "http://top/v1", "model": "m"}}))
        self.write("info.json", json.dumps({"$ref": "real-info.json"}))
        r = aos_agent_info.load(self.d, env=OUTER)
        self.assertEqual(r["engine"]["endpoint"], "http://top/v1")

    def test_params_resolved_deeply(self):
        """engine.params 每一格都解，巢狀的也解。"""
        r = self.load(info={"engine": {"endpoint": "http://a/v1", "model": "m",
                                       "params": {"temperature": {"$ref": "", "$at": "/t"},
                                                  "nested": {"x": [{"$env": "V"}, "lit"]}}}, "t": 0.5},
                      env={"V": "vv"})
        self.assertEqual(r["engine"]["params"], {"temperature": 0.5, "nested": {"x": ["vv", "lit"]}})

    def test_cycle(self):
        self.bad("ReferenceCycle", info={"system": {"$ref": "", "$at": "."}})
        self.bad("ReferenceCycle", info={"system": {"$ref": "", "$at": "/history"},
                                         "history": {"$ref": "", "$at": "/system"}})

    def test_same_target_from_two_fields_is_fine(self):
        self.write("p.json", json.dumps("prompts/x.json"))
        r = self.load(info={"system": {"$ref": "p.json"}, "history": {"$ref": "p.json"}})
        self.assertEqual(r["system_path"], r["history_path"])

    def test_unknown_directive(self):
        self.bad("UnknownDirective", info={"system": {"$xyz": 1}})

    def test_opt_is_not_accepted_anywhere(self):
        """agent.md 沒有任何選項表：哪一格放 $opt 都是 UnknownOption。"""
        self.bad("UnknownOption", info={"system": {"$opt": "append", "$val": "s.json"}})
        self.bad("UnknownOption", info={"engine": {"$opt": "x"}})
        self.bad("UnknownOption", info={"tools": [{"$opt": "x", "$val": "t.json"}]})
        self.bad("UnknownOption", info={"_metainfo": {"$opt": "x"}})

    def test_directive_error_wrapped_as_agent_error(self):
        e = self.bad("ReferencePointerInvalid", info={"system": {"$ref": "", "$at": "x/y"}})
        self.assertIsInstance(e, AgentError)

    def test_referenced_files_are_not_resolved(self):
        """system／history／tools 指到的檔原樣：裡面的 $ 開頭 key 不會被當指示詞。"""
        r = self.load(system={"content": "有 ${x} 跟 $env 都是字面"},
                      history=[{"role": "assistant", "content": None,
                                "tool_calls": [{"id": "c1", "type": "function",
                                                "function": {"name": "sh", "arguments": "{\"$ref\": 1}"}}]},
                               {"role": "tool", "tool_call_id": "c1", "content": "x", "$weird": {"$env": "NOPE"}}],
                      tools={"t.json": [tool("a", _meta={"argv": [{"$env": "NOPE"}], "cwd": {"$ref": "no.json"}},
                                             _note={"$opt": "x"})]},
                      env={})
        self.assertEqual(r["system"], "有 ${x} 跟 $env 都是字面")
        self.assertEqual(r["history"][1]["$weird"], {"$env": "NOPE"})
        self.assertEqual(r["tools_raw"][0]["_meta"]["argv"], [{"$env": "NOPE"}])


# ---------------------------------------------------------------- 人格檔 ----

class TestSystem(AgentCase):

    def test_missing_file_is_empty_string(self):
        self.assertEqual(self.load(info={"system": "nope.json"})["system"], "")

    def test_content(self):
        self.assertEqual(self.load(system={"content": "嗨"})["system"], "嗨")

    def test_empty_content_stays_empty(self):
        self.assertEqual(self.load(system={"content": ""})["system"], "")

    def test_bad_json(self):
        self.bad("JsonSyntax", system="{")

    def test_not_object(self):
        self.bad("NotAnObject", system="[]")

    def test_content_not_string(self):
        self.bad("FieldTypeMismatch", system={"content": 1})
        self.bad("FieldTypeMismatch", system={"no": "content"})

    def test_extra_keys_ignored(self):
        self.assertEqual(self.load(system={"content": "x", "role": "system"})["system"], "x")

    def test_field_type(self):
        self.bad("FieldTypeMismatch", info={"system": ["a"]})
        self.bad("FieldTypeMismatch", info={"system": None})


# ---------------------------------------------------------------- 記憶檔 ----

class TestHistory(AgentCase):

    def test_missing_file_is_empty_list(self):
        self.assertEqual(self.load(info={"history": "nope.json"})["history"], [])

    def test_example_from_spec(self):
        h = [{"role": "user", "content": "看看資料夾裡有什麼"},
             {"role": "assistant", "content": None,
              "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "sh", "arguments": "{\"cmd\":\"ls\"}"}}]},
             {"role": "tool", "tool_call_id": "c1", "content": "state.json\nprompts\ntools\n"},
             {"role": "assistant", "content": "裡面有 state.json、prompts、tools…"}]
        self.assertEqual(self.load(history=h)["history"], h)

    def test_unknown_keys_kept_verbatim(self):
        h = [{"role": "user", "content": "x", "name": "bob", "_ts": 123, "reasoning": {"a": 1}}]
        self.assertEqual(self.load(history=h)["history"], h)

    def test_bad_json(self):
        self.bad("JsonSyntax", history="[")

    def test_not_array(self):
        self.bad("NotAnArray", history="{}")

    def test_message_not_object(self):
        self.bad("MessageInvalid", history=["hi"])

    def test_system_role_not_allowed(self):
        self.bad("MessageInvalid", history=[{"role": "system", "content": "x"}])

    def test_unknown_role(self):
        self.bad("MessageInvalid", history=[{"role": "developer", "content": "x"}])
        self.bad("MessageInvalid", history=[{"content": "x"}])

    def test_user_content_must_be_string(self):
        self.bad("MessageInvalid", history=[{"role": "user"}])
        self.bad("MessageInvalid", history=[{"role": "user", "content": None}])
        self.bad("MessageInvalid", history=[{"role": "user", "content": [{"type": "text", "text": "x"}]}])

    def test_tool_needs_string_content_and_call_id(self):
        self.bad("MessageInvalid", history=[{"role": "tool", "content": "x"}])
        self.bad("MessageInvalid", history=[{"role": "tool", "content": "x", "tool_call_id": 1}])
        self.bad("MessageInvalid", history=[{"role": "tool", "tool_call_id": "c1", "content": None}])

    def test_assistant_needs_content_or_tool_calls(self):
        self.bad("MessageInvalid", history=[{"role": "assistant"}])
        self.bad("MessageInvalid", history=[{"role": "assistant", "content": None}])
        self.bad("MessageInvalid", history=[{"role": "assistant", "content": None, "tool_calls": None}])
        self.assertEqual(len(self.load(history=[{"role": "assistant", "content": ""}])["history"]), 1)
        self.assertEqual(len(self.load(history=[{"role": "assistant", "tool_calls": []}])["history"]), 1)

    def test_error_says_which_message(self):
        e = self.bad("MessageInvalid", history=[{"role": "user", "content": "ok"}, {"role": "x"}])
        self.assertIn("第 1 則", str(e))

    def test_field_type(self):
        self.bad("FieldTypeMismatch", info={"history": 3})


# ---------------------------------------------------------------- 工具檔 ----

class TestTools(AgentCase):

    def test_timeout_preserved_raw_and_hidden_from_model(self):
        t = tool("slow", _timeout_ms=17)
        r = self.load(tools={"t.json": [t]})
        self.assertEqual(r["tools_raw"], [t])
        self.assertNotIn("_timeout_ms", r["tools"][0])
        self.assertNotIn("_timeout_ms", r["tools_raw"][0]["_meta"])

    def test_timeout_requires_literal_positive_integer(self):
        for value in (0, -1, True, False, 1.5, "60", None, {"$env": "LIMIT"}):
            with self.subTest(value=value):
                e = self.bad("ToolInvalid", tools={"t.json": [tool("slow", _timeout_ms=value)]})
                self.assertIn("_timeout_ms", str(e))
                self.assertIn("t.json", str(e))

    def test_merge_in_file_order(self):
        r = self.load(tools={"tools/b.json": [tool("b1"), tool("b2")], "tools/a.json": [tool("a1")]},
                      info={"tools": ["tools/b.json", "tools/a.json"]})
        self.assertEqual([t["function"]["name"] for t in r["tools"]], ["b1", "b2", "a1"])
        r = self.load(tools={"tools/b.json": [tool("b1"), tool("b2")], "tools/a.json": [tool("a1")]},
                      info={"tools": ["tools/a.json", "tools/b.json"]})
        self.assertEqual([t["function"]["name"] for t in r["tools"]], ["a1", "b1", "b2"])

    def test_underscore_keys_stripped_for_model_only(self):
        t = tool("a", _note="說明", description="d")
        t["function"]["description"] = "desc"
        t["function"]["_private"] = "stays: only top-level _ keys are stripped"
        r = self.load(tools={"t.json": [t]})
        self.assertEqual(r["tools"], [{"type": "function", "description": "d",
                                       "function": {"name": "a", "description": "desc",
                                                    "_private": "stays: only top-level _ keys are stripped"}}])
        self.assertEqual(r["tools_raw"], [t])
        self.assertIn("_meta", r["tools_raw"][0])

    def test_function_extras_verbatim(self):
        t = tool("a")
        t["function"].update({"parameters": {"type": "object"}, "strict": True, "weird": [1]})
        self.assertEqual(self.load(tools={"t.json": [t]})["tools"][0]["function"], t["function"])

    def test_missing_file_is_read_failed(self):
        e = self.bad("ReadFailed", info={"tools": ["tools/nope.json"]})
        self.assertIn("tools/nope.json", str(e))

    def test_bad_json(self):
        self.bad("JsonSyntax", tools={"t.json": "[oops"})

    def test_file_not_array(self):
        self.bad("ToolInvalid", tools={"t.json": {"type": "function"}})

    def test_empty_file_ok(self):
        self.assertEqual(self.load(tools={"t.json": []})["tools"], [])

    def test_element_not_object(self):
        self.bad("ToolInvalid", tools={"t.json": ["sh"]})

    def test_missing_type(self):
        t = tool("a"); del t["type"]
        self.bad("ToolInvalid", tools={"t.json": [t]})

    def test_missing_function(self):
        self.bad("ToolInvalid", tools={"t.json": [{"type": "function", "_meta": {}}]})
        self.bad("ToolInvalid", tools={"t.json": [{"type": "function", "function": "sh", "_meta": {}}]})

    def test_missing_name(self):
        self.bad("ToolInvalid", tools={"t.json": [{"type": "function", "function": {}, "_meta": {}}]})
        self.bad("ToolInvalid", tools={"t.json": [{"type": "function", "function": {"name": ""}, "_meta": {}}]})
        self.bad("ToolInvalid", tools={"t.json": [{"type": "function", "function": {"name": 1}, "_meta": {}}]})

    def test_missing_meta(self):
        t = tool("a"); del t["_meta"]
        e = self.bad("ToolInvalid", tools={"t.json": [t]})
        self.assertIn("_meta", str(e))

    def test_meta_not_object(self):
        self.bad("ToolInvalid", tools={"t.json": [tool("a", _meta="tools/bin/x")]})
        self.bad("ToolInvalid", tools={"t.json": [tool("a", _meta=["x"])]})

    def test_meta_forbids_stdin_stdout(self):
        self.bad("ToolInvalid", tools={"t.json": [tool("a", _meta={"argv": ["x"], "stdin": "in.txt"})]})
        self.bad("ToolInvalid", tools={"t.json": [tool("a", _meta={"argv": ["x"], "stdout": {"$opt": "inherit"}})]})
        r = self.load(tools={"t.json": [tool("a", _meta={"argv": ["x"], "stderr": "e", "exit": "c",
                                                          "cwd": "sub", "envs": {"A": "1"}})]})
        self.assertEqual(r["tools_raw"][0]["_meta"]["stderr"], "e")

    def test_meta_is_not_validated_as_inst_here(self):
        """_meta 是不是合法 inst 是跑的時候的事：這裡只看它是物件、沒 stdin／stdout。"""
        self.assertEqual(len(self.load(tools={"t.json": [tool("a", _meta={})]})["tools"]), 1)

    def test_duplicate_name_across_files(self):
        e = self.bad("ToolInvalid", tools={"a.json": [tool("sh")], "b.json": [tool("sh")]})
        self.assertIn("sh", str(e))

    def test_duplicate_name_in_same_file(self):
        self.bad("ToolInvalid", tools={"a.json": [tool("sh"), tool("sh")]})

    def test_error_says_which_file_and_index(self):
        e = self.bad("ToolInvalid", tools={"ok.json": [tool("a")], "bad.json": [tool("b"), "x"]})
        self.assertIn("bad.json", str(e))
        self.assertIn("第 1 個", str(e))

    def test_field_type(self):
        self.bad("FieldTypeMismatch", info={"tools": "tools/base.json"})
        self.bad("FieldTypeMismatch", info={"tools": [1]})


# ---------------------------------------------------------------- engine ----

class TestEngine(AgentCase):

    def eng(self, **kw):
        return self.load(info={"engine": kw})

    def bad_eng(self, code="EngineInvalid", **kw):
        return self.bad(code, info={"engine": kw})

    def test_missing_engine(self):
        self.write("info.json", json.dumps({"_metainfo": {"_type": "llm_agent", "_version": 1}}))
        with self.assertRaises(AgentError) as cm:
            aos_agent_info.load(self.d)
        self.assertEqual(cm.exception.code, "EngineInvalid")

    def test_engine_not_object_is_field_type_mismatch(self):
        self.bad("FieldTypeMismatch", info={"engine": "http://x"})

    def test_required(self):
        self.bad_eng(model="m")
        self.bad_eng(endpoint="http://x")
        self.bad_eng(endpoint="", model="m")
        self.bad_eng(endpoint=1, model="m")
        self.bad_eng(endpoint="http://x", model=None)

    def test_params(self):
        self.assertEqual(self.eng(endpoint="e", model="m", params={"a": 1})["engine"]["params"], {"a": 1})
        self.bad_eng(endpoint="e", model="m", params=[1])
        self.bad_eng(endpoint="e", model="m", params="t=1")

    def test_api_key(self):
        self.assertEqual(self.eng(endpoint="e", model="m", api_key="k")["engine"]["api_key"], "k")
        self.assertEqual(self.eng(endpoint="e", model="m", api_key="")["engine"]["api_key"], "")
        self.assertIsNone(self.eng(endpoint="e", model="m")["engine"]["api_key"])
        self.bad_eng(endpoint="e", model="m", api_key=None)
        self.bad_eng(endpoint="e", model="m", api_key=123)

    def test_api_key_from_env_missing_is_an_error(self):
        """設定壞就不跑，不降級（aos-llm-ask.md §2.5）。"""
        self.bad("EnvironmentVariableMissing",
                 info={"engine": {"endpoint": "e", "model": "m", "api_key": {"$env": "LMSTUDIO_KEY"}}}, env={})
        r = self.load(info={"engine": {"endpoint": "e", "model": "m", "api_key": {"$env": "LMSTUDIO_KEY"}}},
                      env={"LMSTUDIO_KEY": "sk"})
        self.assertEqual(r["engine"]["api_key"], "sk")

    def test_timeout_ms(self):
        self.assertEqual(self.eng(endpoint="e", model="m", timeout_ms=7)["engine"]["timeout_ms"], 7)
        self.assertEqual(self.eng(endpoint="e", model="m")["engine"]["timeout_ms"], 120000)
        self.bad_eng(endpoint="e", model="m", timeout_ms=0)
        self.bad_eng(endpoint="e", model="m", timeout_ms=-1)
        self.bad_eng(endpoint="e", model="m", timeout_ms="5")
        self.bad_eng(endpoint="e", model="m", timeout_ms=True)
        self.bad_eng(endpoint="e", model="m", timeout_ms=1.5)

    def test_unknown_engine_keys_ignored(self):
        r = self.eng(endpoint="e", model="m", kind="openai", retries=3)
        self.assertEqual(sorted(r["engine"]), ["api_key", "cpu", "endpoint", "model", "params", "timeout_ms"])

    def test_cpu_path_defaults_and_relative_absolute(self):
        self.assertIsNone(self.eng(endpoint="e", model="m")["engine"]["cpu"])
        self.assertEqual(self.eng(endpoint="e", model="m", cpu="../cpu")["engine"]["cpu"],
                         os.path.normpath(os.path.join(self.d, "../cpu")))
        self.assertEqual(self.eng(endpoint="e", model="m", cpu="/tmp/cpu")["engine"]["cpu"], "/tmp/cpu")
        self.assertEqual(self.eng(endpoint="e", model="m", cpu="")["engine"]["cpu"], self.d)

    def test_cpu_directive_and_referenced_engine_stay_relative_to_agent(self):
        self.write("conf/engine.json", json.dumps({"endpoint": "e", "model": "m", "cpu": {"$env": "CPU"}}))
        r = self.load(info={"engine": {"$ref": "conf/engine.json"}}, env={"CPU": "workers"})
        self.assertEqual(r["engine"]["cpu"], os.path.join(self.d, "workers"))

    def test_cpu_invalid_type_and_missing_directive(self):
        for value in (None, 7, True, [], {}):
            with self.subTest(value=value):
                self.bad_eng(endpoint="e", model="m", cpu=value)
        self.bad("EnvironmentVariableMissing",
                 info={"engine": {"endpoint": "e", "model": "m", "cpu": {"$env": "CPU"}}}, env={})


if __name__ == "__main__":
    unittest.main()
