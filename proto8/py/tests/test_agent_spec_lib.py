"""Test the libraries of py/aos/agent_spec.py (std, defs.lib: packs copied in, other libraries prefixed, clashes SpecBad) and how tool packs are linked, statically or dynamically (--static / --dynamic, link=)."""
import json
import os
from pathlib import Path
import sys
import unittest
import unittest.mock

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agent_spec_helpers import BODY, HEAD, LIB, WithHome, agent, defs, look, resolve, run_agent  # noqa: E402


class Namespace(WithHome):
    """namespace first cut (aos-ns-cut1-1119): defs.std and defs.lib; packs copied in tool by tool; another library's tools get
    "<library>_"; two packs giving one name with different entries = SpecBad; a library root that cannot be read = SpecBad."""

    def make_lib(self, name="mylib", packs=None, tools=("read",)):
        root = Path(self.temp.name) / name
        for t in tools:
            (root / "tools" / t).mkdir(parents=True)
        (root / "packs").mkdir(parents=True)
        for pack, table in (packs or {"look": {"read": {"path": "../tools/read"}}}).items():
            (root / "packs" / (pack + ".json")).write_text(json.dumps(table if "tools" in table or "$override" in table
                                                                      else {"tools": table}))
        return root

    def tools(self, items):
        return agent(tools=items).dry_run()["tools.json"]["tools"]

    def test_two_reads_each_its_own(self):
        root = self.make_lib()
        my = defs.lib("my", str(root))
        got = self.tools([defs.std.pack("look"), my.pack("look")])
        self.assertEqual(got["read"], {"path": {"$env": "AOS_HOME", "$path": "/lib/tools/base/read"}})
        self.assertEqual(got["my_read"], {"path": str(root / "tools" / "read")})
        self.assertEqual(list(got), list(look()) + ["my_read"])
        with unittest.mock.patch.dict(os.environ, {"AOS_NS_TEST_WS": self.temp.name}):       # root as a directive: written as one
            got = self.tools([defs.lib("my", defs.env("AOS_NS_TEST_WS", "/mylib")).pack("look")])
        self.assertEqual(got, {"my_read": {"path": {"$env": "AOS_NS_TEST_WS", "$path": "/mylib/tools/read"}}})

    def test_lib_tool_and_names(self):
        my = defs.lib("my", str(self.make_lib()))
        self.assertEqual(self.tools([defs.std.tool("base/read"), my.tool("read"), my.tool("read", name="other", env={"A": "1"})]),
                         {"read": {"path": {"$env": "AOS_HOME", "$path": "/lib/tools/base/read"}},
                          "my_read": {"path": str(self.temp.name) + "/mylib/tools/read"},
                          "other": {"path": str(self.temp.name) + "/mylib/tools/read", "env": {"A": "1"}}})
        got = self.tools([my.pack("look", prefix="x-"), defs.std.pack("look", prefix="s_", exclude=["grep"], rename={"read": "cat"})])
        self.assertEqual(sorted(got), sorted(["x-read", "cat"] + ["s_" + n for n in look("read", "grep")]))

    def test_clash_is_spec_bad_and_the_ways_out(self):
        my = defs.lib("my", str(self.make_lib()))
        with self.assertRaisesRegex(defs.SpecBad, r"tool read comes from both std.pack\('look'\) and my.pack\('look'\)"):
            self.tools([defs.std.pack("look"), my.pack("look", prefix="")])
        mine = {"path": str(Path(self.temp.name) / "mylib" / "tools" / "read")}
        std_read = {"path": {"$env": "AOS_HOME", "$path": "/lib/tools/base/read"}}
        self.assertEqual(self.tools([defs.std.pack("look"), my.pack("look", prefix="", exclude=["read"])])["read"], std_read)
        self.assertEqual(self.tools([defs.std.pack("look"), my.pack("look", prefix="", rename={"read": "read2"})])["read2"], mine)
        self.assertEqual(self.tools([defs.std.pack("look"), my.pack("look", prefix=""), defs.tool("read", my.tool("read"))])["read"], mine)
        self.assertNotIn("read", self.tools([defs.std.pack("look"), my.pack("look", prefix=""), defs.drop("read")]))

    def test_same_entry_from_two_packs_is_one_tool(self):
        """a diamond: both packs point at the same tool, with the same entry -> not a clash."""
        same = self.make_lib("same", {"look": {"read": {"path": {"$env": "AOS_HOME", "$path": "/lib/tools/base/read"}}}})
        got = self.tools([defs.std.pack("look"), defs.lib("same", str(same)).pack("look", prefix="")])
        self.assertEqual(list(got), list(look()))
        other = self.make_lib("other", {"look": {"read": {"path": {"$env": "AOS_HOME", "$path": "/lib/tools/base/read"},
                                                          "env": {"A": "1"}}}})
        self.assertRaises(defs.SpecBad, self.tools, [defs.std.pack("look"), defs.lib("other", str(other)).pack("look", prefix="")])

    def test_spec_bad(self):
        my = defs.lib("my", str(self.make_lib()))
        odd = defs.lib("odd", str(self.make_lib("odd", {"base": {"$override": "x.json", "tools": {}},
                                                       "out": {"read": {"path": "../../elsewhere/read"}}})))
        cases = {"root is not a folder": ([defs.lib("my", str(Path(self.temp.name) / "nowhere")).pack("look")], "is not a folder"),
                 "root variable not set": ([defs.lib("my", defs.env("AOS_NS_TEST_UNSET", "/x")).tool("read")], "AOS_NS_TEST_UNSET is not set"),
                 "root relative": ([defs.lib("my", "mylib").pack("look")], "must be an absolute path"),
                 "library named std": ([defs.lib("std", str(self.temp.name)).pack("look")], "std comes with aos"),
                 "bad library name": ([defs.lib("My lib", "/").pack("look")], "library name must be"),
                 "no such pack": ([my.pack("net")], r"there is no .*/packs/net.json \(packs of my: look\)"),
                 "pack with $override": ([odd.pack("base")], "no \\$override"),
                 "pack path leaves the root": ([odd.pack("out")], "leaves the library root"),
                 "prefix with a dot": ([my.pack("look", prefix="my.")], "prefix must be letters"),
                 "rename an unknown tool": ([my.pack("look", rename={"cat": "x"})], "the pack has no tool cat"),
                 "exclude an unknown tool": ([defs.std.pack("look", exclude=["cat"])], "the pack has no tool cat"),
                 "rename and exclude": ([my.pack("look", rename={"read": "x"}, exclude=["read"])], "in both rename and exclude"),
                 "name too long": ([my.pack("look", prefix="p" * 64)], "must be 1-64 letters"),
                 "no such tool folder": ([defs.std.tool("base/nope")], "there is no tool folder \\$AOS_HOME/lib/tools/base/nope"),
                 "tool folder outside": ([my.tool("../read")], "relative to the library's tools folder"),
                 "defs.drop of nothing": ([defs.std.pack("look"), defs.drop("cat")], r"defs.drop\('cat'\).*no pack in tools has a tool cat"),
                 "same pack twice": ([my.pack("look"), my.pack("look")], r"my.pack\('look'\) is listed twice"),
                 "a library is not a tool": ([my], "each item of tools")}
        for why, (items, line) in cases.items():
            with self.subTest(why=why):
                self.assertRaisesRegex(defs.SpecBad, line, self.tools, items)
        self.assertRaisesRegex(defs.SpecBad, "std has one state machine", agent(fsm=defs.std.fsm("eca")).dry_run)
        with unittest.mock.patch.dict(os.environ, {}):
            os.environ.pop("AOS_HOME")
            self.assertIn("AOS_HOME is not set", defs.std.pack("look")["bad"])
            self.assertIn("AOS_HOME is not set", defs.std.tool("base/read")["bad"])

    def test_clash_through_agent_py_is_one_line_and_writes_nothing(self):
        dest = Path(self.temp.name) / "clash"
        dest.mkdir()
        (dest / "agent.py").write_text(HEAD + BODY.replace(
            "std = defs.std\n", "std = defs.std\nmy = defs.lib(\"my\", %r)\n" % str(self.make_lib())).replace(
            'std.pack("look"), ', 'std.pack("look"), my.pack("look", prefix=""), '))
        r = run_agent(dest / "agent.py", "--compile", home=self.home)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(len(r.stderr.splitlines()), 1, r.stderr)
        self.assertTrue(r.stderr.startswith("clash: error: SpecBad tool read comes from both"), r.stderr)
        self.assertEqual(os.listdir(dest), ["agent.py"])


def at_run_time(tools_json, home, folder):
    """what aos-tools makes of a tools.json when the agent runs: its $override packs, then its own table, merged field by field
    (aos.apps.tools.registry.patch itself; null = not a tool), each path made absolute from the file that wrote it."""
    from aos.apps.tools import registry
    acc = {}
    for base in tools_json.get("$override", []):
        f = resolve(base, home)
        registry.patch(acc, json.loads(Path(f).read_text())["tools"], f)
    own = {n: (dict(e, path=resolve(e["path"], home)) if e else e) for n, e in tools_json.get("tools", {}).items()}
    registry.patch(acc, own, str(Path(folder) / "tools.json"))
    out = {}
    for name, t in acc.items():
        if "null" in t:
            continue
        e = dict(t["entry"])
        p = e["path"]
        e["path"] = os.path.normpath(os.path.join(os.path.dirname(t["origin"]["path"]), resolve(p, home)))
        out[name] = e
    return out


class Linking(WithHome):
    """tool packs linked statically (copied into tools.json, the default) or dynamically ($override, read when the agent runs):
    a compile option, like gcc (user 11-19 "或者說，用選項吧，gcc那樣"; default static: "預設靜態 (Recommended)" picked). Whatever the option,
    the agent gets the same tools when it runs; what dynamic linking cannot give is SpecBad or a warning, never a silent change."""

    make_lib = Namespace.make_lib

    def compile(self, items, link="static"):
        said = []
        out = agent(tools=items)._files(None, said.append, link=link)["tools.json"]   # _files: .dry_run() with the warnings caught
        return out, said

    def same_at_run_time(self, items, link="dynamic"):
        static, _ = self.compile(items)
        dyn, said = self.compile(items, link)
        self.assertEqual(at_run_time(dyn, self.home, self.temp.name), at_run_time(static, self.home, self.temp.name))
        return dyn, said

    def test_dynamic_names_the_packs_and_gives_the_same_tools(self):
        dyn, said = self.same_at_run_time([defs.std.pack("look"), defs.std.pack("mailbox"), defs.std.pack("json")])
        self.assertEqual(dyn["$override"], [{"$env": "AOS_HOME", "$path": "/lib/packs/%s.json" % p} for p in ("look", "mailbox", "json")])
        self.assertEqual(dyn["tools"], {})
        self.assertIn("links std.pack('look'), std.pack('mailbox'), std.pack('json') dynamically", dyn["description"])
        self.assertNotIn("copied in", dyn["description"])
        self.assertEqual(said, [])
        static, _ = self.compile([defs.std.pack("look")])
        self.assertNotIn("$override", static)                                           # the default: static, as before
        self.assertEqual(agent(tools=[defs.std.pack("look")]).dry_run(link="dynamic")["tools.json"]["$override"],
                         [{"$env": "AOS_HOME", "$path": "/lib/packs/look.json"}])     # .dry_run(link=) takes it too

    def test_one_pack_can_say_how(self):
        dyn, _ = self.same_at_run_time([defs.std.pack("look", link="dynamic"), defs.std.pack("mailbox")], link="static")
        self.assertEqual(dyn["$override"], [{"$env": "AOS_HOME", "$path": "/lib/packs/look.json"}])
        self.assertIn("mailbox_send", dyn["tools"])
        self.assertIn("copied in the tools of std.pack('mailbox')", dyn["description"])
        dyn, _ = self.same_at_run_time([defs.std.pack("look", link="static"), defs.std.pack("mailbox")])
        self.assertEqual(dyn["$override"], [{"$env": "AOS_HOME", "$path": "/lib/packs/mailbox.json"}])
        self.assertIn("read", dyn["tools"])

    def test_left_out_tools_are_null(self):
        dyn, _ = self.same_at_run_time([defs.std.pack("look", exclude=["grep"]), defs.drop("glob")])
        self.assertEqual(dyn["tools"], {"grep": None, "glob": None})

    def test_replacing_a_tool_of_a_dynamic_pack(self):
        peek = defs.home("/lib/tools/base/peek_now_time")
        dyn, _ = self.same_at_run_time([defs.std.pack("look"), defs.tool("read", peek)])
        self.assertEqual(dyn["tools"], {"read": {"path": peek}})
        rich = self.make_lib("rich", {"look": {"read": {"path": "../tools/read", "env": {"A": "1"}}}})
        items = [defs.lib("rich", str(rich)).pack("look", prefix="", link="dynamic"), defs.tool("read", peek)]
        self.compile(items[:1] + [defs.tool("read", peek, env={"A": "1"})])            # every field given: the merge gives just that
        with self.assertRaisesRegex(defs.SpecBad, r"tool read: with rich.pack\('look'\) linked dynamically, aos would merge .*"
                                                  r"field by field.*link it statically"):
            self.compile(items)
        self.compile([defs.lib("rich", str(rich)).pack("look", prefix=""), defs.tool("read", peek)])   # static: replaced as a whole

    def test_renamed_tools_need_static_linking(self):
        root = self.make_lib()
        my = defs.lib("my", str(root))
        dyn, said = self.same_at_run_time([defs.std.pack("look"), my.pack("look"), defs.std.pack("json", rename={"json_get": "query"})])
        self.assertEqual(dyn["$override"], [{"$env": "AOS_HOME", "$path": "/lib/packs/look.json"}])
        self.assertEqual(sorted(dyn["tools"]), sorted(["my_read", "query"] + [n for n in json.loads(
            (LIB / "packs" / "json.json").read_text())["tools"] if n != "json_get"]))
        self.assertEqual(len(said), 2)
        self.assertIn("my.pack('look') is linked statically: its tools are renamed", said[0])
        self.assertIn("std.pack('json') is linked statically", said[1])
        with self.assertRaisesRegex(defs.SpecBad, r"my.pack\('look'\): link=\"dynamic\" cannot rename its tools"):
            self.compile([my.pack("look", link="dynamic")])
        dyn, said = self.compile([my.pack("look", prefix="", link="dynamic")])           # no prefix: the pack as it is
        self.assertEqual(dyn["$override"], [str(root / "packs" / "look.json")])
        self.assertEqual(at_run_time(dyn, self.home, self.temp.name), {"read": {"path": str(root / "tools" / "read")}})

    def test_clashes_are_still_spec_bad(self):
        my = defs.lib("my", str(self.make_lib()))
        with self.assertRaisesRegex(defs.SpecBad, r"tool read comes from both std.pack\('look'\) and my.pack\('look'\)"):
            self.compile([defs.std.pack("look"), my.pack("look", prefix="")], link="dynamic")
        dyn, _ = self.compile([defs.std.pack("look"), my.pack("look", prefix="", exclude=["read"])], link="dynamic")
        self.assertEqual(at_run_time(dyn, self.home, self.temp.name)["read"]["path"], str(self.home) + "/lib/tools/base/read")
        self.assertEqual(dyn["tools"], {"read": {"path": {"$env": "AOS_HOME", "$path": "/lib/tools/base/read"}}})  # both packs give read: written

    def test_bad_link(self):
        with self.assertRaisesRegex(defs.SpecBad, "link must be \"static\" or \"dynamic\""):
            self.compile([defs.std.pack("look", link="shared")])
        with self.assertRaisesRegex(defs.SpecBad, "link must be \"static\" or \"dynamic\""):
            self.compile([defs.std.pack("look")], link="shared")

    def test_the_options_of_agent_py(self):
        folder = Path(self.temp.name) / "w"
        folder.mkdir()
        (folder / "agent.py").write_text(HEAD + BODY)
        call = lambda *argv: run_agent(folder / "agent.py", *argv, home=self.home)  # noqa: E731
        r = call("--compile", "--dynamic")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads((folder / "tools.json").read_text())["$override"],
                         [{"$env": "AOS_HOME", "$path": "/lib/packs/look.json"}])
        self.assertNotIn("$override", json.loads(call("--dry-run", "--static").stdout)["tools.json"])
        self.assertNotIn("$override", json.loads(call("--dry-run").stdout)["tools.json"])
        self.assertIn("$override", json.loads(call("--dry-run", "--dynamic").stdout)["tools.json"])
        other = Path(self.temp.name) / "other"
        other.mkdir()
        self.assertEqual(call("--compile", "--dynamic", str(other)).returncode, 0)
        self.assertEqual(call("--compile", str(other), "--static").returncode, 0)
        self.assertNotIn("$override", json.loads((other / "tools.json").read_text()))
        r = call("--compile", "--static", "--dynamic")
        self.assertEqual((r.returncode, r.stderr.split(" (")[0]), (1, "w: error: ArgumentsBad give one of --static and --dynamic, not --static --dynamic"))
        r = call("--compile", "--shared")
        self.assertEqual(r.returncode, 1)
        self.assertIn("w: error: FlagUnknown --shared", r.stderr)
        self.assertEqual(call("--dry-run", "--dynamic", str(other)).returncode, 1)          # --dry-run takes no folder

    def test_the_tools_of_defs_load_are_linked_statically(self):
        base = Path(self.temp.name) / "base"
        base.mkdir()
        (base / "agent.py").write_text(HEAD + BODY)
        strict = Path(self.temp.name) / "strict"
        strict.mkdir()
        (strict / "agent.py").write_text(HEAD + 'base = defs.load("../base")\n'
                                         'defs.main(defs.Agent("Strict.", system=base.system, tools=[base.tools, defs.std.pack("json")], '
                                         'llm=base.llm, fsm=base.fsm))\n')
        r = run_agent(strict / "agent.py", "--dry-run", "--dynamic", home=self.home)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("strict: warning: defs.load('../base') is linked statically: it is the tools of another agent.py", r.stderr)
        tools_json = json.loads(r.stdout)["tools.json"]
        self.assertEqual(tools_json["$override"], [{"$env": "AOS_HOME", "$path": "/lib/packs/json.json"}])
        self.assertIn("peek", tools_json["tools"])
        self.assertNotIn("grep", tools_json["tools"])                                    # the base took grep out of std.pack("look")


if __name__ == "__main__":
    unittest.main()
