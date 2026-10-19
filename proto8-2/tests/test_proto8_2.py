import json, os, subprocess, tempfile, threading, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXEC = str(ROOT / "bin" / "aos-exec")
BOB = str(ROOT / "demo" / "agent-bob")
ANN = str(ROOT / "demo" / "agent-ann")


def run(*args, env=None, **kw):
    e = {k: v for k, v in os.environ.items() if k not in ("AOS_WS", "AOS_ENTRY", "AOS_STACK")}
    e.update(env or {})
    return subprocess.run(args, capture_output=True, text=True, env=e, **kw)


def prog(parent, name, body, mode=0o755, entry=".aos/exec"):
    d = Path(parent) / name
    (d / entry).parent.mkdir(parents=True, exist_ok=True)
    (d / entry).write_text("#!/bin/sh\n" + body)
    (d / entry).chmod(mode)
    return str(d)


def workspace(tmp, name, question):
    ws = Path(tmp) / name
    (ws / "inbox").mkdir(parents=True)
    (ws / "inbox" / "q.txt").write_text(question)
    return ws


class T(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = self._t.name
        self.addCleanup(self._t.cleanup)

    def test_missing_entry(self):
        d = Path(self.tmp, "p"); d.mkdir()
        r = run(EXEC, str(d), self.tmp)
        self.assertEqual(r.returncode, 1)
        self.assertIn("入口不存在", r.stderr)

    def test_exec_json_only(self):
        d = Path(self.tmp, "p", ".aos"); d.mkdir(parents=True)
        (d / "exec.json").write_text('{"argv": ["sh", "-c", "echo $1:$AOS_WS; exit 5", "sh"]}')
        ws = Path(self.tmp, "ws"); ws.mkdir()
        r = run(EXEC, str(d.parent), str(ws), "x")
        self.assertEqual(r.returncode, 5, r.stderr)
        self.assertEqual(r.stdout.strip(), f"x:{ws.resolve()}")

    def test_exec_json_custom_entry_name(self):
        d = Path(self.tmp, "p"); d.mkdir()
        (d / "main.json").write_text('{"argv": ["echo", "hi"]}')
        r = run(EXEC, str(d), self.tmp, env={"AOS_ENTRY": "main"})
        self.assertEqual((r.returncode, r.stdout), (0, "hi\n"))

    def test_small_shell_wrapper_form_1(self):
        d = prog(self.tmp, "p", "exec aos-inst .aos/exec.json \"$@\"\n")
        Path(d, ".aos", "exec.json").write_text('{"argv": ["echo", "a"]}')
        # 小殼 .aos/exec 是可執行檔，優先於同名 .json；殼裡明指 exec.json 所以還是跑得起來
        r = run(EXEC, d, self.tmp, "b")
        self.assertEqual((r.returncode, r.stdout), (0, "a b\n"))

    def test_neither_entry_nor_json(self):
        d = Path(self.tmp, "p"); d.mkdir()
        r = run(EXEC, str(d), self.tmp)
        self.assertEqual(r.returncode, 1)
        self.assertIn("exec.json", r.stderr)

    def test_executable_preferred_over_json(self):
        d = prog(self.tmp, "p", "echo exe\n")
        Path(d, ".aos", "exec.json").write_text('{"argv": ["echo", "json"]}')
        r = run(EXEC, d, self.tmp)
        self.assertEqual(r.stdout, "exe\n")

    def test_not_executable(self):
        d = prog(self.tmp, "p", "echo hi\n", mode=0o644)
        r = run(EXEC, d, self.tmp)
        self.assertEqual(r.returncode, 1)
        self.assertIn("不可執行", r.stderr)

    def test_ws_omitted_without_aos_ws_uses_cwd(self):
        d = prog(self.tmp, "p", 'echo "$AOS_WS"\n')
        ws = Path(self.tmp, "ws"); ws.mkdir()
        other = Path(self.tmp, "other"); other.mkdir()
        r = run(EXEC, d, cwd=str(ws))
        self.assertEqual(r.stdout.strip(), str(ws.resolve()))

    def test_ws_omitted_or_dash_reuses_aos_ws(self):
        d = prog(self.tmp, "p", 'echo "$AOS_WS"\n')
        ws = Path(self.tmp, "ws"); ws.mkdir()
        other = Path(self.tmp, "other"); other.mkdir()
        for extra in ((), ("-",)):
            r = run(EXEC, d, *extra, cwd=str(other), env={"AOS_WS": str(ws)})
            self.assertEqual(r.stdout.strip(), str(ws))

    def test_dash_with_args_passthrough(self):
        d = prog(self.tmp, "p", 'echo "$AOS_WS:$1"\n')
        ws = Path(self.tmp, "ws"); ws.mkdir()
        r = run(EXEC, d, "-", "x", cwd=str(ws))
        self.assertEqual(r.stdout.strip(), f"{ws.resolve()}:x")

    def test_ws_given_is_used_and_relative_to_cwd(self):
        d = prog(self.tmp, "p", 'echo "$AOS_WS"\n')
        ws = Path(self.tmp, "ws"); ws.mkdir()
        r = run(EXEC, d, str(ws), cwd=self.tmp)
        self.assertEqual(r.stdout.strip(), str(ws.resolve()))
        r = run(EXEC, "p", "ws", cwd=self.tmp)
        self.assertEqual(r.stdout.strip(), str(ws.resolve()))

    def test_cd_into_workspace_then_relative_agent(self):
        ws = workspace(self.tmp, "ws", "hello")
        agent_link = Path(self.tmp, "agent-bob"); agent_link.symlink_to(BOB)
        r = run(EXEC, "../agent-bob", cwd=str(ws))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("hello", (ws / "out" / "q.txt").read_text())

    def test_args_after_ws_passthrough(self):
        d = prog(self.tmp, "p", 'echo "$#:$1:$2"\n')
        r = run(EXEC, d, self.tmp, "x", "y")
        self.assertEqual(r.stdout.strip(), "2:x:y")

    def test_args_stdin_cwd_and_custom_entry(self):
        d = prog(self.tmp, "p", 'pwd; echo "$@"; cat\n', entry="main.sh")
        ws = Path(self.tmp, "ws"); ws.mkdir()
        r = run(EXEC, d, str(ws), "a", "b", input="from stdin", env={"AOS_ENTRY": "main.sh"})
        self.assertTrue(r.stdout.startswith(d + "\na b\nfrom stdin"))

    def test_nested_same_workspace(self):
        inner = prog(self.tmp, "outer/inner", 'echo "$AOS_WS" > "$AOS_WS/seen"\n')
        outer = prog(self.tmp, "outer", f'aos-exec {inner}\n')
        ws = Path(self.tmp, "ws"); ws.mkdir()
        r = run(EXEC, outer, str(ws))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((ws / "seen").read_text().strip(), str(ws))

    def test_demo_flow(self):
        ws = workspace(self.tmp, "ws", "hello")
        r = run(EXEC, BOB, str(ws))
        self.assertEqual(r.returncode, 0, r.stderr)
        tr = [json.loads(l) for l in (ws / ".aos" / "trace.jsonl").read_text().splitlines()]
        self.assertEqual([(t["state"], t["code"]) for t in tr],
                         [("idle", 0), ("think", 0), ("act", 0), ("idle", 10)])
        self.assertIn("hello", (ws / "out" / "q.txt").read_text())
        self.assertTrue((ws / "done" / "q.txt").exists())
        self.assertFalse((ws / "inbox" / "q.txt").exists())

    def test_two_workspaces_concurrently(self):
        a, b = workspace(self.tmp, "a", "AAA"), workspace(self.tmp, "b", "BBB")
        rs = {}
        ths = [threading.Thread(target=lambda w=w: rs.update({w: run(EXEC, BOB, str(w))})) for w in (a, b)]
        [t.start() for t in ths]; [t.join() for t in ths]
        for w, tag in ((a, "AAA"), (b, "BBB")):
            self.assertEqual(rs[w].returncode, 0, rs[w].stderr)
            out = (w / "out" / "q.txt").read_text()
            self.assertIn(tag, out)
        self.assertNotIn("BBB", (a / "out" / "q.txt").read_text())
        self.assertEqual(list(Path(BOB).rglob("state")), [])  # 定義資料夾保持乾淨
        self.assertEqual(list(Path(BOB).rglob("trace.jsonl")), [])
        self.assertNotEqual((a / ".aos" / "plan").read_text(), (b / ".aos" / "plan").read_text())

    def test_stack_default_and_override(self):
        d = prog(self.tmp, "p", 'echo "$AOS_STACK"\n')
        ws = Path(self.tmp, "ws"); ws.mkdir()
        r = run(EXEC, d, str(ws))
        self.assertEqual(r.stdout.strip(), str(ws) + "/.aos/")
        self.assertTrue((ws / ".aos").is_dir())
        mine = Path(self.tmp, "mystack")
        r = run(EXEC, d, str(ws), env={"AOS_STACK": str(mine)})
        self.assertEqual(r.stdout.strip(), str(mine) + "/")
        self.assertTrue(mine.is_dir())

    def test_nested_shares_stack(self):
        inner = prog(self.tmp, "outer/inner", 'echo "$AOS_STACK" > "$AOS_STACK/seen"\n')
        outer = prog(self.tmp, "outer", f'aos-exec {inner}\n')
        ws = Path(self.tmp, "ws"); ws.mkdir()
        self.assertEqual(run(EXEC, outer, str(ws)).returncode, 0)
        self.assertEqual((ws / ".aos" / "seen").read_text().strip(), str(ws) + "/.aos/")

    def test_bob_state_in_stack_not_ws_or_def(self):
        ws = workspace(self.tmp, "ws", "hello")
        self.assertEqual(run(EXEC, BOB, str(ws)).returncode, 0)
        for n in ("state", "trace.jsonl", "plan", "current"):
            self.assertTrue((ws / ".aos" / n).exists(), n)
            self.assertFalse((ws / n).exists(), n)
            self.assertEqual(list(Path(BOB).rglob(n)), [])

    def test_bob_requires_stack(self):
        ws = workspace(self.tmp, "ws", "hello")
        r = run(str(Path(BOB) / "act/.aos/exec"), env={"AOS_WS": str(ws)})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("沒設定 AOS_STACK", r.stderr)
        # fsm 本身沒設 AOS_STACK 也退 1
        r = run(str(ROOT / "bin" / "aos-fsm"), "fsm.json", env={"AOS_WS": str(ws)},
                cwd=BOB)
        self.assertEqual(r.returncode, 1)
        self.assertIn("沒設定 AOS_STACK", r.stderr)

    def test_bob_think_is_embedded_inst(self):
        cfg = json.loads((Path(BOB) / "fsm.json").read_text())
        think = cfg["states"]["think"]["val"]
        self.assertIsInstance(think, dict)
        self.assertEqual(think["argv"][0], "python3")
        self.assertEqual(cfg["states"]["idle"]["val"], "idle")   # 資料夾格
        self.assertEqual(cfg["states"]["act"]["val"], "act")
        self.assertFalse((Path(BOB) / "fsm").exists())

    def test_bob_entry_direct_exec_no_enoexec(self):
        # 入口帶 shebang：不經 sh、直接 exec 也跑得起來（P-05）
        ws = workspace(self.tmp, "ws", "hello")
        stack = Path(self.tmp, "stack")
        stack.mkdir()
        env = {"AOS_WS": str(ws), "AOS_STACK": str(stack),
               "PATH": str(ROOT / "bin") + os.pathsep + os.environ["PATH"]}
        r = run(str(Path(BOB) / ".aos" / "exec"), env=env, cwd=BOB)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((ws / "done" / "q.txt").exists())

    def test_loop_failure_code(self):
        prog(self.tmp, "agent/bad", "exit 7\n")
        agent = prog(self.tmp, "agent", "aos-loop loop.json\n")
        Path(agent, "loop.json").write_text('{"run": "bad", "max": 3}')
        ws = Path(self.tmp, "ws"); ws.mkdir()
        self.assertEqual(run(EXEC, agent, str(ws)).returncode, 7)

    def test_loop_embedded_inst_runs_each_lap(self):
        agent = prog(self.tmp, "agent", "aos-loop loop.json\n")
        Path(agent, "loop.json").write_text(json.dumps(
            {"run": {"argv": ["sh", "-c", 'echo x >> "$AOS_STACK/n"']}, "max": 3}))
        ws = Path(self.tmp, "ws"); ws.mkdir()
        r = run(EXEC, agent, str(ws))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((ws / ".aos" / "n").read_text().split(), ["x", "x", "x"])

    def test_loop_embedded_inst_stop_and_failure_codes(self):
        for code, want in ((10, 0), (7, 7)):
            agent = prog(self.tmp, f"agent{code}", "aos-loop loop.json\n")
            Path(agent, "loop.json").write_text(json.dumps(
                {"run": {"argv": ["sh", "-c", f"exit {code}"]}, "max": 3}))
            ws = Path(self.tmp, f"ws{code}"); ws.mkdir()
            self.assertEqual(run(EXEC, agent, str(ws)).returncode, want)

    def test_loop_own_errors_exit_1_one_line(self):
        agent = prog(self.tmp, "agent", "aos-loop loop.json\n")
        ws = Path(self.tmp, "ws"); ws.mkdir()
        for text in (None, "{nope", '{"max": 2}', '{"run": {"argv": ["no-such-cmd-xyz"]}}'):
            if text is not None:
                Path(agent, "loop.json").write_text(text)
            r = run(EXEC, agent, str(ws))
            self.assertEqual(r.returncode, 1, text)
            self.assertEqual(len(r.stderr.strip().splitlines()), 1, text)
            self.assertTrue(r.stderr.startswith("aos-loop: "), text)

    def test_demo_flow_ann(self):
        ws = workspace(self.tmp, "ws", "hello")
        r = run(EXEC, ANN, str(ws))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("hello", (ws / "out" / "q.txt").read_text())
        self.assertTrue((ws / "done" / "q.txt").exists())
        self.assertFalse((ws / "inbox" / "q.txt").exists())
        self.assertEqual((ws / ".aos" / "state").read_text(), "idle\n")
        tr = [json.loads(l) for l in (ws / ".aos" / "trace.jsonl").read_text().splitlines()]
        self.assertEqual([(t["state"], t["code"]) for t in tr],
                         [("idle", 0), ("think", 0), ("act", 0), ("idle", 10)])
        for n in ("state", "trace.jsonl", "plan", "current"):
            self.assertEqual(list(Path(ANN).rglob(n)), [], n)   # 定義資料夾乾淨

    def test_stamp_tool_alone(self):
        stamp = str(Path(BOB) / "act" / "tools" / "stamp")
        ws = Path(self.tmp, "ws"); ws.mkdir()
        for n in ("1", "2"):
            r = run(EXEC, stamp, str(ws), input="body text\n")
            self.assertEqual(r.returncode, 0, r.stderr)
            lines = r.stdout.split("\n")
            self.assertTrue(lines[0].startswith("# "), r.stdout)
            self.assertEqual(lines[1], "body text")
            self.assertEqual((ws / ".aos" / "runs").read_text().strip(), n)

    def test_bob_act_goes_through_stamp_with_own_stack(self):
        ws = workspace(self.tmp, "ws", "hello")
        self.assertEqual(run(EXEC, BOB, str(ws)).returncode, 0)
        out = (ws / "out" / "q.txt").read_text().split("\n")
        self.assertTrue(out[0].startswith("# "))
        self.assertIn("hello", out[1])
        self.assertEqual((ws / ".aos" / "stamp" / "runs").read_text().strip(), "1")
        self.assertFalse((ws / ".aos" / "runs").exists())     # 子 stack 分開
        self.assertEqual(list(Path(BOB).rglob("runs")), [])    # 定義資料夾乾淨

    def test_path_not_duplicated(self):
        c = prog(self.tmp, "c", 'echo "$PATH"' + chr(10))
        b = prog(self.tmp, "b", f'aos-exec {c} > "$AOS_WS/path"' + chr(10))
        a = prog(self.tmp, "a", f'aos-exec {b}' + chr(10))
        ws = Path(self.tmp, "ws"); ws.mkdir()
        self.assertEqual(run(EXEC, a, str(ws)).returncode, 0)
        parts = (ws / "path").read_text().strip().split(":")
        self.assertEqual(parts.count(str(ROOT / "bin")), 1)


if __name__ == "__main__":
    unittest.main()
