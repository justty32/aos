"""任務控制（ctl.json：kill／restart／reload／run）、kill 範圍（Q1）、lost 前的身分掃描（NODE＋TID＋RUN）、掛載。"""
import os, sys  # noqa: E401
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # tests/：base、_matrix
import os
import hashlib
import signal
import subprocess
from unittest.mock import patch
import time
import unittest

from base import HERE, SLEEP, CoreCase
import aos7_proc
import aos7_task
from aos7_fs import read_json, write_json

# 留一個 setsid 的孫程序（新 session、環境變數照樣是這個任務的），pid 寫進槽裡的 gc.pid
LEAVE_GC = 'setsid sleep 60 > /dev/null 2>&1 & echo $! > "$AOS7_TASK/gc.pid"; '


def gc_pid(node, slot, wait=None):
    p = os.path.join(aos7_task.slot_dir(node, slot), "gc.pid")
    end = time.monotonic() + (wait or 0)
    while True:
        try:
            with open(p) as f:
                v = f.read().strip()
            if v:
                return int(v)
        except OSError:
            pass
        if time.monotonic() >= end:
            return None
        time.sleep(0.02)


class TestCtl(CoreCase):
    """〔core〕任務控制 kill（run 必填）。restart／reload 的案例搬到 modules/control/tests/，aos7-ctl task 那項搬到 modules/tools/tests/。"""
    def write_ctl(self, node, slot, **ctl):
        write_json(os.path.join(self.slot(node, slot), "ctl.json"), dict({"by": "test"}, **ctl))

    def done(self, node, slot):
        return read_json(os.path.join(self.slot(node, slot), "ctl-done.json"))

    def test_kill_at_tock_reported_by_ctl(self):
        """〔core〕"""
        node = self.mknode("a", [{"name": "s", "argv": SLEEP}])
        self.tick()
        self.wait_pid(node, "s")
        self.write_ctl(node, "s", op="kill", run=1)
        lr = self.tock()
        d = self.done(node, "s")
        self.assertTrue(d["result"]["ok"], d)
        self.assertEqual(d["result"]["run"], "s#1")
        self.assertEqual(lr["ended"], [{"run": "s#1", "code": -15, "by_ctl": {"op": "kill", "by": "test"}}])

    def test_kill_with_stale_run_refused(self):
        """〔core〕"""
        node = self.mknode("a", [{"name": "s", "mode": "keep", "argv": SLEEP}])
        self.tick()
        self.wait_pid(node, "s")
        self.write_ctl(node, "s", op="kill", run=7)
        self.tock()
        d = self.done(node, "s")
        self.assertFalse(d["result"]["ok"])
        self.assertIn("已經不是現在的", d["result"]["msg"])
        self.assertEqual(self.view(node, "s", 1).state, aos7_task.LIVE)

    def test_bad_ctl_gets_failed_receipt(self):
        """〔core〕"""
        node = self.mknode("a", [{"name": "s", "argv": SLEEP}])
        self.tick()
        with open(os.path.join(self.slot(node, "s"), "ctl.json"), "w") as f:
            f.write("[1, 2")
        self.tock()
        self.assertFalse(self.done(node, "s")["result"]["ok"])
        self.assertFalse(os.path.exists(os.path.join(self.slot(node, "s"), "ctl.json")))

    def test_k1_runner_starting_keeps_kill_request(self):
        """交接中的 runner 不能先回成功；放行後同一請求再收。"""
        hook = os.path.join(self.root, "runner_hooks.py")
        release = os.path.join(self.root, "release")
        with open(hook, "w") as f:
            f.write("""import importlib.util, os, time
spec = importlib.util.spec_from_file_location("real_hooks", %r)
real = importlib.util.module_from_spec(spec)
spec.loader.exec_module(real)
for name in dir(real):
    if callable(getattr(real, name)):
        globals()[name] = getattr(real, name)
def test_point(name):
    real.test_point(name)
    if name in os.environ.get("AOS7_TEST_RUNNER_HANG", "").split(","):
        release = os.environ["AOS7_TEST_RUNNER_RELEASE"]
        open(release + ".entered", "w").close()
        end = time.monotonic() + 30
        while not os.path.exists(release) and time.monotonic() < end:
            time.sleep(0.02)
""" % os.path.join(HERE, "_hooks.py"))
        node = self.mknode("a", [{"name": "s", "argv": ["sh", "-c", 'sleep 2; touch "$AOS7_TASK/side"']}])
        self.tick(env={"AOS7_TEST_HOOKS": hook, "AOS7_TEST_RUNNER_HANG": "runner-before-popen",
                       "AOS7_TEST_RUNNER_RELEASE": release})
        sd = self.slot(node, "s")
        self.wait_for(lambda: os.path.exists(release + ".entered") or os.path.exists(os.path.join(sd, "pid.json")))
        runner = self.birth(node, "s")["runner"]
        self.assertTrue(aos7_proc.pid_alive(runner["pid"]))
        self.assertFalse(os.path.exists(os.path.join(sd, "pid.json")))
        self.write_ctl(node, "s", op="kill", run=1)
        self.tock()
        d = self.done(node, "s")["result"]
        self.assertFalse(d["ok"], d)
        self.assertTrue(d["msg"].startswith("unknown"), d)
        self.assertTrue(os.path.exists(os.path.join(sd, "ctl.json")))
        self.tick()   # 前一次 tock 已關回合；交接仍卡著，先開下一回合供 tock 重試
        open(release, "w").close()
        self.wait_pid(node, "s")
        self.tock()
        self.assertTrue(self.done(node, "s")["result"]["ok"])
        self.wait_for(lambda: not aos7_proc.env_procs(node, "s", 1, runners=True))
        self.assertFalse(os.path.exists(os.path.join(sd, "ctl.json")))
        time.sleep(3)
        self.assertFalse(os.path.exists(os.path.join(sd, "side")))

    def test_k1_late_setsid_child_is_collected(self):
        """SIGTERM 才出生的新 session 子程序也收乾淨，keep 不雙活。"""
        cmd = 'trap \'setsid sleep 60 </dev/null >/dev/null 2>&1 & echo $! > "$AOS7_TASK/late.pid"; exit 0\' TERM; sleep 60 & wait'
        node = self.mknode("a", [{"name": "s", "mode": "keep", "argv": ["sh", "-c", cmd]}])
        self.tick()
        self.wait_pid(node, "s")
        # shell 已走到 wait，才送 TERM（避免在 trap 設定前打到它）。
        self.wait_for(lambda: len(aos7_proc.env_procs(node, "s", 1)) >= 2)
        self.write_ctl(node, "s", op="kill", run=1)
        self.tock()
        self.assertTrue(self.done(node, "s")["result"]["ok"])
        late = os.path.join(self.slot(node, "s"), "late.pid")
        self.wait_for(lambda: os.path.exists(late))
        with open(late) as f:
            pid = int(f.read())
        self.wait_for(lambda: not aos7_proc.pid_alive(pid), 3, "快照後出生的 setsid 子程序還活著")
        self.assertEqual(aos7_proc.env_procs(node, "s", 1), [])
        self.assertEqual(self.tick()["started"], ["s#2"])
        self.assertEqual(aos7_proc.env_procs(node, "s", 1, runners=True), [])

    def test_k1_task_argument_is_not_runner(self):
        """argv[2] 以後的 aos7-run 字樣不影響任務身分。"""
        node = self.mknode("a", [{"name": "s", "argv": ["sh", "-c", "sleep 60 & wait", "x/aos7-run"]}])
        self.tick()
        pj = self.wait_pid(node, "s")
        self.assertIn(pj["pid"], aos7_proc.env_procs(node, "s", 1))
        self.write_ctl(node, "s", op="kill", run=1)
        self.tock()
        self.assertTrue(self.done(node, "s")["result"]["ok"])
        self.assertFalse(aos7_proc.pid_alive(pj["pid"]))

    def test_k1_inherited_aos_environment_is_cleared(self):
        """繼承的 AOS7_* 只放行 LiteLLM 金鑰，核心身分照樣傳；測試不落地金鑰。"""
        probe = '''import hashlib, json, os
from pathlib import Path
key = os.environ.get("AOS7_LITELLM_KEY", "")
result = {"key_sha": hashlib.sha256(key.encode()).hexdigest(),
          "names": sorted(k for k in os.environ if k.startswith("AOS7_")),
          "run": os.environ["AOS7_RUN"]}
Path(os.environ["AOS7_TASK"], "env.json").write_text(json.dumps(result))
'''
        node = self.mknode("a", [{"name": "s", "argv": [sys.executable, "-B", "-c", probe]}])
        self.tick(env={"AOS7_SUBROOT": "/nope", "AOS7_FOO": "1", "AOS7_LITELLM_KEY": "fx1-test-key",
                       "AOS7_LITELLM_URL": "http://example.invalid/v1", "AOS7_TEST_PROBE": "1"})
        self.wait_ended(node, "s", 1)
        env = read_json(os.path.join(self.slot(node, "s"), "env.json"))
        self.assertEqual(env["key_sha"], hashlib.sha256(b"fx1-test-key").hexdigest())
        self.assertEqual(set(env["names"]), {"AOS7_ROOT", "AOS7_NODE", "AOS7_NODE_ID", "AOS7_TASK",
                                            "AOS7_TID", "AOS7_RUN", "AOS7_LITELLM_KEY"})
        self.assertEqual(env["run"], "1")

    def test_k1_birth_read_failure_keeps_run_number(self):
        """birth 讀失敗的 exit 仍帶環境的整數 run。"""
        node = self.mknode("a")
        sd = self.slot(node, "s")
        os.makedirs(sd)
        write_json(os.path.join(sd, "birth.json"), {"run": 1, "argv": ["true"]})
        hits = os.path.join(self.root, "hits")
        self.prog("aos7-run", sd, rc=1, env={"AOS7_RUN": "1", "AOS7_NODE": node,
                  "AOS7_TEST_FAULT": "open:*birth.json:EIO", "AOS7_TEST_FAULT_HITS": hits})
        ex = self.exit_of(node, "s")
        self.assertEqual(ex["run"], 1)
        self.assertIs(type(ex["run"]), int)
        self.assertEqual(ex["code"], 127)
        with open(hits) as f:
            self.assertIn("open\tEIO\t", f.read())

    def test_k1_node_known_pgid_is_revalidated(self):
        """裸 pgid 不能殺外人的群組；同 node 群組照樣收。"""
        node = self.mknode("a")
        victim = subprocess.Popen(SLEEP, start_new_session=True)
        owned = subprocess.Popen(SLEEP, start_new_session=True,
                                 env=dict(os.environ, AOS7_NODE=node, AOS7_TID="x", AOS7_ROOT=self.root))
        self.procs.extend([victim, owned])
        _, clean = aos7_proc.kill_node([node], known_pgids=[victim.pid, owned.pid])
        self.assertTrue(clean)
        self.assertIsNone(victim.poll())
        self.wait_for(lambda: owned.poll() is not None)

    def test_k1_stat_non_utf8_comm(self):
        """stat 的 comm 不是 UTF-8 也能解析、掃描。"""
        def read(pid, name, binary=False):
            data = b"123 (a\xffb) S 1 123 123 0 0"
            return data if binary else data.decode("utf-8")
        with patch.object(aos7_proc, "_read_proc", side_effect=read), patch.object(aos7_proc, "all_pids", return_value=[123]):
            self.assertEqual(aos7_proc.stat_of(123), ("S", 1, 123))
            self.assertEqual(aos7_proc._table(), {123: ("S", 1, 123)})

    def test_k1_starting_runner_unknown_does_not_scan(self):
        """runner 未記上或認不出時，只留請求，不掃描、不殺。"""
        node = self.mknode("a")
        sd = self.slot(node, "s")
        for runner in (None, {"pid": 123, "starttime": None}):
            with self.subTest(runner=runner), patch.object(aos7_proc, "KILL_GRACE", 0), \
                    patch.object(aos7_proc, "same_process", return_value=aos7_proc.UNKNOWN), \
                    patch.object(aos7_proc, "kill_identity") as kill:
                v = aos7_task.View(state=aos7_task.LIVE, run=1, birth={"runner": runner})
                ok, msg = aos7_task.kill_run(sd, node, "s", v)
                self.assertFalse(ok)
                self.assertTrue(msg.startswith("unknown"))
                kill.assert_not_called()

    def test_k1_rescan_has_three_round_limit(self):
        """持續冒出相符程序不能回成功，run 與 node 都最多補收三輪。"""
        node = self.mknode("a")
        for call in (lambda: aos7_proc.kill_identity(node, "s", 1)[0],
                     lambda: aos7_proc.kill_node([node])[1]):
            with patch.object(aos7_proc, "env_procs", return_value=[123]) as scan, \
                    patch.object(aos7_proc, "groups_of", return_value={123}), \
                    patch.object(aos7_proc, "kill_groups", return_value=True) as kill:
                self.assertFalse(call())
                self.assertEqual(kill.call_count, 4)   # 初收＋三輪補收
                self.assertEqual(scan.call_count, 5)   # 初掃＋三輪＋最後確認

    def test_k1_node_unknown_still_uses_known_groups(self):
        """掃描不能重驗時照原契約打記著的群組，但不聲稱乾淨。"""
        from aos7_fs import Unknown
        with patch.object(aos7_proc, "group_is_node", side_effect=Unknown("test", kind="proc")), \
                patch.object(aos7_proc, "kill_groups", return_value=True) as kill:
            self.assertEqual(aos7_proc.kill_node([self.root], known_pgids=[123]), (1, False))
            kill.assert_called_once_with({123})

    def test_k1_node_rejected_pgid_not_readded_on_unknown(self):
        """已確定是外人的 pgid，後面掃描不完整也不打。"""
        from aos7_fs import Unknown
        with patch.object(aos7_proc, "group_is_node", side_effect=lambda g, n: g != 123), \
                patch.object(aos7_proc, "env_procs", side_effect=Unknown("test", kind="proc")), \
                patch.object(aos7_proc, "kill_groups", return_value=True) as kill:
            self.assertEqual(aos7_proc.kill_node([self.root], known_pgids=[123, 456]), (1, False))
            kill.assert_called_once_with({456})

    def test_k1_rescan_kill_failure_not_clean(self):
        """補收那輪 SIGKILL 後確認不了，下一輪掃空也不能回乾淨。"""
        scans = iter([[123], []])
        with patch.object(aos7_proc, "env_procs", side_effect=lambda *a, **k: next(scans)), \
                patch.object(aos7_proc, "groups_of", return_value={123}), \
                patch.object(aos7_proc, "kill_groups", return_value=False):
            self.assertFalse(aos7_proc._kill_remaining(self.root, "s", 1))

    def test_k1_runner_alive_but_task_found_is_killed(self):
        """沒 pid.json、runner 還在，但相符的任務已經起來（例如 pid.json 寫不進去）：照常收，不永遠留請求。"""
        node = self.mknode("a")
        sd = self.slot(node, "s")
        with patch.object(aos7_proc, "KILL_GRACE", 0), \
                patch.object(aos7_proc, "same_process", return_value=aos7_proc.ALIVE), \
                patch.object(aos7_proc, "env_procs", return_value=[123]), \
                patch.object(aos7_proc, "kill_identity", return_value=(True, "killed 1 group(s)")) as kill:
            v = aos7_task.View(state=aos7_task.LIVE, run=1, birth={"runner": {"pid": 9, "starttime": 1}})
            self.assertEqual(aos7_task.kill_run(sd, node, "s", v), (True, "killed 1 group(s)"))
            kill.assert_called_once()


class TestKillRange(CoreCase):
    """〔core〕"""
    def test_kill_reaches_setsid_grandchild(self):
        node = self.mknode("a", [{"name": "g", "argv": ["sh", "-c", LEAVE_GC + "sleep 60"]}])
        self.tick()
        gc = gc_pid(node, "g", wait=5)
        self.assertTrue(aos7_proc.pid_alive(gc))
        write_json(os.path.join(self.slot(node, "g"), "ctl.json"), {"op": "kill", "run": 1})
        self.tock()
        self.wait_for(lambda: not aos7_proc.pid_alive(gc), 3, "setsid 的孫程序沒收到")

    def test_forged_pgid_not_killed(self):
        node = self.mknode("a", [{"name": "s", "argv": SLEEP}])
        import subprocess
        victim = subprocess.Popen(["sleep", "60"], start_new_session=True)
        self.procs.append(victim)
        self.tick()
        pj = self.wait_pid(node, "s")
        pj["pgid"] = victim.pid
        write_json(os.path.join(self.slot(node, "s"), "pid.json"), pj)
        write_json(os.path.join(self.slot(node, "s"), "ctl.json"), {"op": "kill", "run": 1})
        self.tock()
        self.assertIsNone(victim.poll())
        self.assertIn("不是這個任務的群組", read_json(os.path.join(self.slot(node, "s"), "ctl-done.json"))["result"]["msg"])

    def test_inst_kill_reaches_other_session(self):
        node = self.mknode("a", [{"name": "i", "inst": "s.inst.json"}])
        write_json(os.path.join(node, "s.inst.json"), {"argv": SLEEP})
        self.tick()
        pj = self.wait_pid(node, "i")
        self.wait_for(lambda: len(aos7_proc.groups_with_descendants(pj["pgid"])) >= 2)
        groups = aos7_proc.groups_with_descendants(pj["pgid"])
        write_json(os.path.join(self.slot(node, "i"), "ctl.json"), {"op": "kill", "run": 1})
        self.tock()
        self.assertFalse(any(aos7_proc.group_alive(g) for g in groups))


class TestIdentityScan(CoreCase):
    """〔core〕"""
    def test_lost_kills_leftover_before_keep_restarts(self):
        """runner 與任務主程序都被 kill -9，setsid 的孫程序還在：lost 判定前先身分掃描收掉它，keep 不雙開。"""
        node = self.mknode("a", [{"name": "k", "mode": "keep", "argv": ["sh", "-c", LEAVE_GC + "sleep 60"]}])
        self.tick()
        pj = self.wait_pid(node, "k")
        gc = gc_pid(node, "k", wait=5)
        runner = self.birth(node, "k")["runner"]["pid"]
        os.kill(runner, signal.SIGKILL)
        os.kill(pj["pid"], signal.SIGKILL)
        self.wait_for(lambda: not aos7_proc.pid_alive(pj["pid"]) and not aos7_proc.pid_alive(runner))
        self.assertTrue(aos7_proc.pid_alive(gc))
        lr = self.tock()
        self.assertEqual(lr["ended"], [{"run": "k#1", "code": None, "lost": True}])
        self.assertFalse(aos7_proc.pid_alive(gc), "lost 前沒收掉舊 run 的殘留")
        self.assertIn("note", self.exit_of(node, "k"))
        self.assertEqual(self.tick()["started"], ["k#2"])
        self.assertEqual(aos7_proc.env_procs(node, "k", 1, runners=True), [])

    def test_old_run_leftover_not_taken_as_new_run(self):
        """同一個槽上一個 run 留下的孫程序：不算這次的活任務、kill 這次也不打到它。"""
        node = self.mknode("a", [{"name": "e", "argv": ["sh", "-c",
                                                        'if [ "$AOS7_RUN" = 1 ]; then ' + LEAVE_GC + 'exit 0; fi; exec sleep 60']}])
        # exec：dash 不 exec 最後一個命令，不寫的話 run 2 是 sh＋sleep 兩個程序，下面「只有主程序」的斷言會多一個 pid
        self.tick()
        self.wait_ended(node, "e", 1)
        gc = gc_pid(node, "e", wait=5)
        self.assertTrue(aos7_proc.pid_alive(gc))
        self.tock()
        self.tick()
        pj = self.wait_pid(node, "e")
        self.assertEqual(pj["run"], 2)
        self.assertEqual(aos7_proc.env_procs(node, "e", 2), [pj["pid"]])
        # run 2 的主程序與 runner 死掉：身分掃描比 RUN，找不到這次的 → lost；run 1 的殘留不動
        os.kill(self.birth(node, "e")["runner"]["pid"], signal.SIGKILL)
        os.kill(pj["pid"], signal.SIGKILL)
        self.wait_for(lambda: not aos7_proc.pid_alive(pj["pid"]))
        time.sleep(0.1)
        lr = self.tock()
        self.assertIn({"run": "e#2", "code": None, "lost": True}, lr["ended"])
        self.assertNotIn("note", self.exit_of(node, "e"))
        self.assertTrue(aos7_proc.pid_alive(gc), "run 2 的 lost 判定打到了 run 1 的殘留")
        # 對 run 1 下的 kill（指定 run）不執行
        write_json(os.path.join(self.slot(node, "e"), "ctl.json"), {"op": "kill", "run": 1})
        self.tick()
        self.assertFalse(read_json(os.path.join(self.slot(node, "e"), "ctl-done.json"))["result"]["ok"])

    def test_runner_died_without_pid_json_is_lost(self):
        node = self.mknode("a")
        sd = self.slot(node, "x")
        dead = os.getpid() + 100000   # 不存在的 pid
        write_json(os.path.join(sd, "birth.json"), {"name": "x", "slot": "x", "run": 1, "round": 1,
                                                    "runner": {"pid": dead, "starttime": 1}})
        self.set_tasks(node, [{"name": "x", "argv": ["true"]}])
        write_json(os.path.join(node, ".aos", "round.json"), {"round": 1, "open": True})
        lr = self.tock()
        self.assertEqual(lr["ended"], [{"run": "x#1", "code": None, "lost": True}])

    def test_no_runner_young_birth_is_live_old_is_lost(self):
        node = self.mknode("a", [{"name": "x", "argv": ["true"]}])
        sd = self.slot(node, "x")
        write_json(os.path.join(sd, "birth.json"), {"name": "x", "slot": "x", "run": 1, "round": 1, "runner": None})
        self.assertEqual(aos7_task.judge(sd, node, "x", 2).state, aos7_task.LIVE)
        self.assertEqual(aos7_task.judge(sd, node, "x", 3).state, aos7_task.SUSPECT)


class TestMounts(CoreCase):
    """〔core〕"""
    def test_mounts_made_and_rebuilt_per_run(self):
        node = self.mknode("a", [{"name": "m", "argv": ["true"], "mounts": {"bob": "b/inbox", "bad/": "x"}}])
        self.tick()
        sd = self.slot(node, "m")
        self.assertTrue(os.path.islink(os.path.join(sd, "mnt", "bob")))
        self.assertTrue(os.path.isdir(os.path.join(self.root, "b", "inbox")))
        b = self.birth(node, "m")
        self.assertIn("at", b["mounts"]["bob"])
        self.wait_ended(node, "m", 1)
        self.tock()
        self.set_tasks(node, [{"name": "m", "argv": ["true"], "mounts": {"c": "c"}}])
        self.tick()
        self.assertEqual(sorted(os.listdir(os.path.join(sd, "mnt"))), ["c"])

    def test_mount_request_served(self):
        """執行中加掛：下一個 tick 審核、寫回條、建 mnt、在 birth 標 dyn；換 run 時照宣告重建（加掛的不帶過去，要帶用控制包 restart）。"""
        node = self.mknode("a", [{"name": "m", "mode": "keep", "argv": SLEEP}])
        os.makedirs(os.path.join(self.root, "z"))
        self.tick()
        sd = self.slot(node, "m")
        self.wait_pid(node, "m")
        write_json(os.path.join(sd, "mount-req", "z.json"), {"name": "z", "path": "z", "why": "t"})
        self.tock()
        self.tick()
        self.assertTrue(read_json(os.path.join(sd, "mount-done", "z.json"))["result"]["ok"])
        self.assertFalse(os.path.exists(os.path.join(sd, "mount-req", "z.json")))
        self.assertTrue(self.birth(node, "m")["mounts"]["z"].get("dyn"))
        write_json(os.path.join(sd, "ctl.json"), {"op": "kill", "run": 1})
        self.tock()
        self.tick()
        b = self.birth(node, "m")
        self.assertEqual(b["run"], 3)
        self.assertNotIn("z", b["mounts"])
        self.assertFalse(os.path.exists(os.path.join(sd, "mount-done")))   # 新 run 清掉


if __name__ == "__main__":
    unittest.main()
