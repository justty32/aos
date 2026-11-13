"""user_zone_guard（before_tool 的 hook handler）：參數路徑落在專區、不在 mailbox/、工具不是唯讀＝退 10 擋；mailbox/ 裡、專區外、唯讀工具、相對路徑接 $AOS_WS、~ 展開、JSON 指標、巢狀參數、捷徑都照算；壞事件退 1。"""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

PROTO = Path(__file__).resolve().parents[3]
ENTRY = PROTO / "lib" / "agent" / "user_zone_guard" / "_entry"


class Guard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(os.path.realpath(self.tmp.name))
        self.zone = root / "home" / ".aos" / "user"
        (self.zone / "mailbox" / "new").mkdir(parents=True)
        (self.zone / "done").mkdir()
        self.ws = root / "ws"
        self.ws.mkdir()
        (self.ws / "z").symlink_to(self.zone)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        self.env.update(HOME=str(root / "home"), AOS_WS=str(self.ws))

    def fire(self, name, arguments, raw=None):
        ev = raw if raw is not None else json.dumps({"event": "before_tool", "hook": "user_zone_guard", "stack": "/x",
                                                     "name": name, "id": "1", "arguments": arguments})
        return subprocess.run([str(ENTRY)], input=ev, text=True, capture_output=True, timeout=30, env=self.env)

    def assertBlocked(self, name, arguments):
        r = self.fire(name, arguments)
        self.assertEqual(r.returncode, 10, r.stdout + r.stderr)
        self.assertIn("user_zone_guard: blocked: %s would touch" % name, r.stdout)

    def assertAllowed(self, name, arguments):
        r = self.fire(name, arguments)
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))

    def test_blocks_writes_outside_mailbox(self):
        self.assertBlocked("json_set", {"path": str(self.zone / "done" / "x" / "reply.json"), "value": 1})
        self.assertBlocked("json_set", {"path": "~/.aos/user/log.jsonl"})
        self.assertBlocked("jsonx_set", {"path": "z/door.json#/mode", "value": "away"})       # 相對＋捷徑＋指標
        self.assertBlocked("json_multi_set", {"items": [{"path": "/tmp/a.json"}, {"path": str(self.zone / "config.json")}]})
        self.assertBlocked("json_set", {"path": str(self.zone)})

    def test_allows_mailbox_outside_and_reads(self):
        self.assertAllowed("mailbox_send", {"box": str(self.zone / "mailbox"), "status": "NEEDS-USER", "title": "t/x"})
        self.assertAllowed("json_set", {"path": str(self.zone / "mailbox" / "new" / "a" / "letter.json")})
        self.assertAllowed("json_set", {"path": "notes/a.json", "value": "~/.aos/user is the zone"})
        self.assertAllowed("json_get", {"path": str(self.zone / "door.json")})
        self.assertAllowed("jsonx_multi_get", {"items": [{"path": "~/.aos/user/log.jsonl"}]})
        self.assertAllowed("peek_now_time", {})
        self.assertAllowed("json_set", {"path": str(self.zone) + "-other/x.json"})

    def test_zone_from_env_and_bad_event(self):
        other = Path(self.tmp.name) / "zone2"
        other.mkdir()
        self.env["AOS_USER_ZONE"] = str(other)
        self.assertAllowed("json_set", {"path": str(self.zone / "done" / "x")})
        self.assertBlocked("json_set", {"path": str(other / "door.json")})
        r = self.fire("x", None, raw="not json")
        self.assertEqual(r.returncode, 1)
        self.assertIn("user_zone_guard: error: ArgumentsBad", r.stderr)


if __name__ == "__main__":
    unittest.main()
