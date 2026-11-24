"""Test 11-24 (the user's "pack檔壞掉，那我是希望就是這個pack檔內的工具不能用，其他都可以用"): a registry that "$override"s a pack that is
missing, not JSON, the wrong shape or an unresolvable directive skips only that pack (warning on stderr, a "broken pack" row in ls), the
other packs and its own tools keep working; the registry itself being broken is still RegistryBad."""
import json
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import env_helper  # noqa: E402  同夾的共用零件


sys.dont_write_bytecode = True
PROTO = Path(__file__).resolve().parents[4]
BIN = PROTO / "bin" / "aos-tools"
OK = '''#!/usr/bin/env python3
import sys
if len(sys.argv) > 1 and sys.argv[1] == "--tooldef":
    print('{"description": "Answers ok.", "parameters": {"type": "object", "properties": {}}}')
    sys.exit(0)
sys.stdin.read()
print("ok")
'''


class PackSkip(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="aos-tools-pack-skip-"))
        lib = self.tmp / "lib"
        lib.mkdir()
        for n in ("good", "mine", "lost"):
            f = lib / n
            f.write_text(OK)
            f.chmod(f.stat().st_mode | stat.S_IXUSR)
        packs = self.tmp / "packs"
        packs.mkdir()
        (packs / "good.json").write_text(json.dumps({"tools": {"good": {"path": "../lib/good"}}}))
        (packs / "bad.json").write_text('{"tools": {"lost": ')
        (packs / "shape.json").write_text(json.dumps({"tools": ["not", "an", "object"]}))
        self.reg = self.tmp / "tools.json"
        self.reg.write_text(json.dumps({"$override": ["packs/good.json", "packs/missing.json", "packs/bad.json",
                                                      "packs/shape.json", {"$env": "NO_SUCH_VAR_FOR_TEST", "$path": "/x.json"}],
                                        "tools": {"mine": {"path": "lib/mine"}}}))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_tools(self, *args):
        return subprocess.run([sys.executable, str(BIN), "--file", str(self.reg)] + list(args), cwd=self.tmp,
                              env=env_helper.clean_env(drop=("TC_", "NO_SUCH_VAR_FOR_TEST")), capture_output=True, text=True, input="{}")

    def test_only_the_broken_packs_are_left_out(self):
        r = self.run_tools("ls", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(sorted(t["name"] for t in json.loads(r.stdout)), ["good", "mine"])
        warnings = [l for l in r.stderr.splitlines() if l.startswith("aos-tools: warning: pack ")]
        self.assertEqual(len(warnings), 4, r.stderr)
        self.assertIn("packs/missing.json does not exist", r.stderr)
        self.assertIn("bad.json (from %s#/$override/2) skipped (RegistryBad" % self.reg, r.stderr)
        self.assertIn("shape.json (from %s#/$override/3) skipped (RegistryBad" % self.reg, r.stderr)
        self.assertIn("$override/4 skipped (DirectiveBad", r.stderr)
        self.assertIn("its tools are left out, the other tools work", r.stderr)
        text = self.run_tools("ls").stdout.splitlines()
        self.assertEqual([l.split("\t")[0] for l in text if not l.startswith("!")], ["good", "mine"])
        self.assertEqual(sum(1 for l in text if l.startswith("!") and "\tbroken pack: " in l), 4)
        r = self.run_tools("call", "good")
        self.assertEqual((r.returncode, r.stdout), (0, "ok\n"), r.stderr)
        r = self.run_tools("call", "lost")
        self.assertEqual(r.returncode, 1)
        self.assertIn("ToolMissing", r.stderr)

    def test_the_registry_itself_broken_is_still_an_error(self):
        self.reg.write_text('{"$override": ["packs/good.json"], "tools": ')
        r = self.run_tools("ls")
        self.assertEqual(r.returncode, 1)
        self.assertIn("RegistryBad", r.stderr)


if __name__ == "__main__":
    unittest.main()
