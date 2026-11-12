"""Test lib/mcp_freeze.py: registry names, $ref expansion and $-key removal, description truncation, _metainfo hints, and diff lines."""
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mcp_freeze as mf  # noqa: E402
from tool_io import Error  # noqa: E402

# Copy of the fake stdio server's tool list (fake_mcp_stdio.py), kept here so the two steps do not wait on each other.
OBJ = {"type": "object", "properties": {}}
FAKE_TOOLS = [
    {"name": "echo", "description": "Echo the text back.",
     "inputSchema": {"type": "object", "properties": {"text": {"type": "string", "description": "Text to echo."}},
                     "required": ["text"]},
     "annotations": {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False}},
    {"name": "fail", "description": "Always report an error.", "inputSchema": OBJ},
    {"name": "image", "description": "Return a small png.", "inputSchema": OBJ, "annotations": {"readOnlyHint": True}},
    {"name": "sleep", "description": "Sleep some seconds.",
     "inputSchema": {"type": "object", "properties": {"seconds": {"type": "number"}}}},
    {"name": "big", "description": "Return 200KB of text.", "inputSchema": OBJ},
    {"name": "refschema", "description": "Schema with $ref and $defs.",
     "inputSchema": {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object",
                     "properties": {"point": {"$ref": "#/$defs/point"}},
                     "$defs": {"point": {"$id": "p", "type": "object",
                                         "properties": {"x": {"type": "number"}, "y": {"type": "number"}}}}}},
    {"name": "show_env", "description": "Say whether a variable is set (never its value).",
     "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}}},
     "annotations": {"openWorldHint": True}},
]
TOOLS = {t["name"]: t for t in FAKE_TOOLS}


def dollar_keys(node):
    if isinstance(node, dict):
        return [k for k in node if k.startswith("$")] + [k for v in node.values() for k in dollar_keys(v)]
    if isinstance(node, list):
        return [k for v in node for k in dollar_keys(v)]
    return []


class Warnings(list):
    def __call__(self, sentence):
        self.append(sentence)


class RegistryNameTest(unittest.TestCase):
    def bad(self, server, tool):
        with self.assertRaises(Error) as e:
            mf.registry_name(server, tool)
        self.assertEqual(e.exception.code, "NameBad")

    def test_rules(self):
        self.assertEqual(mf.registry_name("time", "get_current_time"), "time_get_current_time")
        self.assertEqual(mf.registry_name("gh", "ListIssues"), "gh_listissues")
        self.assertEqual(mf.registry_name("gh", "list-issues"), "gh_list_issues")
        self.assertEqual(mf.registry_name("fs", "dir.read"), "fs_dir_read")
        self.assertEqual(mf.registry_name("fs", "a/b~c"), "fs_a_b_c")
        self.assertEqual(mf.registry_name("fs", "a__b"), "fs_a_b")
        self.assertEqual(mf.registry_name("fs", "_x--y_"), "fs_x_y_")

    def test_too_long(self):
        self.assertEqual(len(mf.registry_name("s", "x" * 62)), 64)
        self.bad("s", "x" * 63)

    def test_bad_server_or_tool(self):
        for server in ("Time", "1time", "a-b", "", "aos", "x" * 33, None):
            self.bad(server, "echo")
        for tool in ("", None, 3):
            self.bad("time", tool)


class CleanSchemaTest(unittest.TestCase):
    def test_ref_expanded_and_dollar_keys_gone(self):
        w = Warnings()
        out = mf.clean_schema(TOOLS["refschema"]["inputSchema"], w)
        self.assertEqual(out, {"type": "object", "properties": {"point": {
            "type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}}}}})
        self.assertEqual(w, [])
        self.assertEqual(dollar_keys(out), [])

    def test_ref_siblings_kept_and_nested_dollar_keys_removed(self):
        schema = {"type": "object", "properties": {
            "a": {"$ref": "#/definitions/n", "description": "the a"},
            "b": {"type": "array", "items": [{"$comment": "c", "type": "string"}]}},
            "definitions": {"n": {"type": "integer", "description": "a number"}}}
        out = mf.clean_schema(schema, Warnings())
        self.assertEqual(out["properties"]["a"], {"type": "integer", "description": "the a"})
        self.assertEqual(out["properties"]["b"]["items"], [{"type": "string"}])
        self.assertEqual(dollar_keys(out), [])

    def test_cycle_stops(self):
        schema = {"type": "object", "properties": {"node": {"$ref": "#/$defs/node"}},
                  "$defs": {"node": {"type": "object", "properties": {"next": {"$ref": "#/$defs/node"}}}}}
        w = Warnings()
        out = mf.clean_schema(schema, w)
        self.assertEqual(out["properties"]["node"]["properties"]["next"], {})
        self.assertTrue(any("cycle" in s for s in w), w)
        self.assertEqual(dollar_keys(out), [])

    def test_depth_limit(self):
        defs = {"d%d" % i: {"type": "object", "properties": {"n": {"$ref": "#/$defs/d%d" % (i + 1)}}} for i in range(12)}
        defs["d12"] = {"type": "string"}
        w = Warnings()
        out = mf.clean_schema({"type": "object", "properties": {"n": {"$ref": "#/$defs/d0"}}, "$defs": defs}, w)
        node, depth = out, 0
        while node.get("properties"):
            node, depth = node["properties"]["n"], depth + 1
        self.assertEqual(node, {})
        self.assertEqual(depth, 11)
        self.assertTrue(any("deeper" in s for s in w), w)

    def test_unresolvable_becomes_empty_with_warning(self):
        schema = {"type": "object", "properties": {
            "a": {"$ref": "#/$defs/missing"}, "b": {"$ref": "https://example.com/s.json"}, "c": {"$ref": 5}}}
        w = Warnings()
        out = mf.clean_schema(schema, w)
        self.assertEqual(out["properties"], {"a": {}, "b": {}, "c": {}})
        self.assertEqual(len(w), 3)

    def test_pointer_escapes(self):
        schema = {"type": "object", "properties": {"a": {"$ref": "#/$defs/x~1y~0z"}},
                  "$defs": {"x/y~z": {"type": "boolean"}}}
        self.assertEqual(mf.clean_schema(schema, Warnings())["properties"]["a"], {"type": "boolean"})

    def test_top_level_not_object_wrapped(self):
        for schema in (None, [], "x", {"type": "string"}, {"$ref": "#/$defs/s", "$defs": {"s": {"type": "array"}}}):
            w = Warnings()
            self.assertEqual(mf.clean_schema(schema, w), {"type": "object", "properties": {}})
            self.assertEqual(len(w), 1, schema)

    def test_missing_type_becomes_object(self):
        w = Warnings()
        out = mf.clean_schema({"properties": {"a": {"type": "string"}}}, w)
        self.assertEqual(out, {"properties": {"a": {"type": "string"}}, "type": "object"})
        self.assertEqual(w, [])

    def test_param_description_truncated(self):
        schema = {"type": "object", "properties": {"a": {"type": "string", "description": "d" * 500}}}
        out = mf.clean_schema(schema, Warnings())
        self.assertEqual(out["properties"]["a"]["description"], "d" * 300)
        self.assertEqual(len(schema["properties"]["a"]["description"]), 500)


class FreezeToolTest(unittest.TestCase):
    def test_shape(self):
        reg, cell = mf.freeze_tool("fake", "fake.json", TOOLS["echo"], "stdio")
        self.assertEqual(reg, "fake_echo")
        self.assertEqual(cell["_entry"], ["python3", {"$env": "AOS_HOME", "$path": "/lib/base/mcp_tool/_entry"},
                                          "--pack", "fake.json", "--tool", "echo"])
        self.assertEqual(cell["_tooldef"]["description"], "[MCP server fake] Echo the text back.")
        self.assertEqual(cell["_tooldef"]["parameters"], TOOLS["echo"]["inputSchema"])
        self.assertEqual(cell["_metainfo"], {"summary": "echo on the MCP server fake", "side_effect": False,
                                             "idempotent": True, "resource": [], "timeout_ms": 60000})

    def test_every_fake_tool_has_no_dollar_keys_outside_entry(self):
        for tool in FAKE_TOOLS:
            reg, cell = mf.freeze_tool("fake", "fake.json", tool, "stdio")
            self.assertEqual(dollar_keys(cell["_tooldef"]) + dollar_keys(cell["_metainfo"]), [], tool["name"])
            self.assertEqual(cell["_tooldef"]["parameters"]["type"], "object")

    def test_metainfo_hints(self):
        meta = {n: mf.freeze_tool("fake", "fake.json", TOOLS[n], "stdio")[1]["_metainfo"] for n in TOOLS}
        self.assertTrue(meta["fail"]["side_effect"])
        self.assertNotIn("idempotent", meta["fail"])
        self.assertEqual(meta["fail"]["resource"], [])
        self.assertFalse(meta["image"]["side_effect"])
        self.assertEqual(meta["show_env"]["resource"], ["net"])
        tool = {"name": "w", "inputSchema": OBJ, "annotations": {"readOnlyHint": False, "idempotentHint": False}}
        m = mf.freeze_tool("fake", "fake.json", tool, "stdio")[1]["_metainfo"]
        self.assertTrue(m["side_effect"])
        self.assertIs(m["idempotent"], False)

    def test_http_means_net(self):
        m = mf.freeze_tool("site", "site.json", TOOLS["echo"], "http")[1]["_metainfo"]
        self.assertEqual(m["resource"], ["net"])

    def test_description_truncated_and_missing(self):
        tool = {"name": "long", "description": "x" * 2000, "inputSchema": OBJ}
        d = mf.freeze_tool("fake", "fake.json", tool, "stdio")[1]["_tooldef"]["description"]
        self.assertEqual(len(d), 1024)
        self.assertTrue(d.startswith("[MCP server fake] xxx"))
        d = mf.freeze_tool("fake", "fake.json", {"name": "n", "inputSchema": OBJ}, "stdio")[1]["_tooldef"]["description"]
        self.assertEqual(d, "[MCP server fake] ")

    def test_original_name_kept_and_warn_prefixed(self):
        w = Warnings()
        tool = {"name": "Dir.Read/x", "inputSchema": {"type": "string"}}
        reg, cell = mf.freeze_tool("fs", "fs.json", tool, "stdio", w)
        self.assertEqual(reg, "fs_dir_read_x")
        self.assertEqual(cell["_entry"][-1], "Dir.Read/x")
        self.assertEqual(len(w), 1)
        self.assertTrue(w[0].startswith("Dir.Read/x: "), w)

    def test_bad_name(self):
        with self.assertRaises(Error) as e:
            mf.freeze_tool("fake", "fake.json", {"inputSchema": OBJ}, "stdio")
        self.assertEqual(e.exception.code, "NameBad")


class DiffToolsTest(unittest.TestCase):
    def freeze(self, tools):
        return {t["name"]: mf.freeze_tool("fake", "fake.json", t, "stdio")[1] for t in tools}

    def test_no_changes(self):
        self.assertEqual(mf.diff_tools(self.freeze(FAKE_TOOLS), self.freeze(FAKE_TOOLS)), [])

    def test_added_removed_changed(self):
        old = self.freeze([TOOLS["echo"], TOOLS["fail"], TOOLS["sleep"]])
        echo = dict(TOOLS["echo"], description="Echo it.")
        sleep = dict(TOOLS["sleep"], inputSchema={"type": "object", "properties": {"ms": {"type": "integer"}}})
        new = self.freeze([echo, sleep, TOOLS["big"]])
        self.assertEqual(mf.diff_tools(old, new), [
            "+ big",
            "~ echo: description changed",
            "    before: [MCP server fake] Echo the text back.",
            "    after:  [MCP server fake] Echo it.",
            "- fail",
            "~ sleep: parameters changed",
            '    before: {"properties": {"seconds": {"type": "number"}}, "type": "object"}',
            '    after:  {"properties": {"ms": {"type": "integer"}}, "type": "object"}'])


if __name__ == "__main__":
    unittest.main()
