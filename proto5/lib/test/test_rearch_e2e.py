"""重架構端到端：agent 交一次模型工作，再跑反覆行程直到 done_exit，依序停乾淨。

proto5-2：cpu 由池宣告拉起（default／llm 各 1 顆），孩子看 daemon 的 kids 檔；停完 daemon 那邊池全消失。
"""
import json
import os
from pathlib import Path

import aos_client
import aos_daemon_ticks
from _kernel_util import KernelCase, PY, read_json, wait_for


class RearchEndToEnd(KernelCase):
    def test_agent_llm_once_recurring_done_and_orderly_shutdown(self):
        tools = self.root / "fake-llm-bin"
        tools.mkdir()
        executable = tools / "llm-http"
        executable.write_text("#!%s\n" % PY + '''import json, os, sys
prompt = sys.stdin.read()
print(json.dumps({"answer": "假模型回答：" + prompt.strip(), "args": sys.argv[1:],
                  "cpu_pid": os.getppid(), "pid": os.getpid()}, ensure_ascii=False))
''')
        executable.chmod(0o755)
        path_env = {"$fmt": {"$val": str(tools) + ":${old}", "old": {"$env": "PATH"}}}
        self.setup_running({"default": {"count": 1}, "llm": {"count": 1, "envs": {"PATH": path_env}}})
        for pool in ("default", "llm"):   # one-boot：沒有 kernel 池，tick 由 daemon 直接開
            self.wait_running(pool, 1)
        cpu_pids = {pool: self.kid_pid(pool, 0) for pool in ("default", "llm")}
        daemon_pid = self.daemon_process.pid

        prompt = self.root / "question.txt"
        prompt.write_text("請說明這次交件。\n")
        answer_file = self.root / "answer.json"
        target = self.write(self.root / "ask.json", {
            "argv": ["llm-http", "--model", "offline-demo"],
            "stdin": str(prompt), "stdout": str(answer_file)})
        request = aos_client.new_name("agent")
        response = aos_client.call(self.home, "add", {
            "name": "agent-question", "target": target, "once": True, "pool": "llm"},
            name=request, timeout_ms=5000, poll_ms=5, acknowledge=False)
        self.assertEqual(response["id"], request[:-5])
        result = response["result"]
        self.assertEqual(set(result), {"code", "kind", "timed_out", "stopped", "ms"})
        self.assertEqual((result["code"], result["kind"]), (0, "child"))
        self.assertFalse(result["timed_out"])
        self.assertFalse(result["stopped"])
        answer = read_json(answer_file)
        self.assertEqual(answer["answer"], "假模型回答：請說明這次交件。")
        self.assertEqual(answer["args"], ["--model", "offline-demo"])
        self.assertEqual(answer["cpu_pid"], cpu_pids["llm"])
        response_file = self.home / "responses" / request
        self.assertTrue(response_file.exists())
        self.write(self.root / "agent-receipt.json", {"response": response, "answer": answer})
        acknowledgment = aos_client.ack(self.home, request)
        wait_for(lambda: not response_file.exists() and
                 not (self.home / "requests" / acknowledgment).exists())

        counter = self.root / "counter.txt"
        workers = self.root / "repeat-pids.txt"
        source = '''import os
from pathlib import Path
counter = Path(%r)
number = int(counter.read_text()) + 1 if counter.exists() else 1
counter.write_text(str(number))
with open(%r, 'a') as f: f.write(str(os.getpid()) + '\\n')
raise SystemExit(100 if number == 3 else 0)
''' % (str(counter), str(workers))
        repeat = self.job(source, name="repeat")
        added = self.good_cli("add", self.home, repeat, "--name", "repeat", "--interval-ms", "5")
        self.assertIn("repeat", added.stdout)
        wait_for(lambda: self.state().get("procs", {}).get("repeat", {}).get("status") == "done")
        process = self.state()["procs"]["repeat"]
        self.assertEqual((process["runs"], process["fails"]), (3, 0))
        self.assertEqual(counter.read_text(), "3")

        self.assertIsNotNone(aos_daemon_ticks.peek(str(self.daemon), self.home))  # 停之前 daemon 替它開 tick
        self.kernel_stop()
        self.assertEqual(self.state()["phase"], "stopped")
        self.assertEqual(list((self.daemon / "pools").iterdir()), [])
        wait_for(lambda: aos_daemon_ticks.peek(str(self.daemon), self.home) is None)  # 停好那格撤了 tick 登記
        self.daemon_stop()
        all_pids = {*cpu_pids.values(), daemon_pid, answer["pid"],
                    *(int(pid) for pid in workers.read_text().splitlines())}
        for pid in all_pids:
            with self.subTest(pid=pid):
                with self.assertRaises(ProcessLookupError):
                    os.kill(pid, 0)
