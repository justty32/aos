import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "aos-step-lua"
LUA = "/usr/bin/lua5.4"
EXEC = ROOT.parent / "proto4-3" / "aos-exec"
LUA_PATH = str(ROOT / "lua" / "?.lua") + ";;"


class StepLuaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aos-step-lua-")
        self.home = Path(self.tmp.name)
        self.prog = self.home / "job.lua"

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, source):
        self.prog.write_text(source, encoding="utf-8")

    def run_tool(self, *args, prog=None, env=None):
        return subprocess.run(
            [str(TOOL), str(prog or self.prog), *args], cwd=self.home,
            text=True, capture_output=True, check=False, env=env,
        )

    def state(self):
        return json.loads((self.home / "job.state.json").read_text(encoding="utf-8"))

    def test_steps_follow_returned_order_and_names(self):
        self.write("local function second(s) end\nlocal function first(s) end\n"
                   "return {{name='second',fn=second},{name='first',fn=first}}\n")
        result = self.run_tool("--status")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["steps"], ["second", "first"])

    def test_finds_lua_modules_when_invoked_through_path(self):
        self.write("local function only(s) s.ok=true end\nreturn {{name='only',fn=only}}\n")
        env = os.environ.copy(); env["PATH"] = str(ROOT) + os.pathsep + env["PATH"]
        result = subprocess.run(["aos-step-lua", str(self.prog)], cwd=self.home, env=env,
                                text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.state()["state"]["ok"])

    def test_state_crosses_steps_and_file_has_readable_shape(self):
        self.write("local function load(s) s.x=4 end\nlocal function compute(s) s.x=s.x*3 end\n"
                   "return {{name='load',fn=load},{name='compute',fn=compute}}\n")
        self.assertEqual(self.run_tool().returncode, 0)
        self.assertEqual(self.run_tool().returncode, 0)
        state = self.state()
        self.assertEqual(state["state"], {"x": 12})
        self.assertEqual(state["steps"], ["load", "compute"])
        self.assertTrue((self.home / "job.state.json").read_text().startswith('{"state":'))

    def test_binary_is_base64_on_disk_and_round_trips(self):
        self.write("local function put(s) s.raw='\\0\\255\\1' end\n"
                   "local function check(s) s.same=(s.raw=='\\0\\255\\1') end\n"
                   "return {{name='put',fn=put},{name='check',fn=check}}\n")
        self.assertEqual(self.run_tool().returncode, 0)
        raw = (self.home / "job.state.json").read_text()
        self.assertIn('"raw":{"$b64":"AP8B"}', raw)
        self.assertEqual(self.run_tool().returncode, 0)
        self.assertTrue(self.state()["state"]["same"])
        self.assertEqual(self.state()["state"]["raw"], {"$b64": "AP8B"})

    def test_aos_b64_and_unb64(self):
        self.write("local function codec(s) local x='\\0\\255\\1'; s.encoded=aos.b64(x); s.same=aos.unb64(s.encoded)==x end\n"
                   "return {{name='codec',fn=codec}}\n")
        self.assertEqual(self.run_tool().returncode, 0)
        self.assertEqual(self.state()["state"], {"encoded": "AP8B", "same": True})

    def test_step_failure_rolls_back_and_writes_traceback(self):
        self.write("local function good(s) s.kept=1 end\nlocal function boom(s) s.kept=9; error('bad first line\\nmore') end\n"
                   "return {{name='good',fn=good},{name='boom',fn=boom}}\n")
        self.assertEqual(self.run_tool().returncode, 0)
        result = self.run_tool()
        self.assertEqual(result.returncode, 1)
        self.assertEqual((self.state()["pc"], self.state()["state"]), (1, {"kept": 1}))
        self.assertIn("第 1 格 boom", result.stderr)
        error = (self.home / ".aos-step-lua/error").read_text()
        self.assertIn("stack traceback", error)
        self.assertIn("bad first line", error)
        self.assertIn("bad first line", self.run_tool("--status").stderr)

    def test_function_in_state_fails_without_advancing(self):
        self.write("local function bad(s) s.x=function() end end\nreturn {{name='bad',fn=bad}}\n")
        result = self.run_tool()
        self.assertEqual(result.returncode, 1)
        self.assertFalse((self.home / "job.state.json").exists())
        self.assertIn("state 裡有 JSON 放不進的東西：函式", result.stderr)

    def test_syntax_error_is_exit_two(self):
        self.write("local function broken( end\n")
        result = self.run_tool()
        self.assertEqual(result.returncode, 2)
        self.assertIn("載不起 PROG", result.stderr)

    def test_missing_return_array_is_exit_two(self):
        self.write("local function nope(s) end\n")
        result = self.run_tool()
        self.assertEqual(result.returncode, 2)
        self.assertIn("return 步驟陣列", result.stderr)

    def test_missing_step_name_or_fn_is_exit_two(self):
        self.write("return {{name='bad'}}\n")
        result = self.run_tool()
        self.assertEqual(result.returncode, 2)
        self.assertIn("缺 fn", result.stderr)

    def test_done_returns_100_repeatedly(self):
        self.write("local function only(s) end\nreturn {{name='only',fn=only}}\n")
        self.assertEqual(self.run_tool().returncode, 0)
        self.assertTrue(self.state()["done"])
        self.assertEqual(self.run_tool().returncode, 100)
        self.assertEqual(self.run_tool().returncode, 100)

    def test_wait_for_blocks_until_file_then_runs_next_step(self):
        self.write("local function submit(s) return aos.wait_for('out.json') end\n"
                   "local function consume(s) local f=assert(io.open(here..'/next.txt','w')); f:write('ran'); f:close() end\n"
                   "return {{name='submit',fn=submit},{name='consume',fn=consume}}\n")
        self.assertEqual(self.run_tool().returncode, 0)
        first = self.state()
        self.assertEqual((first["pc"], first["waiting"]["checks"]), (1, 0))
        self.assertEqual(first["waiting"]["for"], str(self.home / "out.json"))
        self.assertEqual(self.run_tool().returncode, 0)
        blocked = self.state()
        self.assertEqual(blocked["waiting"]["checks"], 1)
        self.assertEqual((blocked["last"], blocked["history"]),
                         (first["last"], first["history"]))
        self.assertFalse((self.home / "next.txt").exists())
        (self.home / "out.json").touch()
        self.assertEqual(self.run_tool().returncode, 0)
        state = self.state()
        self.assertNotIn("waiting", state)
        self.assertEqual((self.home / "next.txt").read_text(), "ran")
        self.assertIn("(wait)", [item.get("step") for item in state["history"]])

    def test_last_lua_step_can_wait_before_done_exit(self):
        self.write("local function only(s) return aos.wait_for('last.out') end\n"
                   "return {{name='only',fn=only}}\n")
        self.assertEqual(self.run_tool().returncode, 0)
        self.assertFalse(self.state()["done"])
        self.assertEqual(self.run_tool().returncode, 0)
        (self.home / "last.out").touch()
        self.assertEqual(self.run_tool().returncode, 100)
        self.assertTrue(self.state()["done"])

    def test_waiting_status_and_reset(self):
        self.write("local function only(s) return aos.wait_for('pending.out') end\n"
                   "return {{name='only',fn=only}}\n")
        self.run_tool()
        status = self.run_tool("--status")
        self.assertIn("waiting", json.loads(status.stdout))
        self.assertIn("在等 " + str(self.home / "pending.out"), status.stderr)
        self.assertEqual(self.run_tool("--reset").returncode, 0)
        self.assertNotIn("waiting", json.loads(self.run_tool("--status").stdout))

    def test_reset_removes_progress_and_error(self):
        self.write("local function only(s) s.x=1 end\nreturn {{name='only',fn=only}}\n")
        self.run_tool()
        self.assertEqual(self.run_tool("--reset").returncode, 0)
        self.assertFalse((self.home / "job.state.json").exists())
        self.assertEqual(json.loads(self.run_tool("--status").stdout)["pc"], 0)

    def test_changed_program_warns_and_runs_current_pc(self):
        self.write("local function one(s) end\nlocal function old(s) s.which='old' end\nreturn {{name='one',fn=one},{name='old',fn=old}}\n")
        self.run_tool()
        self.write("local function one(s) end\nlocal function newer(s) s.which='new' end\nreturn {{name='one',fn=one},{name='newer',fn=newer}}\n")
        result = self.run_tool()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PROG 改過了（上次 2 個、現在 2 個）", result.stderr)
        self.assertIn("函式名對不上（上次 old、現在 newer）", result.stderr)
        self.assertEqual(self.state()["state"]["which"], "new")

    def test_here_pc_and_global_state_are_available(self):
        self.write("local function first(s) s.at=here; s.pc0=pc; s.global=(state==s) end\n"
                   "local function second(s) s.pc1=pc end\n"
                   "return {{name='first',fn=first},{name='second',fn=second}}\n")
        self.run_tool(); self.run_tool()
        self.assertEqual(self.state()["state"], {"at": str(self.home), "global": True, "pc0": 0, "pc1": 1})

    def test_call_dir_read_and_json(self):
        child = self.home / "child"
        (child / ".aos").mkdir(parents=True)
        (child / ".aos/inst.json").write_text(json.dumps({
            "argv": ["sh", "-c", "printf '{\"answer\":42}'"], "stdout": "out.json"}))
        self.write("local function tool(s) local r=aos.call_dir('child',{read='child/out.json',json=true}); s.r=aos.value(r) end\n"
                   "return {{name='tool',fn=tool}}\n")
        result = self.run_tool()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.state()["state"]["r"], {"answer": 42})

    def test_call_returns_child_exit_three(self):
        script = self.home / "exit3"
        script.write_text("#!/bin/sh\nexit 3\n"); script.chmod(0o755)
        self.write("local function tool(s) s.r=aos.call('./exit3') end\nreturn {{name='tool',fn=tool}}\n")
        self.assertEqual(self.run_tool().returncode, 0)
        result = self.state()["state"]["r"]
        self.assertEqual((result["code"], result["kind"]), (3, "child"))
        self.assertEqual(set(result), {"code", "kind", "out", "err", "value"})

    def test_call_plain_file_with_args(self):
        script = self.home / "args"
        script.write_text("#!/bin/sh\nprintf '<%s>|<%s>' \"$@\"\n"); script.chmod(0o755)
        self.write("local function tool(s) s.out=aos.call('./args',{args={'a b','--stderr'},capture=true}).out end\n"
                   "return {{name='tool',fn=tool}}\n")
        self.assertEqual(self.run_tool().returncode, 0)
        self.assertEqual(self.state()["state"]["out"], "<a b>|<--stderr>")

    def test_call_json_rejects_args(self):
        (self.home / "one.json").write_text('{"argv":["true"]}')
        self.write("local function tool(s) aos.call_json('one.json',{args={'extra'}}) end\n"
                   "return {{name='tool',fn=tool}}\n")
        result = self.run_tool()
        self.assertEqual(result.returncode, 1)
        self.assertIn("inst 目標的參數寫在 inst.json 的 argv 裡", result.stderr)

    def test_call_dir_rejects_even_empty_args(self):
        (self.home / "child").mkdir()
        self.write("local function tool(s) aos.call_dir('child',{args={}}) end\n"
                   "return {{name='tool',fn=tool}}\n")
        result = self.run_tool()
        self.assertEqual(result.returncode, 1)
        self.assertIn("inst 目標的參數寫在 inst.json 的 argv 裡", result.stderr)

    def test_stderr_option_reaches_aos_exec(self):
        script = self.home / "noisy"
        script.write_text("#!/bin/sh\necho seen >&2\n"); script.chmod(0o755)
        self.write("local function tool(s) s.ok=aos.ok(aos.call('./noisy')) end\nreturn {{name='tool',fn=tool}}\n")
        result = self.run_tool("--stderr", "child.err")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.home / "child.err").read_text().strip(), "seen")

    def test_aos_exec_runs_program_to_done(self):
        self.write("local function a(s) s.a=1 end\nlocal function b(s) s.b=2 end\n"
                   "return {{name='a',fn=a},{name='b',fn=b}}\n")
        inst = self.home / "step.json"
        inst.write_text(json.dumps({"argv": [str(TOOL), str(self.prog)], "cwd": str(self.home),
                                    "stderr": "/dev/stderr"}))
        codes = [subprocess.run([str(EXEC), str(inst)]).returncode for _ in range(3)]
        self.assertEqual(codes, [0, 0, 100])


class JsonLuaTest(unittest.TestCase):
    def lua(self, expression):
        env = os.environ.copy(); env["LUA_PATH"] = LUA_PATH
        return subprocess.run([LUA, "-e", expression], text=True, capture_output=True,
                              check=False, env=env)

    def test_nested_round_trip(self):
        r = self.lua("local j=require'json'; local x=j.decode('{\"a\":[1,true,{\"b\":2}]}'); io.write(j.encode(x))")
        self.assertEqual((r.returncode, json.loads(r.stdout)), (0, {"a": [1, True, {"b": 2}]}))

    def test_empty_table_encodes_as_object(self):
        r = self.lua("local j=require'json'; io.write(j.encode({}))")
        self.assertEqual((r.returncode, r.stdout), (0, "{}"))

    def test_unicode_escape_surrogate_and_chinese(self):
        r = self.lua("local j=require'json'; io.write(j.decode([[\"\\u4e2d\\ud83d\\ude00文\"]]))")
        self.assertEqual((r.returncode, r.stdout), (0, "中😀文"))

    def test_null_uses_sentinel_and_round_trips(self):
        r = self.lua("local j=require'json'; local x=j.decode('{\"x\":null}'); assert(x.x==j.null); io.write(j.encode(x))")
        self.assertEqual((r.returncode, r.stdout), (0, '{"x":null}'))


if __name__ == "__main__":
    unittest.main()
