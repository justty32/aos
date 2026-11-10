"""Test where aos-tools caches executable tool definitions (11-10 aos-tools-cli step 2): $AOS_STACK/tooldef_cache.json, never the registry."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest


sys.dont_write_bytecode = True
PROTO = Path(__file__).resolve().parents[3]
BIN = PROTO / "cmd" / "aos-tools" / "bin" / "aos-tools"
GITIGNORE = PROTO / "cmd" / "aos-agent" / "stack.gitignore"

COUNTING = """#!/usr/bin/env python3
import json, os, sys
if sys.argv[1:] == ["--tooldef"]:
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "calls"), "a") as f:
        f.write("x")
    print(json.dumps({"description": "%s"}))
    sys.exit(0)
print("ran")
"""


def clean_env(**extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
    env["PATH"] = os.path.expanduser("~/.local/bin") + os.pathsep + env.get("PATH", "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.update(extra)
    return env


class Cache(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="aos-tools-cache-"))
        self.reg = self.tmp / "def" / "tools.json"
        self.reg.parent.mkdir()
        self.stack = self.tmp / "stack"
        self.stack.mkdir()
        self.tool = self.tmp / "bin" / "count"
        self.tool.parent.mkdir()
        self.write_tool("v1")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write_tool(self, desc):
        self.tool.write_text(COUNTING % desc)
        self.tool.chmod(0o755)

    def calls(self):
        p = self.tool.parent / "calls"
        return len(p.read_text()) if p.exists() else 0

    def run_tools(self, *args, **env):
        return subprocess.run([sys.executable, str(BIN)] + [str(a) for a in args], cwd=self.tmp,
                              env=clean_env(**env), capture_output=True, text=True, stdin=subprocess.DEVNULL)

    def ok(self, *args, **env):
        r = self.run_tools(*args, **env)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r

    @property
    def cache(self):
        return self.stack / "tooldef_cache.json"

    def test_add_does_not_store_cache_in_registry(self):
        self.ok("--file", self.reg, "add", self.tool, AOS_STACK=str(self.stack))
        entry = json.loads(self.reg.read_text())["tools"]["count"]
        self.assertEqual(entry, {"path": str(self.tool)})

    def test_second_ls_uses_stack_cache(self):
        self.ok("--file", self.reg, "add", self.tool, AOS_STACK=str(self.stack))
        n = self.calls()
        self.ok("--file", self.reg, "ls", AOS_STACK=str(self.stack))
        self.ok("--file", self.reg, "ls", "--json", AOS_STACK=str(self.stack))
        self.assertEqual(self.calls(), n)
        data = json.loads(self.cache.read_text())
        self.assertEqual(list(data), [str(self.tool)])
        self.assertEqual(data[str(self.tool)]["tooldef"], {"description": "v1"})

    def test_changed_tool_reruns_and_writes_back(self):
        self.ok("--file", self.reg, "add", self.tool, AOS_STACK=str(self.stack))
        time.sleep(0.01)
        self.write_tool("v2-longer")
        n = self.calls()
        r = self.ok("--file", self.reg, "ls", "--json", AOS_STACK=str(self.stack))
        self.assertEqual(json.loads(r.stdout)[0]["tooldef"], {"description": "v2-longer"})
        self.assertEqual(self.calls(), n + 1)
        self.ok("--file", self.reg, "ls", AOS_STACK=str(self.stack))
        self.assertEqual(self.calls(), n + 1)
        self.assertEqual(json.loads(self.cache.read_text())[str(self.tool)]["tooldef"], {"description": "v2-longer"})

    def test_no_stack_no_file_and_reruns(self):
        self.ok("--file", self.reg, "add", self.tool)
        n = self.calls()
        self.ok("--file", self.reg, "ls")
        self.assertEqual(self.calls(), n + 1)
        self.ok("--file", self.reg, "ls", AOS_STACK=str(self.tmp / "missing"))
        self.assertEqual(self.calls(), n + 2)
        self.assertFalse((self.tmp / "missing").exists())
        found = [p.name for p in self.tmp.rglob("tooldef_cache.json")]
        self.assertEqual(found, [])

    def test_broken_cache_heals(self):
        self.cache.write_text("not json")
        self.ok("--file", self.reg, "add", self.tool, AOS_STACK=str(self.stack))
        self.assertIn(str(self.tool), json.loads(self.cache.read_text()))
        self.cache.write_text("[1, 2]")
        self.ok("--file", self.reg, "ls", AOS_STACK=str(self.stack))
        self.assertIn(str(self.tool), json.loads(self.cache.read_text()))

    def test_no_cache_never_touches_cache_file(self):
        self.ok("--file", self.reg, "add", "--no-cache", self.tool, AOS_STACK=str(self.stack))
        self.assertEqual(json.loads(self.reg.read_text())["tools"]["count"], {"path": str(self.tool), "cache": False})
        n = self.calls()
        self.ok("--file", self.reg, "ls", AOS_STACK=str(self.stack))
        self.ok("--file", self.reg, "ls", AOS_STACK=str(self.stack))
        self.assertEqual(self.calls(), n + 2)
        self.assertFalse(self.cache.exists())

    def test_cache_object_in_registry_is_bad(self):
        self.reg.write_text(json.dumps({"tools": {"count": {"path": str(self.tool), "cache": {"stamp": "1-1", "tooldef": {}}}}}))
        r = self.run_tools("--file", self.reg, "ls")
        self.assertEqual(r.returncode, 1)
        self.assertIn("aos-tools: error: RegistryBad", r.stderr)
        self.assertIn("cache must be false", r.stderr)

    def test_gitignore_template_blocks_cache(self):
        repo = self.tmp / "repo"
        (repo / "stacks" / "a").mkdir(parents=True)
        shutil.copyfile(GITIGNORE, repo / "stacks" / ".gitignore")
        (repo / "stacks" / "a" / "tooldef_cache.json").write_text("{}")
        (repo / "stacks" / "a" / "tools.json").write_text("{}")
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        ign = subprocess.run(["git", "-C", str(repo), "check-ignore", "-q", "stacks/a/tooldef_cache.json"])
        self.assertEqual(ign.returncode, 0)
        keep = subprocess.run(["git", "-C", str(repo), "check-ignore", "-q", "stacks/a/tools.json"])
        self.assertEqual(keep.returncode, 1)


if __name__ == "__main__":
    unittest.main()
