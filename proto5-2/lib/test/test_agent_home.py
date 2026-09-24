"""agent.md §2～§3 共用讀驗回歸；所有檔案只放暫存家。"""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import aos_agent_home as home
from aos_directives import Context


def tool(name="echo"):
    return {"type": "function", "function": {"name": name}, "_meta": {"argv": ["echo"]}}


def tool_call(ident="c1"):
    return {"id": ident, "type": "function", "function": {"name": "echo", "arguments": "{}"}}


class AgentHomeTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.info = {"_metainfo": {"_type": "llm_agent", "_version": 1}, "llm": {"model": "small"}}
        self.save()

    def write(self, name, value):
        path = self.base / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path

    def save(self):
        self.write("info.json", self.info)

    def load(self):
        self.save()
        return home.load_llm_view(self.base, env={})

    def error(self, code, fn, *args, **kwargs):
        with self.assertRaises(home.AgentError) as cm:
            fn(*args, **kwargs)
        self.assertEqual(cm.exception.code, code)
        self.assertEqual(str(cm.exception), code + ": " + cm.exception.msg)

    def field_error(self, path, value, code="FieldTypeMismatch"):
        obj = self.info
        for k in path[:-1]:
            obj = obj[k]
        obj[path[-1]] = value
        self.error(code, self.load)

    def invalid_message(self, msg):
        self.error("MessageInvalid", home.check_message, msg)

    def invalid_tool(self, value):
        self.error("ToolInvalid", home.read_tools, [self.write("tools.json", value)])

    def test_defaults(self):
        view = self.load()
        self.assertEqual((view["system"], view["history"], view["tools"], view["params"]), ("", [], [], {}))
        self.assertEqual(view["system_path"], str(self.base / "prompts/system.json"))
        self.assertEqual(view["history_path"], str(self.base / "prompts/history.json"))

    def test_metainfo_missing(self):
        del self.info["_metainfo"]
        self.error("MetainfoInvalid", self.load)

    def test_metainfo_non_object(self):
        self.field_error(["_metainfo"], None, "MetainfoInvalid")

    def test_metainfo_missing_fields(self):
        for v in ({}, {"_type": "llm_agent"}, {"_version": 1}):
            with self.subTest(v=v):
                self.error("MetainfoInvalid", home.check_metainfo, v)

    def test_metainfo_wrong_type(self):
        self.field_error(["_metainfo", "_type"], "posix", "NotAnAgent")

    def test_metainfo_version(self):
        for v in (True, False, 1.0, "1", 2, None):
            with self.subTest(v=v):
                self.field_error(["_metainfo", "_version"], v, "UnsupportedVersion")

    def test_system_field_type(self):
        self.field_error(["system"], None)

    def test_history_field_type(self):
        self.field_error(["history"], None)

    def test_tools_field_type(self):
        for v in (None, {}, "tools.json", [None]):
            self.field_error(["tools"], v)

    def test_model_field_type(self):
        for v in (None, "", [], 2):
            self.field_error(["llm", "model"], v)

    def test_params_field_type(self):
        for v in (None, [], "x"):
            self.field_error(["llm", "params"], v)

    def test_llm_missing(self):
        del self.info["llm"]
        self.error("LlmInvalid", self.load)

    def test_model_missing(self):
        del self.info["llm"]["model"]
        self.error("LlmInvalid", self.load)

    def test_llm_literal(self):
        for v in (None, [], {"$env": "missing"}):
            self.field_error(["llm"], v)

    def test_unused_fields_never_resolved(self):
        for k in ("tick", "tool_pool", "unrecognized"):
            self.info[k] = {"$env": "MISSING"}
        self.info["llm"].update(pool={"$env": "MISSING"}, timeout_ms={"$env": "MISSING"})
        self.assertEqual(self.load()["model"], "small")

    def test_params_reference_original_document(self):
        self.info["shared"] = {"temperature": 0.25}
        self.info["llm"]["params"] = {"$ref": "", "$at": "/shared"}
        self.assertEqual(self.load()["params"], {"temperature": 0.25})

    def test_params_relative_reference(self):
        self.info["llm"].update(shared={"temperature": 0.5}, params={"$ref": "", "$at": "../shared"})
        self.assertEqual(self.load()["params"], {"temperature": 0.5})

    def test_reference_container_retains_location(self):
        self.write("other.json", {"shared": {"first": 3, "second": {"$ref": "", "$at": "../first"}}})
        self.info["llm"]["params"] = {"$ref": "other.json#/shared"}
        self.assertEqual(self.load()["params"], {"first": 3, "second": 3})

    def test_reference_cycle_preserved(self):
        self.info["llm"]["params"] = {"x": {"$ref": "", "$at": "/llm/params"}}
        self.error("ReferenceCycle", self.load)

    def test_resolve_field_public_api(self):
        self.info["llm"]["params"] = {"x": {"$env": "VALUE"}}
        self.save()
        doc = home.read_info_doc(self.base)
        self.assertEqual(home.resolve_field(doc, Context(doc, env={"VALUE": "ok"}), ["llm", "params"]), {"x": "ok"})

    def test_directive_errors_preserved(self):
        self.info["system"] = {"$ref": "missing.json"}
        self.error("ReferenceReadFailed", self.load)
        self.info["system"] = {"$env": "MISSING"}
        self.error("EnvironmentVariableMissing", self.load)

    def test_opt_in_all_six_fields(self):
        original = copy.deepcopy(self.info)
        for path in (["_metainfo"], ["system"], ["history"], ["tools"], ["llm", "model"], ["llm", "params"]):
            for option in ("unknown", None, [], 1):
                with self.subTest(path=path, option=option):
                    self.info = copy.deepcopy(original)
                    self.field_error(path, {"$opt": option, "$val": "x"}, "UnknownOption")

    def test_opt_nested_and_referenced(self):
        for value in ({"x": [{"$opt": "x"}]}, {"$ref": "opts.json"}):
            self.write("opts.json", {"x": {"$opt": "x"}})
            self.field_error(["llm", "params"], value, "UnknownOption")

    def test_opt_inside_format_and_reference(self):
        for value in ({"$opt": None}, {"$ref": "option.json"}):
            self.write("option.json", {"$opt": "unknown"})
            self.info["system"] = {"$fmt": {"$val": "${p}", "p": value}}
            self.error("UnknownOption", self.load)
        self.write("format.json", {"$fmt": {"$val": {"$opt": "unknown"}}})
        self.info["system"] = {"$ref": "format.json"}
        self.error("UnknownOption", self.load)

    def test_ignored_directive_keys_not_checked_for_options(self):
        self.info["system"] = {"$env": "SYSTEM", "ignored": {"$opt": "unknown"}}
        self.save()
        self.assertEqual(home.load_llm_view(self.base, {"SYSTEM": "missing.json"})["system"], "")

    def test_system_directory(self):
        self.field_error(["system"], ".")

    def test_history_directory(self):
        self.field_error(["history"], ".")

    def test_tools_directory_sorted_done_excluded(self):
        self.write("tools/b.json", [tool("b")])
        self.write("tools/a.json", [tool("a")])
        self.write("tools/c.json.done", [tool("bad")])
        self.write("tools/c.txt", [tool("bad")])
        self.write("tools/sub/d.json", [tool("bad")])
        self.write("last.json", [tool("last")])
        self.info["tools"] = ["tools", "last.json"]
        view = self.load()
        self.assertEqual([t["function"]["name"] for t in view["tools"]], ["a", "b", "last"])
        self.assertEqual([Path(p).name for p in view["tool_paths"]], ["a.json", "b.json", "last.json"])
        self.assertIn("_meta", view["tools_raw"][0])
        self.assertNotIn("_meta", view["tools"][0])

    def test_info_missing(self):
        self.error("NotAnAgent", home.read_info_doc, self.base / "missing")

    def test_info_read_failed(self):
        with patch("builtins.open", side_effect=PermissionError("禁止")):
            self.error("ReadFailed", home.read_info_doc, self.base)

    def test_info_json_syntax(self):
        (self.base / "info.json").write_text("{", encoding="utf-8")
        self.error("JsonSyntax", home.read_info_doc, self.base)

    def test_info_not_object(self):
        self.write("info.json", [])
        self.error("NotAnObject", home.read_info_doc, self.base)

    def test_info_directive_not_followed(self):
        self.write("info.json", {"$env": "MISSING"})
        self.error("FieldTypeMismatch", home.read_info_doc, self.base)

    def test_system_invalid(self):
        for value in ([], None, {}, {"content": None}, {"content": {"$env": "X"}}):
            self.error("MessageInvalid", home.read_system, self.write("system.json", value))

    def test_history_not_array(self):
        self.error("NotAnArray", home.read_history, self.write("history.json", {}))

    def test_history_invalid_message(self):
        self.error("MessageInvalid", home.read_history, self.write("history.json", [{"role": "system", "content": "x"}]))

    def test_content_not_resolved(self):
        self.assertEqual(home.read_system(self.write("system.json", {"content": "$env:X"})), "$env:X")
        msg = {"role": "user", "content": "hi", "extra": {"$env": "MISSING"}}
        self.assertEqual(home.read_history(self.write("history.json", [msg])), [msg])
        t = tool()
        t["_meta"]["stderr"] = {"$opt": "merge"}
        t["function"]["parameters"] = {"$ref": "MISSING"}
        self.assertEqual(home.read_tools([self.write("tools.json", [t])]), [t])

    def test_content_io_errors(self):
        for reader in (home.read_system, home.read_history):
            path = self.base / "bad.json"
            path.write_text("{", encoding="utf-8")
            self.error("JsonSyntax", reader, path)
            with patch("builtins.open", side_effect=PermissionError("禁止")):
                self.error("ReadFailed", reader, path)
        self.error("ReadFailed", home.read_tools, [self.base / "missing"])
        self.error("JsonSyntax", home.read_tools, [path])

    def test_tool_top_array(self):
        self.invalid_tool({})

    def test_tool_object(self):
        self.invalid_tool([None])

    def test_tool_type(self):
        t = tool()
        t["type"] = "custom"
        self.invalid_tool([t])

    def test_tool_function(self):
        t = tool()
        t["function"] = None
        self.invalid_tool([t])

    def test_tool_name(self):
        for fn in ({}, {"name": ""}, {"name": 1}):
            t = tool()
            t["function"] = fn
            self.invalid_tool([t])

    def test_tool_description(self):
        t = tool()
        t["function"]["description"] = None
        self.invalid_tool([t])

    def test_tool_parameters(self):
        t = tool()
        t["function"]["parameters"] = []
        self.invalid_tool([t])

    def test_tool_meta(self):
        t = tool()
        t["_meta"] = None
        self.invalid_tool([t])
        del t["_meta"]
        self.invalid_tool([t])

    def test_tool_forbidden_stdio(self):
        for key in ("stdin", "stdout"):
            t = tool()
            t["_meta"][key] = None
            self.invalid_tool([t])

    def test_tool_timeout(self):
        for value in (-1, True, False, 1.0, None):
            t = tool()
            t["_timeout_ms"] = value
            self.invalid_tool([t])
        t["_timeout_ms"] = 0
        self.assertEqual(home.read_tools([self.write("tools.json", [t])]), [t])

    def test_tool_duplicate_across_files(self):
        self.error("ToolInvalid", home.read_tools, [self.write("a.json", [tool()]), self.write("b.json", [tool()])])

    def test_strip_private_shallow(self):
        t = tool()
        t.update(_note="x", _run="legacy", extra={"_nested": 1})
        stripped = home.strip_private(t)
        self.assertEqual(set(stripped), {"type", "function", "extra"})
        self.assertIs(stripped["function"], t["function"])
        self.assertEqual(stripped["extra"], {"_nested": 1})

    def test_user_valid(self):
        home.check_message({"role": "user", "content": ""})

    def test_user_invalid(self):
        for m in ({"role": "user"}, {"role": "user", "content": None}, {"role": "user", "content": []}):
            self.invalid_message(m)

    def test_tool_message_valid(self):
        home.check_message({"role": "tool", "content": "", "tool_call_id": "c"})

    def test_tool_message_invalid(self):
        for ident in ("", None, 1):
            self.invalid_message({"role": "tool", "content": "x", "tool_call_id": ident})
        self.invalid_message({"role": "tool", "content": None, "tool_call_id": "c"})

    def test_assistant_valid(self):
        for content in ("", None):
            home.check_message({"role": "assistant", "content": content, "tool_calls": [tool_call()]})
        home.check_message({"role": "assistant", "content": "ok"})

    def test_assistant_invalid_content(self):
        for m in ({"role": "assistant"}, {"role": "assistant", "content": None},
                  {"role": "assistant", "content": 1, "tool_calls": [tool_call()]},
                  {"role": "assistant", "tool_calls": [tool_call()]}):
            self.invalid_message(m)

    def test_empty_calls_not_mutated(self):
        msg = {"role": "assistant", "content": "", "tool_calls": []}
        home.check_message(msg)
        self.assertIn("tool_calls", msg)
        msg["content"] = None
        self.invalid_message(msg)

    def test_message_object_role(self):
        for m in ([], None, {}, {"role": "system", "content": "x"}, {"role": [], "content": "x"}):
            self.invalid_message(m)

    def test_calls_array_object(self):
        for v in ({}, None, "", [None]):
            self.invalid_message({"role": "assistant", "content": "x", "tool_calls": v})

    def test_call_id(self):
        for v in (None, "", 1):
            c = tool_call()
            c["id"] = v
            self.invalid_message({"role": "assistant", "content": None, "tool_calls": [c]})
        del c["id"]
        self.invalid_message({"role": "assistant", "content": None, "tool_calls": [c]})

    def test_call_type(self):
        c = tool_call()
        c["type"] = "bad"
        self.invalid_message({"role": "assistant", "content": None, "tool_calls": [c]})

    def test_call_function(self):
        c = tool_call()
        c["function"] = []
        self.invalid_message({"role": "assistant", "content": None, "tool_calls": [c]})

    def test_call_name(self):
        for v in (None, "", 1):
            c = tool_call()
            c["function"]["name"] = v
            self.invalid_message({"role": "assistant", "content": None, "tool_calls": [c]})

    def test_call_arguments(self):
        c = tool_call()
        c["function"]["arguments"] = {}
        self.invalid_message({"role": "assistant", "content": None, "tool_calls": [c]})
        c["function"]["arguments"] = "不是 JSON 也合法"
        home.check_message({"role": "assistant", "content": None, "tool_calls": [c]})

    def test_call_duplicate_id(self):
        self.invalid_message({"role": "assistant", "content": None, "tool_calls": [tool_call(), tool_call()]})

    def test_from_model_role(self):
        self.error("MessageInvalid", home.check_message, {"role": "user", "content": "x"}, from_model=True)
        home.check_message({"role": "assistant", "content": "x"}, from_model=True)


if __name__ == "__main__":
    unittest.main()
