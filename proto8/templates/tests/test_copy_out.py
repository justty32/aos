"""Test copy-out: the four --proto8 modes, kernel/NAME templates, env-mode symlink fallbacks, the needs line, and --relink leaving good anchors alone."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


sys.dont_write_bytecode = True
PROTO = Path(__file__).resolve().parents[2]
BIN = PROTO / "templates" / "copy-out"


def clean_env(**extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.update(extra)
    return env


class CopyOut(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="copy-out-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_copy(self, *args, **env):
        return subprocess.run([sys.executable, str(BIN)] + [str(a) for a in args], cwd=self.tmp,
                              env=clean_env(**env), capture_output=True, text=True)

    def ok(self, *args, **env):
        r = self.run_copy(*args, **env)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def json(self, *parts):
        return json.loads(self.tmp.joinpath(*parts).read_text())

    def test_default_is_env(self):
        r = self.ok("a")
        self.assertIn("paths written as env", r.stdout)
        self.assertIn("needs AOS_PROTO8 set to this machine's proto8 folder (now: unset", r.stdout)
        tools = self.json("a", "tools.json")["tools"]
        self.assertEqual(tools["agents"]["path"], {"$env": "AOS_PROTO8", "$path": "/lib/agent/agents"})
        self.assertEqual(tools["memory"]["path"], "tools/memory")
        self.assertEqual(self.json("a", "tools", "memory", "_entry"), [{"$env": "AOS_PROTO8", "$path": "/lib/agent/memory/_entry"}])
        self.assertEqual(self.json("a", "tools", "memory", "_memory.json")["base"], {"$env": "AOS_PROTO8", "$path": "/knowledge/aos"})
        self.assertFalse(os.path.lexists(self.tmp / "a" / ".aos-proto8"))
        self.assertFalse((self.tmp / "a" / ".gitignore").exists())

    def test_env_mode_needs_line_shows_current_value(self):
        r = self.ok("a", AOS_PROTO8="/some/where")
        self.assertIn("(now: /some/where;", r.stdout)

    def test_env_mode_file_symlink_becomes_copy_with_warning(self):
        r = self.ok("a")
        td = self.tmp / "a" / "tools" / "memory" / "_tooldef.json"
        self.assertFalse(td.is_symlink())
        self.assertEqual(td.read_bytes(), (PROTO / "lib" / "agent" / "memory" / "_tooldef.json").read_bytes())
        self.assertIn("tools/memory/_tooldef.json is a copy of", r.stderr)

    def test_no_machine_path_in_env_copy(self):
        self.ok("reviewer", "r")
        for p in (self.tmp / "r").rglob("*.json"):
            self.assertNotIn(str(PROTO), p.read_text(), p)

    def test_aos_cd_directive_env(self):
        self.ok("reviewer", "r")
        argv = self.json("r", "fsm.json")["states"]["think"]["exec"]["argv"]
        self.assertEqual(argv[1], {"$env": "AOS_PROTO8", "$path": "/templates/agent-fsm/brain.py"})

    def test_aos_cd_directive_anchor_keeps_aos_cd(self):
        self.ok("--proto8", "anchor", "reviewer", "r")
        argv = self.json("r", "fsm.json")["states"]["think"]["exec"]["argv"]
        self.assertEqual(argv[1], {"$env": "AOS_CD", "$path": ".aos-proto8/templates/agent-fsm/brain.py"})

    def test_anchor_mode_is_old_behaviour(self):
        r = self.ok("--proto8", "anchor", "a")
        self.assertEqual(self.json("a", "tools.json")["tools"]["agents"]["path"], ".aos-proto8/lib/agent/agents")
        self.assertEqual(os.readlink(self.tmp / "a" / ".aos-proto8"), str(PROTO))
        self.assertIn("/.aos-proto8", (self.tmp / "a" / ".gitignore").read_text())
        self.assertEqual(os.readlink(self.tmp / "a" / "tools" / "memory" / "_tooldef.json"),
                         "../../.aos-proto8/lib/agent/memory/_tooldef.json")
        self.assertIn("needs", r.stdout)

    def test_absolute_mode(self):
        self.ok("--proto8", "absolute", "a")
        self.assertEqual(self.json("a", "tools.json")["tools"]["agents"]["path"], str(PROTO / "lib" / "agent" / "agents"))
        self.assertEqual(os.readlink(self.tmp / "a" / "tools" / "memory" / "_tooldef.json"),
                         str(PROTO / "lib" / "agent" / "memory" / "_tooldef.json"))

    def test_relative_mode(self):
        self.ok("--proto8", "relative", "a")
        p = self.json("a", "tools.json")["tools"]["agents"]["path"]
        self.assertFalse(os.path.isabs(p))
        self.assertEqual(os.path.realpath(self.tmp / "a" / p), str(PROTO / "lib" / "agent" / "agents"))
        link = self.tmp / "a" / "tools" / "memory" / "_tooldef.json"
        self.assertFalse(os.path.isabs(os.readlink(link)))
        self.assertTrue(link.exists())

    def test_kernel_template(self):
        r = self.ok("kernel/llm-kernel", "llm")
        self.assertIn("copied kernel/llm-kernel", r.stdout)
        k = self.json("llm", "kernel.json")
        self.assertEqual(k["exec"], {"$env": "AOS_PROTO8", "$path": "/lib/base/llm_http"})
        self.assertEqual(k["endpoints"]["fake"]["exec"], {"$env": "AOS_PROTO8", "$path": "/lib/base/llm_fake"})
        self.assertEqual(k["endpoints"]["smart-high"]["exec"], "endpoints/litellm")   # 範本裡的照舊
        self.assertIn("/tmp/aos-demo-sender", k["budget"]["senders"])                  # key 不動

    def test_kernel_daemon_judge_argv(self):
        self.ok("--proto8", "relative", "kernel/daemon-judge", "dj")
        argv = self.json("dj", "daemon.json")["exec"]["argv"]
        self.assertEqual(os.path.realpath(self.tmp / "dj" / argv[1]), str(PROTO / "lib" / "aos" / "judge"))
        self.assertEqual(argv[2], {"$env": "AOS_CD", "$path": "judge.json"})

    def test_bad_template_and_mode(self):
        self.assertIn("TemplateMissing", self.run_copy("kernel/none", "x").stderr)
        self.assertIn("TemplateMissing", self.run_copy("kernel/../templates/agent-fsm", "x").stderr)
        r = self.run_copy("--proto8", "nope", "x")
        self.assertEqual(r.returncode, 1)
        self.assertIn("ArgumentsBad", r.stderr)
        self.assertFalse((self.tmp / "x").exists())

    def test_dest_exists(self):
        (self.tmp / "a").mkdir()
        self.assertIn("DestExists", self.run_copy("a").stderr)

    # ---- --relink ----

    def test_relink_keeps_users_relative_anchor(self):
        self.ok("--proto8", "anchor", "a")
        link = self.tmp / "a" / ".aos-proto8"
        os.remove(link)
        os.symlink(os.path.relpath(PROTO, self.tmp / "a"), link)
        before = os.readlink(link)
        r = self.ok("--relink", "a")
        self.assertEqual(os.readlink(link), before)
        self.assertIn("already 1", r.stdout)

    def test_relink_keeps_anchor_reaching_another_proto8(self):
        self.ok("--proto8", "anchor", "a")
        other = self.tmp / "other"
        (other / "templates").mkdir(parents=True)
        (other / "py").mkdir()
        (other / "templates" / "copy-out").write_text("")
        (other / "py" / "aos_flags.py").write_text("")
        link = self.tmp / "a" / ".aos-proto8"
        os.remove(link)
        os.symlink(other, link)
        self.ok("--relink", "a")
        self.assertEqual(os.readlink(link), str(other))

    def test_relink_repoints_broken_absolute_anchor(self):
        self.ok("--proto8", "anchor", "a")
        link = self.tmp / "a" / ".aos-proto8"
        os.remove(link)
        os.symlink("/nonexistent/proto8", link)
        r = self.ok("--relink", "a")
        self.assertEqual(os.readlink(link), str(PROTO))
        self.assertIn("relinked", r.stdout)


if __name__ == "__main__":
    unittest.main()
