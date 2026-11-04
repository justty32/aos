"""test_pi_tools - 仿 pi coding agent 的 read、write、edit、bash（原 demo/pi-tools，10-24 遷移進 proto8/lib/base）。

工具一支一支用 aos-exec 叫（arguments 從 stdin 進、stdout 是結果）。掛上它們的 demo/agent-pip 與那兩案 11-04 隨 demo 刪了。
不連真模型。設計：proto8/thinking/2026-10-24-pi-tools.md。"""
import json, os, re, signal, subprocess, tempfile, time, unittest
from pathlib import Path
import own_error  # noqa: E402
own_error.install()

from aos_bins import ROOT, tool, path_with  # noqa: E402

EXEC = tool("aos-exec")
TOOLS = ROOT / "lib" / "base"                       # 10-24 遷移前是 demo/pi-tools
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_BRAIN_URL", "AOS_BRAIN_MODEL", "AOS_BRAIN_KEY")
CODES = ("ArgumentsBad", "WsMissing", "PathBad", "FileMissing", "FileBad", "ReadFailed", "WriteFailed",
         "MkdirFailed", "TextMissing", "TextBad", "CommandFailed", "LaunchFailed")


def env_with(extra=None):
    e = {k: v for k, v in os.environ.items() if k not in CLEAR}
    e["PATH"] = path_with(e.get("PATH", ""))
    e.update(extra or {})
    return e


class Tools(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = Path(self._t.name)
        self.addCleanup(self._t.cleanup)
        self.ws = self.tmp / "ws"
        self.ws.mkdir()

    def tool(self, name, args, timeout=30):
        """叫 lib/base/<名>；回 (結束碼, stdout, 錯誤代號或 None)。錯誤時 stderr 那行與 stdout 最後一行要一樣、格式對。"""
        stdin = args if isinstance(args, str) else json.dumps(args)
        r = subprocess.run([EXEC, str(TOOLS / name)], input=stdin, capture_output=True, text=True, timeout=timeout,
                           env=env_with({"AOS_WS": str(self.ws), "AOS_STACK": str(self.tmp / "stack") + "/"}))
        mine = [l for l in r.stderr.splitlines() if l.startswith(name + ": ")]
        if r.returncode == 0:
            self.assertEqual(mine, [], r.stderr)
            return 0, r.stdout, None
        self.assertEqual(len(mine), 1, r.stderr)
        m = re.match(r"%s: ([A-Z][A-Za-z]+) \S" % name, mine[0])
        self.assertTrue(m and m.group(1) in CODES, mine[0])
        self.assertEqual(r.stdout.rstrip("\n").splitlines()[-1], mine[0])     # 給腦看的也有同一行
        return r.returncode, r.stdout, m.group(1)

    def put(self, rel, text):
        p = self.ws / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        return p

    # ---- read
    def test_read(self):
        self.put("a.py", "one\ntwo\nthree\n")
        self.assertEqual(self.tool("read", {"path": "a.py"}), (0, "one\ntwo\nthree\n", None))
        code, out, _ = self.tool("read", {"path": "a.py", "offset": 2, "max_lines": 1})
        self.assertEqual(out, "two\n\n[檔案還有 1 行。用 offset=3 接著讀。]\n")
        self.assertEqual(self.tool("read", {"path": "a.py", "offset": 9})[2], "ArgumentsBad")
        self.assertEqual(self.tool("read", {"path": "a.py", "offset": 0})[2], "ArgumentsBad")

    def test_read_truncates_and_says_where_to_continue(self):
        self.put("big.txt", "".join("%d\n" % i for i in range(1, 3001)))
        _, out, _ = self.tool("read", {"path": "big.txt"})
        lines = out.splitlines()
        self.assertEqual((lines[0], lines[1999]), ("1", "2000"))
        self.assertEqual(lines[-1], "[第 1-2000 行，共 3000 行。用 offset=2001 接著讀。]")
        _, out, _ = self.tool("read", {"path": "big.txt", "offset": 2001})
        self.assertEqual(out.splitlines()[-1], "3000")
        self.put("wide.txt", ("x" * 1000 + "\n") * 100)          # 100KB：被 50KB 截
        _, out, _ = self.tool("read", {"path": "wide.txt"})
        self.assertIn("用 offset=", out)
        self.assertLess(len(out.encode()), 52 * 1024)
        self.put("one.txt", "y" * 60000)                          # 第一行就超過 50KB
        self.assertEqual(self.tool("read", {"path": "one.txt"})[2], "FileBad")

    def test_read_errors(self):
        self.assertEqual(self.tool("read", {"path": "nope"})[2], "FileMissing")
        (self.ws / "d").mkdir()
        self.assertEqual(self.tool("read", {"path": "d"})[2], "FileBad")
        self.assertEqual(self.tool("read", "{bad")[2], "ArgumentsBad")
        self.assertEqual(self.tool("read", {})[2], "ArgumentsBad")
        (self.ws / "bin").write_bytes(b"\x7fELF\0\0")
        self.assertEqual(self.tool("read", {"path": "bin"})[2], "FileBad")

    def test_path_escape_blocked(self):
        """跑出工作資料夾：../、絕對路徑、指到外面的符號連結，四支（bash 除外）都擋。"""
        (self.tmp / "secret.txt").write_text("secret\n")
        (self.ws / "link").symlink_to(self.tmp / "secret.txt")
        (self.ws / "dirlink").symlink_to(self.tmp)
        for p in ("../secret.txt", str(self.tmp / "secret.txt"), "link", "dirlink/secret.txt", "a/../../secret.txt"):
            with self.subTest(p=p):
                code, out, err = self.tool("read", {"path": p})
                self.assertEqual((code, err), (1, "PathBad"))
                self.assertNotIn("secret\n", out)
                self.assertEqual(self.tool("write", {"path": p, "content": "x"})[2], "PathBad")
                self.assertEqual(self.tool("edit", {"path": p, "edits": [{"old_text": "secret", "new_text": "x"}]})[2],
                                 "PathBad")
        self.assertEqual((self.tmp / "secret.txt").read_text(), "secret\n")
        self.assertEqual(self.tool("write", {"path": ".", "content": "x"})[2], "PathBad")
        self.put("in.txt", "ok\n")                                 # 裡面的絕對路徑可以
        self.assertEqual(self.tool("read", {"path": str(self.ws / "in.txt")})[1], "ok\n")

    def test_ws_missing(self):
        r = subprocess.run([str(TOOLS / "read" / "_entry")], input='{"path": "a"}', capture_output=True, text=True,
                           env=env_with())
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stderr.startswith("read: WsMissing "), r.stderr)

    # ---- write
    def test_write(self):
        code, out, _ = self.tool("write", {"path": "src/pkg/a.py", "content": "print(1)\n"})
        self.assertEqual((code, out), (0, "已寫入 src/pkg/a.py（9 bytes）\n"))
        self.assertEqual((self.ws / "src/pkg/a.py").read_text(), "print(1)\n")
        p = self.put("run.sh", "old")
        p.chmod(0o755)
        self.tool("write", {"path": "run.sh", "content": "#!/bin/sh\n"})
        self.assertEqual((p.read_text(), p.stat().st_mode & 0o777), ("#!/bin/sh\n", 0o755))
        self.assertEqual(sorted(os.listdir(self.ws)), ["run.sh", "src"])      # 暫存檔沒留下
        self.assertEqual(self.tool("write", {"path": "x"})[2], "ArgumentsBad")
        (self.ws / "d").mkdir()
        self.assertEqual(self.tool("write", {"path": "d", "content": ""})[2], "FileBad")

    # ---- edit
    def test_edit(self):
        p = self.put("a.py", "def f():\n    return 1\n\ndef g():\n    return 2\n")
        code, out, _ = self.tool("edit", {"path": "a.py", "edits": [
            {"old_text": "return 2", "new_text": "return 20"}, {"old_text": "return 1", "new_text": "return 10"}]})
        self.assertEqual((code, out), (0, "已在 a.py 換掉 2 處（第一處在第 2 行）\n"))
        self.assertEqual(p.read_text(), "def f():\n    return 10\n\ndef g():\n    return 20\n")

    def test_edit_not_unique_or_missing(self):
        p = self.put("a.py", "x = 1\nx = 1\ny = 2\n")
        code, out, err = self.tool("edit", {"path": "a.py", "edits": [{"old_text": "x = 1", "new_text": "x = 3"}]})
        self.assertEqual((code, err), (1, "TextBad"))
        self.assertIn("出現 2 次", out)
        self.assertEqual(self.tool("edit", {"path": "a.py", "edits": [{"old_text": "z", "new_text": "q"}]})[2],
                         "TextMissing")
        # 一處不合就整個不改（全有或全無）
        self.assertEqual(self.tool("edit", {"path": "a.py", "edits": [{"old_text": "y = 2", "new_text": "y = 9"},
                                                                       {"old_text": "nope", "new_text": ""}]})[2],
                         "TextMissing")
        self.assertEqual(p.read_text(), "x = 1\nx = 1\ny = 2\n")

    def test_edit_other_errors(self):
        p = self.put("a.py", "abcdef\n")
        bad = lambda edits: self.tool("edit", {"path": "a.py", "edits": edits})[2]   # noqa: E731
        self.assertEqual(bad([{"old_text": "abcd", "new_text": "X"}, {"old_text": "cdef", "new_text": "Y"}]), "TextBad")
        self.assertEqual(bad([{"old_text": "", "new_text": "X"}]), "TextBad")
        self.assertEqual(bad([{"old_text": "abc", "new_text": "abc"}]), "TextBad")      # 改完一樣
        self.assertEqual(bad([]), "ArgumentsBad")
        self.assertEqual(bad([{"old_text": "abc"}]), "ArgumentsBad")
        self.assertEqual(self.tool("edit", {"path": "nope.py", "edits": [{"old_text": "a", "new_text": "b"}]})[2],
                         "FileMissing")
        self.assertEqual(p.read_text(), "abcdef\n")

    def test_edit_keeps_crlf(self):
        p = self.ws / "w.txt"
        p.write_bytes(b"a\r\nb\r\nc\r\n")
        self.assertEqual(self.tool("edit", {"path": "w.txt", "edits": [{"old_text": "a\nb", "new_text": "A\nB"}]})[0], 0)
        self.assertEqual(p.read_bytes(), b"A\r\nB\r\nc\r\n")

    # ---- bash
    def test_bash(self):
        self.put("hello.txt", "hi\n")
        self.assertEqual(self.tool("bash", {"command": "cat hello.txt"}), (0, "hi\n", None))     # cwd＝工作資料夾
        code, out, _ = self.tool("bash", {"command": "echo out; echo err >&2; exit 3"})
        self.assertEqual((code, out), (0, "out\nerr\n\n[結束碼 3]\n"))           # 指令退非 0 不算工具錯
        self.assertEqual(self.tool("bash", {"command": "true"})[1], "(沒有輸出)\n")
        self.assertEqual(self.tool("bash", {"command": "kill -9 $$"})[1], "[被訊號 9 停掉]\n")
        self.assertEqual(self.tool("bash", {"command": ""})[2], "ArgumentsBad")
        self.assertEqual(self.tool("bash", {"command": "ls", "timeout_s": 0})[2], "ArgumentsBad")
        self.assertEqual(self.tool("bash", {"command": "ls", "timeout_s": 301})[2], "ArgumentsBad")
        self.assertEqual(self.tool("bash", {"command": "cat"})[1], "(沒有輸出)\n")   # stdin 是 /dev/null，不會卡

    def test_bash_truncates_tail(self):
        _, out, _ = self.tool("bash", {"command": "seq 1 5000"})
        lines = out.splitlines()
        self.assertEqual((lines[0], lines[1999]), ("3001", "5000"))
        self.assertIn("只留最後 2000 行", lines[-1])
        _, out, _ = self.tool("bash", {"command": "head -c 200000 /dev/zero | tr '\\0' 'x'; echo; echo end"})
        self.assertLess(len(out.encode()), 52 * 1024)
        self.assertIn("end\n", out)

    def test_bash_timeout_kills_group(self):
        pidfile = self.tmp / "child.pid"
        t0 = time.monotonic()
        code, out, err = self.tool("bash", {"command": "echo started; (sleep 60 & echo $! > %s; wait)" % pidfile,
                                            "timeout_s": 1})
        self.assertLess(time.monotonic() - t0, 10)
        self.assertEqual((code, err), (1, "CommandFailed"))
        self.assertTrue(out.startswith("started\n"), out)               # 逾時前的輸出照給
        pid = int(pidfile.read_text())
        time.sleep(0.2)
        with self.assertRaises(ProcessLookupError):                     # 孫行程也停了
            os.kill(pid, 0)

    def test_bash_term_from_outside_kills_command(self):
        """外面（act 格逾時）TERM 這個工具時，指令那一群也要停，不能留成孤兒。"""
        pidfile = self.tmp / "child.pid"
        p = subprocess.Popen([EXEC, str(TOOLS / "bash")], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, start_new_session=True,
                             env=env_with({"AOS_WS": str(self.ws), "AOS_STACK": str(self.tmp / "stack") + "/"}))
        p.stdin.write(json.dumps({"command": "sleep 60 & echo $! > %s; wait" % pidfile}))
        p.stdin.close()
        for _ in range(100):
            if pidfile.exists() and pidfile.read_text().strip():
                break
            time.sleep(0.05)
        p.send_signal(signal.SIGTERM)                                   # 只 TERM 工具本身（aos-exec exec 成它）
        p.wait(10)
        p.stdout.close()
        p.stderr.close()
        pid = int(pidfile.read_text())
        time.sleep(0.2)
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)

    def test_tool_json_shape(self):
        for name in ("read", "write", "edit", "bash"):
            spec = json.loads((TOOLS / name / "_tooldef.json").read_text())
            self.assertEqual(set(spec), {"description", "parameters"})
            self.assertEqual(spec["parameters"]["type"], "object")


if __name__ == "__main__":
    unittest.main()
