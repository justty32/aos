"""Test the sender of aos-agent say / chat (11-13 a2a): --from > the listed agent whose stack holds $AOS_STACK > login name; only an eca's letter carries it."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
PROTO = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(PROTO / "py"), str(PROTO / "lib"), str(PROTO / "cmd" / "aos-agent")]
from aos_agent import common, sender  # noqa: E402


class Target:
    def __init__(self, stack, defn):
        self.stack, self.row = stack, {"def": defn}


class SayFrom(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="say-from-")
        self.addCleanup(tmp.cleanup)
        self.t = Path(tmp.name)
        for n in ("eca", "fsm", "stacks/bob/tools/x", "stacks/amy"):
            (self.t / n).mkdir(parents=True)
        (self.t / "eca" / "cli.json").write_text(json.dumps({"kind": "claude"}))
        self.rows = {"bob": {"stack": str(self.t / "stacks/bob")}, "amy": {"stack": str(self.t / "stacks/amy")}}

    def who(self, opts, stack=None, user="guanyu"):
        env = {"AOS_STACK": stack} if stack else {}
        with patch.dict(os.environ, env), patch.object(sender, "table", return_value=self.rows), \
                patch.object(sender.getpass, "getuser", return_value=user):
            if not stack:
                os.environ.pop("AOS_STACK", None)
            return sender.sender(opts, "aos-agent say - x\n\nusage: aos-agent say")

    def test_precedence(self):
        self.assertEqual(self.who({"from": "carol"}, str(self.t / "stacks/bob")), "carol")
        self.assertEqual(self.who({}, str(self.t / "stacks/bob/tools/x")), "bob")      # agent 的工具下的指令＝那隻 agent
        self.assertEqual(self.who({}, str(self.t / "elsewhere")), "guanyu")            # 不在表上＝人
        self.assertEqual(self.who({}), "guanyu")
        self.assertEqual(self.who({}, user='we"ird'), "user")

    def test_bad_from(self):
        for bad in ("", 'a"b', "a\nb", "x" * 65):
            with self.assertRaises(common.Fail) as e:
                self.who({"from": bad})
            self.assertEqual(e.exception.code, "ArgumentsBad")

    def test_daemon_table_unreadable_means_person(self):
        with patch.dict(os.environ, {"AOS_STACK": str(self.t / "stacks/bob")}), \
                patch.object(sender, "table", side_effect=common.Fail("DaemonMissing", "x")), \
                patch.object(sender.getpass, "getuser", return_value="guanyu"):
            self.assertEqual(sender.sender({}, "h"), "guanyu")

    def test_only_an_eca_letter_carries_the_name(self):
        with patch.object(sender.aos_ws, "put", return_value="sig") as put:
            sender.put(Target("/s1", str(self.t / "eca")), "hi", "bob")
            sender.put(Target("/s2", str(self.t / "fsm")), "hi", "bob")
        self.assertEqual([c[0] for c in put.call_args_list], [("/s1", "hi", "bob"), ("/s2", "hi", None)])

    def test_put_writes_name_into_the_body(self):
        import aos_ws
        with patch.object(aos_ws, "post", return_value="sig") as post, patch.object(aos_ws.os.path, "isdir", return_value=True):
            aos_ws.put("/s", "hi\n", "bob")
            aos_ws.put("/s", "hi\n")
        self.assertEqual([json.loads(c[0][1]) for c in post.call_args_list],
                         [{"role": "user", "content": "hi", "name": "bob"}, {"role": "user", "content": "hi"}])


if __name__ == "__main__":
    unittest.main()
