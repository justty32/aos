"""驗證 mcp_tool 的登記呼叫、媒體存檔、截斷、環境隔離與行程群收尾。"""
import base64
import json
import os
from pathlib import Path
import re
import signal
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ENTRY = HERE.parent / "_entry"
PROTO = HERE.parents[3]
FIXTURE = HERE / "fixtures" / "demo.json"
LINE = "mcp_tool: error: "


def clean_env(**extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_") and k != "FAKE_MODE"}
    env["PATH"] = os.path.expanduser("~/.local/bin") + os.pathsep + env.get("PATH", "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["AOS_HOME"] = str(PROTO)
    env.update(extra)
    return env


class McpToolThroughAosTools(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mcp-tool-"))
        (self.tmp / "mcp").mkdir()
        (self.tmp / "def").mkdir()
        (self.tmp / "ws").mkdir()
        pack = json.loads(FIXTURE.read_text())
        pack["mcp_server"]["args"] = [str(PROTO / "lib" / "tests" / "fake_mcp_stdio.py")]
        # 量 cwd 用的一格：aos-exec 跑包檔裡那格的 _entry 時，cwd 應是包檔的資料夾
        pack["mcp_tools"]["where"] = {"_entry": ["python3", "-c", "import os; print(os.getcwd())"], "_tooldef": {"description": "Print the cwd."}}
        pack["tools"]["demo_where"] = {"path": "demo.json#/mcp_tools/where"}
        self.pack = self.tmp / "mcp" / "demo.json"
        self.pack.write_text(json.dumps(pack))
        self.reg = self.tmp / "def" / "tools.json"
        self.reg.write_text(json.dumps({"$override": ["../mcp/demo.json"], "tools": {}}))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def tools(self, *args, stdin="", **env):
        return subprocess.run(["aos-tools", "--file", str(self.reg)] + list(args), input=stdin, text=True,
                              capture_output=True, cwd=self.tmp / "ws", env=clean_env(AOS_WS=str(self.tmp / "ws"), **env),
                              timeout=60)

    def entry(self, *args, stdin="", cwd=None, **env):
        return subprocess.run([str(ENTRY)] + list(args), input=stdin, text=True, capture_output=True,
                              cwd=cwd or self.tmp / "mcp", env=clean_env(AOS_WS=str(self.tmp / "ws"), **env), timeout=60)

    def test_pack_top_level_keys_accepted(self):
        """(1) aos-tools 讀包檔：mcp_server／mcp_import／mcp_tools 三個頂層鍵放行。"""
        r = self.tools("ls", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("error:", r.stderr)
        names = {t["name"]: t for t in json.loads(r.stdout)}
        self.assertEqual(set(names), {"demo_echo", "demo_fail", "demo_image", "demo_where"})
        self.assertEqual(names["demo_echo"]["tooldef"]["description"], "[MCP server demo] Return the supplied text.")

    def test_relative_path_and_cwd_from_pack_folder(self):
        """(2) tools 裡相對的 demo.json#/mcp_tools/x 從包檔的資料夾算；_entry 的 cwd＝包檔的資料夾。"""
        names = {t["name"]: t for t in json.loads(self.tools("ls", "--json").stdout)}
        self.assertEqual(names["demo_echo"]["path"], "%s#/mcp_tools/echo" % self.pack)
        r = self.tools("call", "demo_where", "{}")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(os.path.realpath(r.stdout.strip()), os.path.realpath(self.tmp / "mcp"))

    def test_call_echo(self):
        r = self.tools("call", "demo_echo", stdin='{"text": "hello from fake"}')
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "hello from fake\n", ""))

    def test_call_fail_is_callfailed(self):
        r = self.tools("call", "demo_fail", "{}")
        self.assertEqual(r.returncode, 1)
        line = LINE + "CallFailed the server reported an error"
        self.assertEqual(r.stdout, "the fake tool failed\n" + line + "\n")
        self.assertEqual(r.stderr.strip().splitlines()[-1], line)


    def add_tool(self, name, timeout_ms=60000):
        pack = json.loads(self.pack.read_text())
        pack["mcp_tools"][name] = {"_metainfo": {"timeout_ms": timeout_ms}}
        self.pack.write_text(json.dumps(pack))

    def call(self, name, arguments=None, **env):
        return self.entry("--pack", "demo.json", "--tool", name,
                          stdin=json.dumps(arguments or {}), **env)

    def result_server(self, result):
        """每個案例私有的標準庫 server；不更動共用 fake。"""
        script = self.tmp / "result_server.py"
        script.write_text("# Return one test-controlled MCP result.\n"
                          "import json, sys\n"
                          "result = " + repr(result) + "\n"
                          "for line in sys.stdin:\n"
                          " r = json.loads(line)\n"
                          " if 'id' not in r: continue\n"
                          " value = ({'protocolVersion':'2025-06-18', 'capabilities':{}, "
                          "'serverInfo':{'name':'test','version':'1'}} "
                          "if r['method']=='initialize' else result)\n"
                          " print(json.dumps({'jsonrpc':'2.0','id':r['id'],'result':value}), flush=True)\n")
        pack = json.loads(self.pack.read_text())
        pack["mcp_server"]["args"] = [str(script)]
        self.pack.write_text(json.dumps(pack))

    def test_image_saved_with_exact_bytes_and_unique_paths(self):
        stack = self.tmp / "stack"
        self.assertFalse(stack.exists())
        r = self.call("echo", {"text": "hello"}, AOS_STACK=str(stack))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(stack.exists(), "text results must not create the cell")
        paths = []
        for _ in range(2):
            r = self.call("image", AOS_STACK=str(stack))
            self.assertEqual(r.returncode, 0, r.stderr)
            match = re.fullmatch(r"\[image saved: (\$AOS_STACK/.*?) \(image/png, (\d+) bytes\)\]\n", r.stdout)
            self.assertIsNotNone(match, r.stdout)
            path = stack / match[1].removeprefix("$AOS_STACK/")
            paths.append(path)
            expected = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR4nGP4DwQACfsD/fteaysAAAAASUVORK5CYII=")
            self.assertEqual(path.read_bytes(), expected)
            self.assertEqual(int(match[2]), len(expected))
            self.assertNotIn(str(stack), r.stdout + r.stderr)
        self.assertNotEqual(*paths)

    def test_image_through_tools_uses_own_cell(self):
        stack = self.tmp / "parent-stack"
        stack.mkdir()
        r = self.tools("call", "demo_image", "{}", AOS_STACK=str(stack))
        self.assertEqual(r.returncode, 0, r.stderr)
        match = re.fullmatch(r"\[image saved: (\$AOS_STACK/.*?) \(image/png, (\d+) bytes\)\]\n", r.stdout)
        self.assertIsNotNone(match, r.stdout)
        saved = stack / "tools" / "demo_image" / match[1].removeprefix("$AOS_STACK/")
        self.assertTrue(saved.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual(len(saved.read_bytes()), int(match[2]))

    def test_media_needs_stack_and_write_errors(self):
        r = self.call("image")
        self.assertEqual(r.returncode, 1)
        self.assertIn(LINE + "StackMissing ", r.stdout)
        self.assertEqual(r.stdout, r.stderr)
        stack = self.tmp / "not-a-directory"
        stack.write_text("occupied")
        r = self.call("image", AOS_STACK=str(stack))
        self.assertEqual(r.returncode, 1)
        self.assertIn(LINE + "WriteFailed ", r.stdout)
        self.assertEqual(r.stdout, r.stderr)

    def test_other_content_and_structured_results(self):
        cases = [
            ({"content": [{"type": "resource_link", "uri": "https://example.test/doc"}]}, "https://example.test/doc\n"),
            ({"content": [{"type": "resource", "resource": {"uri": "test:///x", "text": "embedded text"}}]}, "embedded text\n"),
            ({"structuredContent": {"answer": 42}}, None),
            ({"content": [], "structuredContent": {"answer": 42}}, None),
            ({"content": [{"type": "future"}]}, "[future content not shown]\n"),
        ]
        for result, expected in cases:
            with self.subTest(result=result):
                self.result_server(result)
                r = self.call("echo")
                self.assertEqual(r.returncode, 0, r.stderr)
                if expected is None:
                    self.assertEqual(json.loads(r.stdout), {"answer": 42})
                    self.assertEqual(len(r.stdout.splitlines()), 1)
                else:
                    self.assertEqual(r.stdout, expected)

    def test_audio_saved_and_bad_media_rejected(self):
        data = b"RIFFtest-wave-data"
        self.result_server({"content": [{"type": "audio", "mimeType": "audio/wav", "data": base64.b64encode(data).decode()}]})
        stack = self.tmp / "stack"
        r = self.call("echo", AOS_STACK=str(stack))
        self.assertEqual(r.returncode, 0, r.stderr)
        match = re.fullmatch(r"\[audio saved: (\$AOS_STACK/.*?) \(audio/wav, (\d+) bytes\)\]\n", r.stdout)
        self.assertIsNotNone(match, r.stdout)
        self.assertEqual((stack / match[1].removeprefix("$AOS_STACK/")).read_bytes(), data)
        for content in ({"type": "image", "mimeType": "image/png", "data": "%%%"},
                        {"type": "audio", "mimeType": 123, "data": "YQ=="}):
            self.result_server({"content": [content]})
            r = self.call("echo", AOS_STACK=str(stack))
            self.assertEqual(r.returncode, 1)
            self.assertIn(LINE + "ServerBad ", r.stdout)
            self.assertEqual(r.stdout, r.stderr)

    def test_big_single_line_keeps_prefix(self):
        self.add_tool("big")
        r = self.call("big")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.splitlines()[0], "x" * (50 * 1024))
        self.assertRegex(r.stdout.splitlines()[-1], r"(?i)omitted.*bytes|bytes.*omitted")
        self.assertIn(str(150 * 1024), r.stdout.splitlines()[-1])

    def test_output_line_and_utf8_boundaries(self):
        for count in (2000, 2001):
            with self.subTest(lines=count):
                text = "\n".join(str(i) for i in range(count))
                self.result_server({"content": [{"type": "text", "text": text}]})
                r = self.call("echo")
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(r.stdout.splitlines()[:2000], text.splitlines()[:2000])
                if count == 2000:
                    self.assertEqual(r.stdout, text + "\n")
                else:
                    self.assertIn("[lines 1-2000 of 2001", r.stdout)
        self.result_server({"content": [{"type": "text", "text": "\n" * 2001}]})
        r = self.call("echo")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.startswith("\n" * 2001 + "[lines 1-2000 of 2001"), repr(r.stdout))
        for text in ("a" * (50 * 1024), "a" * (50 * 1024 - 1) + "界tail", "界" * 20000):
            with self.subTest(bytes=len(text.encode())):
                self.result_server({"content": [{"type": "text", "text": text}]})
                r = self.call("echo")
                prefix = text.encode()[:50 * 1024].decode("utf-8", "ignore")
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(r.stdout.splitlines()[0], prefix)
                self.assertNotIn("�", r.stdout)
        self.result_server({"content": [{"type": "text", "text": "first"}, {"type": "text", "text": "second\nthird"}]})
        self.assertEqual(self.call("echo").stdout, "first\nsecond\nthird\n")

    def test_env_file_is_passed_without_secret_output(self):
        secret = "mcp-private-test-value-987"
        env_file = self.tmp / "server.env"
        env_file.write_text("MCP_TEST_SECRET=" + secret + "\n")
        pack = json.loads(self.pack.read_text())
        pack["mcp_server"]["env_file"] = str(env_file)
        self.pack.write_text(json.dumps(pack))
        self.add_tool("show_env")
        r = self.call("show_env", {"names": ["MCP_TEST_SECRET", "MCP_TEST_ABSENT"]})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout), {"MCP_TEST_SECRET": True, "MCP_TEST_ABSENT": False})
        self.assertNotIn(secret, r.stdout + r.stderr)

    def owned_server(self, child=False, initializing=False):
        """私有 wrapper 記群組 PID；TERM handler 回收同群 child，避免孤兒 zombie。"""
        pidfile = self.tmp / "server.pid"
        ready = self.tmp / "calling"
        script = self.tmp / "owned_server.py"
        script.write_text("# Track and reap a test-owned MCP process group.\n"
                          "import os, signal, subprocess, sys\n"
                          "from pathlib import Path\n"
                          "sys.path.insert(0, " + repr(str(PROTO / "lib" / "tests")) + ")\n"
                          "import fake_mcp_stdio as fake\n"
                          "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)']) if " + repr(child) + " else None\n"
                          "def stop(sig, frame):\n"
                          " if child is not None:\n"
                          "  child.terminate()\n"
                          "  child.wait(timeout=3)\n"
                          " raise SystemExit(128 + sig)\n"
                          "signal.signal(signal.SIGTERM, stop)\n"
                          "Path(" + repr(str(pidfile)) + ").write_text(str(os.getpid()))\n"
                          "original = fake.call_tool\n"
                          "def call(name, arguments):\n"
                          " Path(" + repr(str(ready)) + ").write_text('ready')\n"
                          " return original(name, arguments)\n"
                          "fake.call_tool = call\n"
                          + ("Path(" + repr(str(ready)) + ").write_text('ready')\nimport time; time.sleep(120)\n" if initializing else "fake.main()\n"))
        pack = json.loads(self.pack.read_text())
        pack["mcp_server"]["args"] = [str(script)]
        self.pack.write_text(json.dumps(pack))
        return pidfile, ready

    def assert_group_gone(self, pid):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            try:
                os.killpg(pid, 0)
            except ProcessLookupError:
                return
            time.sleep(0.02)
        self.fail("test-owned server process group remains: %d" % pid)

    def cleanup_owned(self, process, pidfile):
        # 即使 communicate 或斷言失敗，也只清本案例記下的群組。
        if pidfile.exists():
            try:
                os.killpg(int(pidfile.read_text()), signal.SIGKILL)
            except ProcessLookupError:
                pass
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=5)

    def test_timeout_cleans_server_group(self):
        self.add_tool("sleep", timeout_ms=100)
        pidfile, _ = self.owned_server(child=True)
        process = subprocess.Popen([str(ENTRY), "--pack", str(self.pack), "--tool", "sleep"],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, env=clean_env(AOS_WS=str(self.tmp / "ws")))
        try:
            stdout, stderr = process.communicate('{"seconds": 120}', timeout=12)
            self.assertEqual(process.returncode, 1, stderr)
            self.assertIn(LINE + "CommandFailed ", stdout)
            self.assertEqual(stdout, stderr)
            self.assert_group_gone(int(pidfile.read_text()))
        finally:
            self.cleanup_owned(process, pidfile)

    def test_signals_clean_server_group_and_preserve_exit_status(self):
        for sig, initializing in ((signal.SIGTERM, False), (signal.SIGINT, False), (signal.SIGTERM, True)):
            with self.subTest(signal=sig, initializing=initializing):
                self.add_tool("sleep")
                pidfile, ready = self.owned_server(child=True, initializing=initializing)
                ready.unlink(missing_ok=True)
                pidfile.unlink(missing_ok=True)
                process = subprocess.Popen([str(ENTRY), "--pack", str(self.pack), "--tool", "sleep"],
                                           stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                           text=True, env=clean_env(AOS_WS=str(self.tmp / "ws")))
                try:
                    process.stdin.write('{"seconds": 120}')
                    process.stdin.close()
                    process.stdin = None
                    deadline = time.monotonic() + 5
                    while not ready.exists() and time.monotonic() < deadline and process.poll() is None:
                        time.sleep(0.02)
                    self.assertTrue(ready.exists(), "server did not reach the intended phase")
                    process.send_signal(sig)
                    stdout, stderr = process.communicate(timeout=12)
                    self.assertEqual(process.returncode, 128 + sig, (stdout, stderr))
                    self.assert_group_gone(int(pidfile.read_text()))
                finally:
                    self.cleanup_owned(process, pidfile)

    def test_server_dies(self):
        r = self.call("echo", FAKE_MODE="die")
        self.assertEqual(r.returncode, 1)
        self.assertIn(LINE + "ServerFailed ", r.stdout)
        self.assertEqual(r.stdout, r.stderr)

    def test_tool_unknown(self):
        r = self.entry("--pack", "demo.json", "--tool", "nope")
        self.assertEqual(r.returncode, 1)
        line = LINE + 'ToolUnknown demo.json has no mcp_tools entry "nope"'
        self.assertEqual((r.stdout.strip(), r.stderr.strip()), (line, line))

    def test_empty_stdin_is_empty_object(self):
        r = self.entry("--pack", "demo.json", "--tool", "echo")
        self.assertEqual((r.returncode, r.stdout), (0, "\n"), r.stderr)

    def test_bad_input(self):
        for args, stdin, code in ((["--pack", "demo.json"], "", "ArgumentsBad"),
                                  (["--pack", "demo.json", "--tool", "echo", "--x", "1"], "", "FlagUnknown"),
                                  (["--pack", "demo.json", "--tool", "echo", "extra"], "", "ArgumentsBad"),
                                  (["--pack", "demo.json", "--tool", "echo"], "not json", "ArgumentsBad"),
                                  (["--pack", "demo.json", "--tool", "echo"], "[1]", "ArgumentsBad"),
                                  (["--pack", "none.json", "--tool", "echo"], "", "PackMissing")):
            r = self.entry(*args, stdin=stdin)
            self.assertEqual(r.returncode, 1, args)
            self.assertTrue(r.stdout.startswith(LINE + code + " "), (args, r.stdout))
            self.assertEqual(r.stdout, r.stderr)

    def test_bad_timeout_is_packbad(self):
        pack = json.loads(self.pack.read_text())
        pack["mcp_tools"]["echo"]["_metainfo"]["timeout_ms"] = "soon"
        self.pack.write_text(json.dumps(pack))
        r = self.entry("--pack", "demo.json", "--tool", "echo")
        self.assertEqual(r.returncode, 1)
        self.assertIn(LINE + "PackBad ", r.stdout)

    def test_help(self):
        r = self.entry("--help")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.startswith("usage: mcp_tool --pack FILE --tool NAME"))
        self.assertIn("CallFailed", r.stdout)

    def test_not_in_any_pack(self):
        """只給包檔的 _entry 用：lib/packs 沒有一份登記它（腦不會從預設包看到它）。"""
        for f in (PROTO / "lib" / "packs").glob("*.json"):
            self.assertNotIn("mcp_tool", f.read_text(), f)


if __name__ == "__main__":
    unittest.main()
