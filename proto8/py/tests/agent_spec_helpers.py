"""Shared helpers of the test_agent_spec*.py tests: the agent.py head and example bodies, a fake AOS_HOME, running an agent.py, snapshots."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
import unittest.mock

sys.dont_write_bytecode = True
LIB = Path(__file__).resolve().parents[1]
PROTO = LIB.parent
SKEL = PROTO / "templates" / "agent-python"
sys.path.insert(0, str(LIB))
from aos.py.agent import defs  # noqa: E402 （跟寫 agent.py 的人同一個名字；＝aos.agent_spec）

HEAD = "import sys\nsys.path.insert(0, %r)\nfrom aos.py.agent import defs\n" % str(LIB)
BODY = '''\
std = defs.std
agent = defs.Agent(
    "Answer questions about the weather.",
    system="You answer questions about the weather.\\n",
    tools=[std.pack("look"), defs.tool("peek", defs.home("/lib/tools/base/peek_now_time")), defs.drop("grep")],
    llm={"model": "luna"},
    fsm=std.fsm(),
)
defs.main(agent)
'''
GENERATED = ["_entry", "_metainfo.json", "body.json", "fsm.json", "interfaces.json", "llm.json", "loop.json", "system.txt", "tools.json"]
SKEL_GENERATED = sorted(GENERATED + ["hookeds.json"])   # the skeleton declares hooks={} (user 11-19 "骨架帶一行空的 HOOKS")
TEMPLATES = PROTO / "templates"
# an eca definition copied from its template: agent.py has no fsm and fills only the content files
ECA = '''\
agent = defs.Agent(
    %(summary)r,
    meta={"cost": {"time_ms": 60000}, "resource": ["llm"]},
    system="You are the docs team's writer.\\n",
    tools=[defs.std.pack(p) for p in ("gadgets", "self", "mailbox", "json", "index")]
          + [defs.drop(n) for n in ("do_task", "self_llm", "self_system", "self_history", "self_ctl")],   # as the eca templates (11-21; events, def, jsonx dropped 11-22)
    llm=%(llm)r,
    hooks=defs.std.hooks(%(template)r),
)
defs.main(agent)
'''


def agent(description="D.", **kw):
    """defs.Agent with the fields a test leaves out filled in: system "", no tools, llm {}, fsm std.fsm()."""
    for key, value in (("system", ""), ("tools", []), ("llm", {})):
        kw.setdefault(key, value)
    if "fsm" not in kw:
        kw["fsm"] = defs.std.fsm()
    return defs.Agent(description, **kw)


def snapshot(folder):
    return {p.name: p.read_bytes() for p in sorted(Path(folder).iterdir()) if p.is_file()}


def tree(folder):
    """every file under folder (relative path -> bytes)."""
    return {str(p.relative_to(folder)): p.read_bytes() for p in sorted(Path(folder).rglob("*")) if p.is_file()}


def plain(value):
    """a definition file without its top-level description (the compiled sentences differ from the hand-written ones)."""
    return {k: v for k, v in value.items() if k != "description"} if isinstance(value, dict) else value


def as_text(value):
    """a value of .dry_run() as .compile() writes it."""
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def fake_home(tmp):
    """AOS_HOME for tests: lib = the py/ source (aos/, packs/), templates = the repo's templates."""
    home = Path(tmp) / "home"
    home.mkdir()
    (home / "lib").symlink_to(LIB)
    (home / "templates").symlink_to(TEMPLATES)
    return home


def env_with(home):
    env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
    if home:
        env["AOS_HOME"] = str(home)
    return env


def run_agent(script, *argv, home=None):
    return subprocess.run([sys.executable, str(script), *argv], text=True, capture_output=True, timeout=30, env=env_with(home))


def resolve(value, home):
    """a {"$env": "AOS_HOME", "$path": ...} directive (or a plain path) -> the path on this machine."""
    return str(home) + value["$path"] if isinstance(value, dict) else value


def borrowed(tools_json, home):
    """the tools a hand-written tools.json gives after aos-tools stacks its $override packs (field by field, null = not a tool);
    the compiled tools.json must give the same table without $override."""
    acc = {}
    for base in tools_json.get("$override", []):
        for name, entry in json.loads(Path(resolve(base, home)).read_text())["tools"].items():
            acc[name] = entry
    for name, entry in tools_json.get("tools", {}).items():
        acc[name] = entry if entry is None or name not in acc or acc[name] is None else dict(acc[name], **entry)
    return {n: e for n, e in acc.items() if e is not None}


def look(*drop):
    """the tools of std.pack("look"), as agent.py copies them in."""
    tools = json.loads((LIB / "packs" / "look.json").read_text())["tools"]
    return {n: e for n, e in tools.items() if n not in drop}


class WithHome(unittest.TestCase):
    """AOS_HOME = a fake home (lib = py/, templates = the repo's), as std.pack / std.tool / std.hooks read it when agent.py runs."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="agent-spec-")
        self.addCleanup(self.temp.cleanup)
        self.home = fake_home(self.temp.name)
        patch = unittest.mock.patch.dict(os.environ, {"AOS_HOME": str(self.home)})
        patch.start()
        self.addCleanup(patch.stop)

    def folder(self, name):
        d = Path(self.temp.name) / name
        d.mkdir(parents=True)
        return d
