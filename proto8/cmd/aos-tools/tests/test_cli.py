"""Test the aos-tools command line (11-10 aos-tools-cli step 1): --file on either side, usage line, late flags, default-file warning, success lines, ls (short by default), ls -l, call NAME ARGS_JSON, naming the tool whose directive fails."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


sys.dont_write_bytecode = True
PROTO = Path(__file__).resolve().parents[3]
BIN = PROTO / "cmd" / "aos-tools" / "bin" / "aos-tools"
TOOL = PROTO / "lib" / "base" / "peek_now_time"

ECHO = """#!/usr/bin/env python3
import json, os, sys
if sys.argv[1:] == ["--tooldef"]:
    print(json.dumps({"description": "echo stdin", "parameters": {"type": "object"}}))
    sys.exit(0)
data = sys.stdin.read()
sys.stdout.write(data)
sys.exit(int(os.environ.get("ECHO_EXIT", "0")))
"""


def clean_env(**extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
    env["PATH"] = os.path.expanduser("~/.local/bin") + os.pathsep + env.get("PATH", "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.update(extra)
    return env


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="aos-tools-cli-"))
        self.reg = self.tmp / "tools.json"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_tools(self, *args, cwd=None, stdin=None, **env):
        return subprocess.run([sys.executable, str(BIN)] + [str(a) for a in args], cwd=cwd or self.tmp,
                              env=clean_env(**env), capture_output=True, text=True,
                              input=stdin if stdin is not None else "")

    def ok(self, *args, **kw):
        r = self.run_tools(*args, **kw)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def bad(self, code, *args, **kw):
        r = self.run_tools(*args, **kw)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("aos-tools: error: %s " % code, r.stderr)
        return r

    def echo_tool(self, name="echo"):
        p = self.tmp / "bin" / name
        p.parent.mkdir(exist_ok=True)
        p.write_text(ECHO)
        p.chmod(0o755)
        return p


class Brief(Base):
    def test_default_is_name_and_first_sentence(self):
        """11-10 深夜使用者「默認是給出短板，然後用-l才是給長版」：不帶旗標＝短版；-b 拿掉。"""
        self.ok("--file", self.reg, "add", TOOL)
        self.echo_tool()
        self.ok("--file", self.reg, "add", self.tmp / "bin" / "echo")
        r = self.ok("--file", self.reg, "ls")
        self.assertEqual(r.stdout, "echo\techo stdin\npeek_now_time\tGet the current UTC time in ISO 8601, e.g. 2026-10-23T08:00:00Z.\n")

    def test_brief_flag_gone_and_long_with_json_bad(self):
        self.bad("FlagUnknown", "--file", self.reg, "ls", "-b")
        self.bad("FlagUnknown", "--file", self.reg, "ls", "--brief")
        self.bad("ArgumentsBad", "--file", self.reg, "ls", "-l", "--json")


class FileEitherSide(Base):
    def test_file_after_subcommand(self):
        self.ok("add", "--file", self.reg, TOOL)
        r = self.ok("ls", "-l", "--file", self.reg, cwd="/")
        self.assertIn("peek_now_time\tdir\t%s" % TOOL, r.stdout)

    def test_file_before_subcommand(self):
        self.ok("--file", self.reg, "add", TOOL)
        self.assertIn("peek_now_time", self.ok("--file", self.reg, "ls", cwd="/").stdout)

    def test_same_file_both_sides_ok(self):
        self.ok("--file", self.reg, "add", TOOL)
        self.ok("--file", self.reg, "ls", "--file", "./tools.json")

    def test_different_files_both_sides_bad(self):
        r = self.bad("ArgumentsBad", "--file", self.reg, "ls", "--file", self.tmp / "other.json")
        self.assertIn("different values", r.stderr)

    def test_empty_file_bad(self):
        self.bad("ArgumentsBad", "--file", "", "ls")
        self.bad("ArgumentsBad", "ls", "--file", "")


class UsageAndLateFlags(Base):
    def test_usage_line_not_cut(self):
        r = self.bad("ArgumentsBad", "add")
        self.assertIn("(XXX | --path-json JSON))", r.stderr)

    def test_flag_after_xxx(self):
        """11-10 cli-sweep Q1（使用者「1.收。」）：XXX 後的旗標也收，跟寫在前面一樣。"""
        self.ok("add", TOOL, "--name", "n")
        self.assertIn("n", json.loads(self.reg.read_text())["tools"])

    def test_flag_after_name_in_call(self):
        self.ok("add", TOOL, "--name", "x")
        self.ok("call", "x", "{}", "--file", str(self.reg))

    def test_unknown_flag_after_xxx(self):
        self.bad("FlagUnknown", "get", "x", "--nope")


class DefaultFileWarning(Base):
    def test_missing_default_warns_for_reading_commands(self):
        r = self.ok("ls")
        self.assertEqual(r.stdout, "")
        self.assertIn("aos-tools: warning: ./tools.json not found; no tools (use --file F)", r.stderr)
        for args in (("get", "x"), ("call", "x"), ("rm", "x")):
            r = self.run_tools(*args)
            self.assertIn("aos-tools: warning: ./tools.json not found", r.stderr, args)

    def test_no_warning_with_file(self):
        r = self.ok("--file", self.tmp / "none.json", "ls")
        self.assertEqual(r.stderr, "")
        r = self.ok("ls", "--file", self.tmp / "none.json")
        self.assertEqual(r.stderr, "")

    def test_no_warning_when_default_exists_or_add(self):
        r = self.ok("add", TOOL)
        self.assertNotIn("warning", r.stderr)
        self.assertEqual(self.ok("ls").stderr, "")


class SuccessLines(Base):
    def test_added_absolute(self):
        r = self.ok("--file", self.reg, "add", TOOL)
        self.assertEqual(r.stdout, "added peek_now_time -> %s (%s: %s)\n" % (TOOL, self.reg, json.dumps(str(TOOL))))

    def test_added_relative(self):
        work = self.tmp / "work"
        work.mkdir()
        rel = os.path.relpath(TOOL, work)
        r = self.ok("--file", "../tools.json", "add", rel, cwd=work)
        stored = os.path.relpath(TOOL, self.tmp)
        self.assertEqual(r.stdout, "added peek_now_time -> %s (../tools.json: %s)\n" % (TOOL, json.dumps(stored)))

    def test_added_path_json(self):
        value = {"$env": "TC_ROOT", "$path": "/lib/base/peek_now_time"}
        r = self.ok("--file", self.reg, "add", "--path-json", json.dumps(value), TC_ROOT=str(PROTO))
        self.assertEqual(r.stdout, "added peek_now_time -> %s (%s: %s)\n" % (TOOL, self.reg, json.dumps(value)))

    def test_removed_names_file(self):
        self.ok("--file", self.reg, "add", TOOL)
        r = self.ok("--file", self.reg, "rm", "peek_now_time")
        self.assertEqual(r.stdout, "removed peek_now_time (%s: key deleted)\n" % self.reg)


class LongListing(Base):
    def test_ls_long_columns_and_no_values(self):
        self.ok("--file", self.reg, "add", "--envs", "SECRET_KEY=hunter2", "--envs", "AOS_MEMORY=/kb", TOOL)
        r = self.ok("--file", self.reg, "ls", "-l")
        cols = r.stdout.rstrip("\n").split("\t")
        self.assertEqual(cols, ["peek_now_time", "dir", str(TOOL), "%s#/tools/peek_now_time" % self.reg,
                                json.dumps(str(TOOL)), "AOS_MEMORY,SECRET_KEY"])
        self.assertNotIn("hunter2", r.stdout)
        self.assertNotIn("hunter2", self.ok("--file", self.reg, "ls", "--json").stdout)

    def test_ls_long_without_env_and_directive_stored(self):
        value = {"$env": "TC_ROOT", "$path": "/lib/base/peek_now_time"}
        self.ok("--file", self.reg, "add", "--path-json", json.dumps(value), TC_ROOT=str(PROTO))
        cols = self.ok("--file", self.reg, "ls", "--long", TC_ROOT=str(PROTO)).stdout.rstrip("\n").split("\t")
        self.assertEqual(cols[4], json.dumps(value))
        self.assertEqual(cols[5], "-")

    def test_ls_long_from_override(self):
        over = self.tmp / "stack" / "tools.json"
        self.ok("--file", self.reg, "add", TOOL)
        self.ok("--file", over, "override", self.reg)
        self.ok("--file", over, "add", "-n", "wc2", TOOL)
        lines = self.ok("--file", over, "ls", "-l").stdout.splitlines()
        self.assertEqual(lines[0].split("\t")[3], "%s#/tools/peek_now_time" % self.reg)
        self.assertEqual(lines[1].split("\t")[3], "%s#/tools/wc2" % over)

    def test_ls_long_and_json_bad(self):
        self.bad("ArgumentsBad", "--file", self.reg, "ls", "-l", "-j")


class CallInline(Base):
    def test_inline_equals_stdin(self):
        tool = self.echo_tool()
        self.ok("--file", self.reg, "add", tool)
        inline = self.ok("--file", self.reg, "call", "echo", '{"who": "bob"}')
        piped = self.ok("--file", self.reg, "call", "echo", stdin='{"who": "bob"}')
        self.assertEqual(inline.stdout, '{"who": "bob"}')
        self.assertEqual(inline.stdout, piped.stdout)

    def test_inline_not_checked_and_exit_code_passed(self):
        tool = self.echo_tool()
        self.ok("--file", self.reg, "add", tool)
        r = self.run_tools("--file", self.reg, "call", "echo", "not json", ECHO_EXIT="7")
        self.assertEqual(r.returncode, 7)
        self.assertEqual(r.stdout, "not json")
        self.assertNotIn("aos-tools: error:", r.stderr)

    def test_negative_number_is_args(self):
        tool = self.echo_tool()
        self.ok("--file", self.reg, "add", tool)
        self.assertEqual(self.ok("--file", self.reg, "call", "echo", "-1").stdout, "-1")

    def test_too_many_args(self):
        self.bad("ArgumentsBad", "--file", self.reg, "call", "a", "{}", "x")


class DirectiveBlame(Base):
    def test_names_the_tool(self):
        self.reg.write_text(json.dumps({"tools": {
            "good": {"path": str(TOOL)},
            "far3": {"path": {"$env": "TC_UNSET_ROOT", "$path": "/x"}}}}))
        r = self.bad("DirectiveBad", "--file", self.reg, "ls")
        self.assertIn("tool far3 (%s#/tools/far3)" % self.reg, r.stderr)


if __name__ == "__main__":
    unittest.main()
