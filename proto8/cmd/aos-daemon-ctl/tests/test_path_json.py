"""test_path_json - add 的 --ws-json／--stack-json／--path-json：指示詞原樣進信（表上記原形、每次起再解；11-10 B01）。"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROTO = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(PROTO / "py"), str(PROTO / "lib")]
import daemon_ctl as dc  # noqa: E402


class PathJson(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="path-json-")
        self.agent = os.path.join(self.tmp, "proj", "defs", "ann")
        os.makedirs(self.agent)
        Path(self.agent, "body.json").write_text('{"exec": "run.sh", "interval_ms": 0}\n')
        os.environ["AOS_TEST_PJ"] = os.path.join(self.tmp, "proj")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)
        os.environ.pop("AOS_TEST_PJ", None)

    def test_parse(self):
        self.assertEqual(dc.path_json('"a/b"', "--ws-json"), "a/b")
        d = {"$env": "X", "$path": "/s"}
        self.assertEqual(dc.path_json(json.dumps(d), "--ws-json"), d)
        for bad in ("x", "{}", "[]", "1", '{"a": 1}', '""'):
            with self.assertRaises(dc.Fail) as cm:
                dc.path_json(bad, "--ws-json")
            self.assertEqual(cm.exception.code, "ArgumentsBad")

    def test_ws_directive_kept(self):
        d = {"$env": "AOS_TEST_PJ"}
        _, body = dc.add_letter(os.path.join(self.agent, "body.json"), ws=d)
        self.assertEqual(body["procs_added"]["body.json"]["ws"], d)

    def test_ws_directive_must_resolve_to_folder(self):
        with self.assertRaises(dc.Fail) as cm:
            dc.add_letter(os.path.join(self.agent, "body.json"), ws={"$env": "AOS_TEST_PJ", "$path": "/nope"})
        self.assertEqual(cm.exception.code, "PathMissing")

    def test_path_directive_rewrites_exec_and_def(self):
        d = {"$env": "AOS_TEST_PJ", "$path": "/defs/ann"}
        folder = dc.resolve_here(d, "--path-json")
        _, body = dc.add_letter(os.path.join(folder, "body.json"), name="ann", def_dir=folder, written=(d, folder))
        spec = body["procs_added"]["ann"]
        self.assertEqual(spec["def"], d)
        self.assertEqual(spec["exec"], {"$env": "AOS_TEST_PJ", "$path": "/defs/ann/run.sh"})
        self.assertNotIn(self.tmp, json.dumps(spec))          # no machine path in the letter

    def test_path_directive_only_env(self):
        with self.assertRaises(dc.Fail) as cm:
            dc.add_letter(os.path.join(self.agent, "body.json"), written=({"$ref": "x.json"}, self.agent))
        self.assertEqual(cm.exception.code, "ArgumentsBad")

    def test_cli_excludes(self):
        ctl = PROTO / "cmd" / "aos-daemon-ctl" / "bin" / "aos-daemon-ctl"
        r = subprocess.run([sys.executable, str(ctl), "-d", self.tmp, "add", "--ws", ".", "--ws-json", '"x"',
                            os.path.join(self.agent, "body.json")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("ArgumentsBad", r.stderr)


if __name__ == "__main__":
    unittest.main()
