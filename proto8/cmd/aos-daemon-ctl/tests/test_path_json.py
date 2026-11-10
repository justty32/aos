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

    def test_absolute_paths_kept_as_written(self):
        # 11-10 晚 B01：寫成絕對路徑的格另記進 as_written（表上原樣存）；相對的照舊轉絕對、不記
        ws = os.path.join(self.tmp, "proj")
        body = os.path.join(self.agent, "body.json")
        st = os.path.join(self.tmp, "st")
        _, letter = dc.add_letter(body, ws=ws, stack=st, kept=dc.typed_kept(body, ws, st))
        spec = letter["procs_added"]["body.json"]
        self.assertEqual(spec["as_written"], {"ws": ws, "stack": os.path.join(self.tmp, "st"),
                                              "def": body, "exec": os.path.join(self.agent, "run.sh")})
        old = os.getcwd()
        os.chdir(self.tmp)
        try:
            rel = os.path.relpath(body, self.tmp)
            _, letter = dc.add_letter(rel, ws="proj", kept=dc.typed_kept(rel, "proj"))
        finally:
            os.chdir(old)
        spec = letter["procs_added"]["body.json"]
        self.assertNotIn("as_written", spec)
        self.assertEqual(spec["ws"], ws)

    def test_json_string_sent_as_is(self):
        # 「add "xxx" 就是原樣送」：--ws-json 的純字串照字面放進信；絕對的另記 as_written
        body = os.path.join(self.agent, "body.json")
        _, letter = dc.add_letter(body, ws=dc.path_json('"rel/ws"', "--ws-json"), kept=())
        spec = letter["procs_added"]["body.json"]
        self.assertEqual(spec["ws"], "rel/ws")
        self.assertNotIn("as_written", spec)
        j = dc.path_json(json.dumps(self.tmp), "--ws-json")
        _, letter = dc.add_letter(body, ws=j, kept=dc.typed_kept(ws=j))
        self.assertEqual(letter["procs_added"]["body.json"]["ws"], self.tmp)
        self.assertEqual(letter["procs_added"]["body.json"]["as_written"], {"ws": self.tmp})
        _, letter = dc.add_letter(body)                  # 程式自己組的絕對路徑不算（預設 kept 空）
        self.assertNotIn("as_written", letter["procs_added"]["body.json"])

    def test_directive_path_not_kept(self):
        d = {"$env": "AOS_TEST_PJ", "$path": "/defs/ann"}
        folder = dc.resolve_here(d, "--path-json")
        _, body = dc.add_letter(os.path.join(folder, "body.json"), name="ann", def_dir=folder, written=(d, folder))
        self.assertNotIn("as_written", body["procs_added"]["ann"])

    def test_cli_excludes(self):
        ctl = PROTO / "cmd" / "aos-daemon-ctl" / "bin" / "aos-daemon-ctl"
        r = subprocess.run([sys.executable, str(ctl), "-d", self.tmp, "add", "--ws", ".", "--ws-json", '"x"',
                            os.path.join(self.agent, "body.json")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("ArgumentsBad", r.stderr)


if __name__ == "__main__":
    unittest.main()
