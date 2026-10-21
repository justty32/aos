import json, os, subprocess, tempfile, threading, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXEC = str(ROOT / "bin" / "aos-exec")
BOB = str(ROOT / "demo" / "agent-bob")
ANN = str(ROOT / "demo" / "agent-ann")
CATHY = str(ROOT / "demo" / "agent-bob" / "act" / "tools" / "cathy")


def run(*args, env=None, **kw):
    # aos 的程式都不動 PATH（ideas § 24）：入口裡叫 aos-exec／aos-loop／aos-fsm，由呼叫者把 bin/ 放進 PATH
    e = {k: v for k, v in os.environ.items() if k not in ("AOS_WS", "AOS_ENTRY", "AOS_STACK")}
    e["PATH"] = str(ROOT / "bin") + os.pathsep + e.get("PATH", "")
    e.update(env or {})
    return subprocess.run(args, capture_output=True, text=True, env=e, **kw)


def prog(parent, name, body, mode=0o755, entry="_exec"):
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
        r = run(EXEC, "--ws", self.tmp, str(d))
        self.assertEqual(r.returncode, 1)
        self.assertIn("入口不存在", r.stderr)

    def test_exec_json_only(self):
        d = Path(self.tmp, "p"); d.mkdir(parents=True)
        (d / "_exec.json").write_text('{"argv": ["sh", "-c", "echo $1:$AOS_WS; exit 5", "sh"]}')
        ws = Path(self.tmp, "ws"); ws.mkdir()
        r = run(EXEC, "--ws", str(ws), str(d), "x")
        self.assertEqual(r.returncode, 5, r.stderr)
        self.assertEqual(r.stdout.strip(), f"x:{ws.resolve()}")

    def test_exec_json_custom_entry_name(self):
        d = Path(self.tmp, "p"); d.mkdir()
        (d / "main.json").write_text('{"argv": ["echo", "hi"]}')
        r = run(EXEC, "--ws", self.tmp, str(d), env={"AOS_ENTRY": "main"})
        self.assertEqual((r.returncode, r.stdout), (0, "hi\n"))

    def test_small_shell_wrapper_form_1(self):
        d = prog(self.tmp, "p", "exec aos-inst _exec.json \"$@\"\n")
        Path(d, "_exec.json").write_text('{"argv": ["echo", "a"]}')
        # 小殼 _exec 是可執行檔，優先於同名 .json；殼裡明指 _exec.json 所以還是跑得起來
        r = run(EXEC, "--ws", self.tmp, d, "b")
        self.assertEqual((r.returncode, r.stdout), (0, "a b\n"))

    def test_neither_entry_nor_json(self):
        d = Path(self.tmp, "p"); d.mkdir()
        r = run(EXEC, "--ws", self.tmp, str(d))
        self.assertEqual(r.returncode, 1)
        self.assertIn("exec.json", r.stderr)

    def test_executable_preferred_over_json(self):
        d = prog(self.tmp, "p", "echo exe\n")
        Path(d, "_exec.json").write_text('{"argv": ["echo", "json"]}')
        r = run(EXEC, "--ws", self.tmp, d)
        self.assertEqual(r.stdout, "exe\n")

    def test_not_executable(self):
        # § 14 之後沒 +x 不再是錯、改當 JSON 讀；sh 腳本不是 JSON＝入口壞（N-60、N-61）
        d = prog(self.tmp, "p", "echo hi\n", mode=0o644)
        r = run(EXEC, "--ws", self.tmp, d)
        self.assertEqual(r.returncode, 1)
        self.assertIn("入口壞", r.stderr)

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
        for extra in ((), ("--ws", "-"), ("--ws=",)):
            r = run(EXEC, *extra, d, cwd=str(other), env={"AOS_WS": str(ws)})
            self.assertEqual(r.stdout.strip(), str(ws))

    def test_dash_with_args_passthrough(self):
        d = prog(self.tmp, "p", 'echo "$AOS_WS:$1"\n')
        ws = Path(self.tmp, "ws"); ws.mkdir()
        r = run(EXEC, "--ws", "-", d, "x", cwd=str(ws))
        self.assertEqual(r.stdout.strip(), f"{ws.resolve()}:x")

    def test_ws_given_is_used_and_relative_to_cwd(self):
        d = prog(self.tmp, "p", 'echo "$AOS_WS"\n')
        ws = Path(self.tmp, "ws"); ws.mkdir()
        r = run(EXEC, "--ws", str(ws), d, cwd=self.tmp)
        self.assertEqual(r.stdout.strip(), str(ws.resolve()))
        r = run(EXEC, "--ws=ws", "p", cwd=self.tmp)
        self.assertEqual(r.stdout.strip(), str(ws.resolve()))

    def test_cd_into_workspace_then_relative_agent(self):
        ws = workspace(self.tmp, "ws", "hello")
        agent_link = Path(self.tmp, "agent-bob"); agent_link.symlink_to(BOB)
        r = run(EXEC, "../agent-bob", cwd=str(ws))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("hello", (ws / "out" / "q.txt").read_text())

    def test_args_after_ws_passthrough(self):
        d = prog(self.tmp, "p", 'echo "$#:$1:$2"\n')
        r = run(EXEC, "--ws", self.tmp, d, "x", "y")
        self.assertEqual(r.stdout.strip(), "2:x:y")

    def test_args_stdin_cwd_and_custom_entry(self):
        d = prog(self.tmp, "p", 'pwd; echo "$@"; cat\n', entry="main.sh")
        ws = Path(self.tmp, "ws"); ws.mkdir()
        r = run(EXEC, "--ws", str(ws), d, "a", "b", input="from stdin", env={"AOS_ENTRY": "main.sh"})
        self.assertTrue(r.stdout.startswith(d + "\na b\nfrom stdin"))

    def test_nested_same_workspace(self):
        inner = prog(self.tmp, "outer/inner", 'echo "$AOS_WS" > "$AOS_WS/seen"\n')
        outer = prog(self.tmp, "outer", f'aos-exec {inner}\n')
        ws = Path(self.tmp, "ws"); ws.mkdir()
        r = run(EXEC, "--ws", str(ws), outer)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((ws / "seen").read_text().strip(), str(ws))

    def test_demo_flow(self):
        ws = workspace(self.tmp, "ws", "hello")
        r = run(EXEC, "--ws", str(ws), BOB)
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
        ths = [threading.Thread(target=lambda w=w: rs.update({w: run(EXEC, "--ws", str(w), BOB)})) for w in (a, b)]
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
        r = run(EXEC, "--ws", str(ws), d)
        self.assertEqual(r.stdout.strip(), str(ws) + "/.aos/")
        self.assertTrue((ws / ".aos").is_dir())
        mine = Path(self.tmp, "mystack")
        r = run(EXEC, "--ws", str(ws), d, env={"AOS_STACK": str(mine)})
        self.assertEqual(r.stdout.strip(), str(mine) + "/")
        self.assertTrue(mine.is_dir())

    def test_nested_shares_stack(self):
        inner = prog(self.tmp, "outer/inner", 'echo "$AOS_STACK" > "$AOS_STACK/seen"\n')
        outer = prog(self.tmp, "outer", f'aos-exec {inner}\n')
        ws = Path(self.tmp, "ws"); ws.mkdir()
        self.assertEqual(run(EXEC, "--ws", str(ws), outer).returncode, 0)
        self.assertEqual((ws / ".aos" / "seen").read_text().strip(), str(ws) + "/.aos/")

    def test_bob_state_in_stack_not_ws_or_def(self):
        ws = workspace(self.tmp, "ws", "hello")
        self.assertEqual(run(EXEC, "--ws", str(ws), BOB).returncode, 0)
        for n in ("state", "trace.jsonl", "plan", "current"):
            self.assertTrue((ws / ".aos" / n).exists(), n)
            self.assertFalse((ws / n).exists(), n)
            self.assertEqual(list(Path(BOB).rglob(n)), [])

    def test_bob_requires_stack(self):
        ws = workspace(self.tmp, "ws", "hello")
        r = run(str(Path(BOB) / "act/_exec"), env={"AOS_WS": str(ws)})
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
        r = run(str(Path(BOB) / "_exec"), env=env, cwd=BOB)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((ws / "done" / "q.txt").exists())

    def test_loop_failure_code(self):
        prog(self.tmp, "agent/bad", "exit 7\n")
        agent = prog(self.tmp, "agent", "aos-loop loop.json\n")
        Path(agent, "loop.json").write_text('{"run": "bad", "max": 3}')
        ws = Path(self.tmp, "ws"); ws.mkdir()
        self.assertEqual(run(EXEC, "--ws", str(ws), agent).returncode, 7)

    def test_loop_embedded_inst_runs_each_lap(self):
        agent = prog(self.tmp, "agent", "aos-loop loop.json\n")
        Path(agent, "loop.json").write_text(json.dumps(
            {"run": {"argv": ["sh", "-c", 'echo x >> "$AOS_STACK/n"']}, "max": 3}))
        ws = Path(self.tmp, "ws"); ws.mkdir()
        r = run(EXEC, "--ws", str(ws), agent)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((ws / ".aos" / "n").read_text().split(), ["x", "x", "x"])

    def test_loop_reaching_max_exits_0_with_empty_stderr(self):
        # N-43：正常退出不寫 stderr（要知道有沒有跑滿看 trace.jsonl 行數）
        agent = prog(self.tmp, "agent", "aos-loop loop.json\n")
        Path(agent, "loop.json").write_text(json.dumps({"run": {"argv": ["true"]}, "max": 2}))
        ws = Path(self.tmp, "ws"); ws.mkdir()
        r = run(EXEC, "--ws", str(ws), agent)
        self.assertEqual((r.returncode, r.stderr), (0, ""))

    def test_brain_writes_current_by_rename(self):
        # N-05：current 先寫 .current 再改名
        for agent in (BOB, ANN):
            ws = workspace(self.tmp, "ws-" + Path(agent).name, "1+1？")
            stack = ws / ".aos"; stack.mkdir()
            (stack / "current").write_text("old\n")
            before = os.stat(stack / "current").st_ino
            r = run("python3", str(Path(agent) / "brain.py"), env={"AOS_WS": str(ws), "AOS_STACK": str(stack)})
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual((stack / "current").read_text(), "q.txt\n")
            self.assertNotEqual(os.stat(stack / "current").st_ino, before)
            self.assertFalse((stack / ".current").exists())

    def test_loop_embedded_inst_stop_and_failure_codes(self):
        for code, want in ((10, 0), (7, 7)):
            agent = prog(self.tmp, f"agent{code}", "aos-loop loop.json\n")
            Path(agent, "loop.json").write_text(json.dumps(
                {"run": {"argv": ["sh", "-c", f"exit {code}"]}, "max": 3}))
            ws = Path(self.tmp, f"ws{code}"); ws.mkdir()
            self.assertEqual(run(EXEC, "--ws", str(ws), agent).returncode, want)

    def test_loop_own_errors_exit_1_one_line(self):
        agent = prog(self.tmp, "agent", "aos-loop loop.json\n")
        ws = Path(self.tmp, "ws"); ws.mkdir()
        for text in (None, "{nope", '{"max": 2}', '{"run": {"argv": ["no-such-cmd-xyz"]}}'):
            if text is not None:
                Path(agent, "loop.json").write_text(text)
            r = run(EXEC, "--ws", str(ws), agent)
            self.assertEqual(r.returncode, 1, text)
            self.assertEqual(len(r.stderr.strip().splitlines()), 1, text)
            self.assertTrue(r.stderr.startswith("aos-loop: "), text)

    def test_demo_flow_ann(self):
        ws = workspace(self.tmp, "ws", "hello")
        r = run(EXEC, "--ws", str(ws), ANN)
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

    def test_ann_has_no_cell_folders(self):
        execs = sorted(str(p.relative_to(ANN)) for p in Path(ANN).rglob("_exec"))
        self.assertEqual(execs, ["_exec"])
        self.assertEqual(sorted(p.name for p in Path(ANN).iterdir()),
                         ["_exec", "act.py", "brain.py", "fsm.json", "idle.py", "loop.json"])

    def test_stamp_tool_alone(self):
        stamp = str(Path(CATHY) / "act" / "tools" / "stamp")
        ws = Path(self.tmp, "ws"); ws.mkdir()
        for n in ("1", "2"):
            r = run(EXEC, "--ws", str(ws), stamp, input="body text\n")
            self.assertEqual(r.returncode, 0, r.stderr)
            lines = r.stdout.split("\n")
            self.assertTrue(lines[0].startswith("# "), r.stdout)
            self.assertEqual(lines[1], "body text")
            self.assertEqual((ws / ".aos" / "runs").read_text().strip(), n)

    def test_nested_three_levels(self):
        ws = workspace(self.tmp, "ws", "hello")
        r = run(EXEC, "--ws", str(ws), BOB)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = (ws / "out" / "q.txt").read_text().split("\n")
        self.assertTrue(out[0].startswith("# "))
        self.assertIn("FAKE ANSWER to: FAKE ANSWER to: hello", out[1])   # 兩層假腦疊出來
        st = ws / ".aos"
        for f in ("state", "current", "plan", "trace.jsonl"):
            self.assertTrue((st / f).is_file(), f)
            self.assertTrue((st / "cathy" / f).is_file(), "cathy/" + f)
        self.assertTrue((st / "cathy/ws/done/q.txt").exists())
        self.assertTrue((st / "cathy/ws/out/q.txt").exists())
        self.assertEqual((st / "cathy/stamp/runs").read_text().strip(), "1")
        self.assertFalse((st / "runs").exists())      # 子 stack 分開
        self.assertFalse((st / "ws").exists())
        self.assertEqual(list(Path(BOB).rglob("runs")), [])    # 定義資料夾乾淨

    def test_cathy_does_not_touch_bob_ws(self):
        ws = workspace(self.tmp, "ws", "hello")
        self.assertEqual(run(EXEC, "--ws", str(ws), BOB).returncode, 0)
        self.assertEqual(list((ws / "inbox").iterdir()), [])
        self.assertTrue((ws / "done" / "q.txt").exists())
        self.assertEqual([p.name for p in (ws / "out").iterdir()], ["q.txt"])
        self.assertEqual(sorted(p.name for p in ws.iterdir()), [".aos", "done", "inbox", "out"])
        self.assertTrue((ws / ".aos/cathy/trace.jsonl").exists())
        self.assertEqual(len((ws / ".aos/trace.jsonl").read_text().splitlines()), 4)

    def test_two_questions_substack_reused_not_leaking(self):
        ws = Path(self.tmp, "ws"); (ws / "inbox").mkdir(parents=True)
        (ws / "inbox" / "q1.txt").write_text("AAA")
        (ws / "inbox" / "q2.txt").write_text("BBB")
        r = run(EXEC, "--ws", str(ws), BOB)
        self.assertEqual(r.returncode, 0, r.stderr)
        a, b = (ws / "out" / "q1.txt").read_text(), (ws / "out" / "q2.txt").read_text()
        self.assertIn("AAA", a); self.assertNotIn("BBB", a)
        self.assertIn("BBB", b); self.assertNotIn("AAA", b)
        c = ws / ".aos" / "cathy"
        self.assertEqual((c / "state").read_text(), "idle\n")
        self.assertEqual(len((c / "trace.jsonl").read_text().splitlines()), 8)
        self.assertEqual(sorted(p.name for p in (c / "ws" / "done").iterdir()), ["q1.txt", "q2.txt"])
        self.assertEqual((c / "current").read_text().strip(), "q2.txt")
        self.assertEqual(len((ws / ".aos" / "trace.jsonl").read_text().splitlines()), 7)

    def test_cathy_standalone(self):
        ws = workspace(self.tmp, "ws", "hello")
        r = run(EXEC, "--ws", str(ws), CATHY)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("hello", (ws / "out" / "q.txt").read_text())
        self.assertTrue((ws / "done" / "q.txt").exists())
        self.assertEqual((ws / ".aos" / "stamp" / "runs").read_text().strip(), "1")

    def test_sub_agent_stop_code_not_leaking(self):
        outer = prog(self.tmp, "outer", "exec aos-loop loop.json\n")
        Path(outer, "loop.json").write_text('{"run": {"argv": ["aos-fsm", "fsm.json"]}, "max": 2}')
        Path(outer, "fsm.json").write_text(json.dumps({"start": "s", "states": {
            "s": {"val": "sub", "next": "t"}, "t": {"val": {"argv": ["true"]}, "next": "s"}}}))
        prog(outer, "sub", "exec aos-loop loop.json\n")
        Path(outer, "sub", "loop.json").write_text('{"run": "idle", "max": 5}')
        prog(Path(outer, "sub"), "idle", "exit 10\n")
        ws = Path(self.tmp, "ws"); ws.mkdir()
        r = run(EXEC, "--ws", str(ws), outer)
        self.assertEqual(r.returncode, 0, r.stderr)
        tr = [json.loads(l) for l in (ws / ".aos" / "trace.jsonl").read_text().splitlines()]
        self.assertEqual([(t["state"], t["code"]) for t in tr], [("s", 0), ("t", 0)])   # 外層沒被誤停
        self.assertEqual((ws / ".aos" / "state").read_text(), "s\n")

    def test_cathy_failure_stops_bob(self):
        ws = workspace(self.tmp, "ws", "hello")
        (ws / ".aos" / "cathy").mkdir(parents=True)
        (ws / ".aos" / "cathy" / "state").write_text("act\n")      # 停在半路、沒有 current
        r = run(EXEC, "--ws", str(ws), BOB)
        self.assertEqual(r.returncode, 1)
        self.assertEqual((ws / ".aos" / "state").read_text(), "act\n")
        self.assertIn("cathy 失敗", r.stderr)
        self.assertIn("agent-cathy act", r.stderr)      # cathy 自己那層的一行
        self.assertTrue((ws / "inbox" / "q.txt").exists())


if __name__ == "__main__":
    unittest.main()
