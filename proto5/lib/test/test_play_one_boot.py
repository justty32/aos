"""試玩 one-boot（proto5/notes/play/2026-09-24-one-boot-opus.md）挖到的七件，各一條以上。

真 daemon＋真 tick（沿用 test_one_boot 的 OneBootCase）。
"""
import json
import os
from pathlib import Path
import signal
import subprocess
import time

import aos_client
import aos_home
from _kernel_util import CLI, PY, read_json, wait_for
from test_one_boot import OneBootCase, pid_alive


class PlayFixes(OneBootCase):
    def aos(self, *args, timeout=40):
        env = dict(os.environ, AOS_KERNEL_HOME=str(self.home))
        return subprocess.run([PY, str(CLI / "aos"), *args], env=env, capture_output=True, text=True, timeout=timeout)

    # 1. ack 印一行
    def test_ack_says_what_happens(self):
        self.setup_running()
        out = self.good_cli("add", self.home, self.job("pass", "one"), "--once").stdout.split()
        name = out[0]
        aos_client.wait_response(self.home, name, timeout_ms=8000, poll_ms=5)
        result = self.good_cli("ack", self.home, name)
        self.assertIn("acked %s" % name, result.stdout)
        self.assertIn("下一格", result.stdout)
        wait_for(lambda: not (self.home / "responses" / name).exists())

    # 2. check 提早看到池名被別的 kernel 用了
    def test_check_reports_pool_owned_by_another_kernel(self):
        self.initialize()
        self.start_daemon()
        other = self.root / "K-other"
        pool = self.daemon / "pools" / self.dpool("default")
        pool.mkdir(parents=True)
        aos_home.write_json(pool / "pool.json", {"pool": "default", "owner": str(other), "count": 1, "skip": [], "ver": 1})
        result = self.cli("check", self.home)
        self.assertEqual(result.returncode, 1, result.stdout)
        line = [l for l in result.stdout.splitlines() if "pools/default" in l][0]
        self.assertTrue(line.startswith("bad"), line)
        self.assertIn(str(other), line)
        self.assertIn("dpool", line)

    def test_check_compares_owner_like_daemon(self):
        """astra 第二輪必修 1：daemon 比 owner 字串；owner 是「K/」這種寫法也算別人（daemon 會回 NameTaken），check 要一樣報。"""
        self.initialize()
        pool = self.daemon / "pools" / self.dpool("default")
        pool.mkdir(parents=True)
        aos_home.write_json(pool / "pool.json", {"pool": "default", "owner": str(self.home) + "/", "count": 1,
                                                 "skip": [], "ver": 1})
        result = self.cli("check", self.home)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("pools/default", result.stdout)

    def test_down_reports_what_stop_saw(self):
        """astra 第二輪必修 2：down 照 halt 自己回報的結果印；daemon 在但沒登記＝「沒登記替它開 tick」。"""
        self.initialize()
        up = subprocess.run([PY, str(CLI / "aos"), "up"], env=dict(os.environ, AOS_KERNEL_HOME=str(self.home)),
                            capture_output=True, text=True, timeout=40)
        self.assertEqual(up.returncode, 0, up.stderr)
        aos_home.post_request(self.daemon, aos_client.new_name("off"),
                              {"jsonrpc": "2.0", "method": "tick", "params": {"home": str(self.home), "off": True}})
        import aos_daemon_ticks
        wait_for(lambda: aos_daemon_ticks.peek(self.daemon, self.home) is None)
        down = self.aos("down", "--keep-daemon")
        self.assertEqual(down.returncode, 0, down.stderr)
        self.assertIn("daemon 沒登記替它開 tick", down.stdout)
        self.assertIn("留著（--keep-daemon）", down.stdout)
        # 收尾：重新 up 再正常 down
        self.assertEqual(self.aos("up").returncode, 0)
        self.assertIn("剛停", self.aos("down").stdout)
        self.kill_leftovers()

    def test_check_quiet_when_pool_is_ours(self):
        self.setup_running()
        self.wait_running("default", 1)
        result = self.cli("check", self.home)
        self.assertNotIn("pools/default", result.stdout)

    # 3. daemon 被 kill -9 之後 ls 前後一致
    def test_ls_after_daemon_killed_is_consistent(self):
        self.setup_running()
        self.wait_running("default", 1)
        wait_for(lambda: "running 1" in self.good_cli("ls", self.home).stdout)
        self.daemon_process.kill()
        self.daemon_process.wait(timeout=5)
        text = self.good_cli("ls", self.home).stdout
        lines = text.splitlines()
        self.assertTrue(lines[0].startswith("health daemon 沒在跑"), lines[0])
        self.assertIn("其實沒在跑", lines[1])
        self.assertIn("tick 沒人開（daemon 沒在跑", lines[2])
        pool = [l for l in lines if l.strip().startswith("default")][0]
        self.assertIn("不明（daemon 沒在跑", pool)
        self.assertNotIn("running 1 pending", pool)

    # 5. aos down 分「剛停／本來就停」，崩過的講清楚
    def test_aos_down_twice_and_after_crash(self):
        self.initialize()
        self.assertEqual(self.aos("up").returncode, 0)
        first = self.aos("down")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn("剛停", first.stdout)
        second = self.aos("down")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("本來就停了", second.stdout)
        self.assertIn("本來就沒在跑", second.stdout)
        self.assertNotIn("剛停", second.stdout)
        # 崩過：daemon 被 kill -9，帳本還寫 running
        self.assertEqual(self.aos("up").returncode, 0)
        pid = read_json(self.daemon / "state.json")["pid"]
        os.kill(pid, signal.SIGKILL)
        wait_for(lambda: not pid_alive(pid))
        crashed = self.aos("down")
        self.assertEqual(crashed.returncode, 0, crashed.stderr)
        self.assertIn("沒在跑：帳本還寫 running", crashed.stdout)
        self.assertIn("下次 aos up 會接上", crashed.stdout)
        self.assertEqual(self.aos("up").returncode, 0)                     # 真的接得上
        self.assertEqual(self.aos("down").returncode, 0)
        self.kill_leftovers()

    # 6. daemon.log 有開機、停機、崩過再開的紀錄
    def test_daemon_log_has_boot_crash_and_stop_lines(self):
        self.initialize()
        self.assertEqual(self.aos("up").returncode, 0)
        pid = read_json(self.daemon / "state.json")["pid"]
        os.kill(pid, signal.SIGKILL)
        wait_for(lambda: not pid_alive(pid))
        self.assertEqual(self.aos("up").returncode, 0)
        self.assertEqual(self.aos("down").returncode, 0)
        log = (self.daemon / "daemon.log").read_text()
        boots = [l for l in log.splitlines() if "aos-daemon: Boot:" in l]
        self.assertEqual(len(boots), 2, log)
        self.assertNotIn("沒正常停", boots[0])
        self.assertIn("上一任 pid %d 沒正常停" % pid, boots[1])
        self.assertEqual(len([l for l in log.splitlines() if "aos-daemon: Stopped:" in l]), 1, log)

    # 4. daemon 被殺時舊 cpu 的去留（刻意的）：新 daemon 先收上一任的孩子、死透才拉新的，不會新舊並存
    def test_new_daemon_waits_for_old_cpu_before_spawning(self):
        self.setup_running(pools={"default": {"count": 1}})
        self.wait_running("default", 1)
        old = self.kid_pid("default", 0)
        # 讓舊 cpu 手上有一件做很久的工作
        slow = self.job("import time; time.sleep(30)", "slow")
        sent = aos_client.submit(self.home, "add", {"target": slow, "name": "slow", "once": True})
        wait_for(lambda: (read_json(self.cpu_home("default", 0) / "state.json", {}) or {}).get("current"))
        self.daemon_process.kill()
        self.daemon_process.wait(timeout=5)
        time.sleep(.3)
        self.assertTrue(pid_alive(old))                                     # daemon 死了，孩子不跟著死（刻意）
        self.start_daemon()
        # 新的一出現就當場看舊的還在不在（astra 第二輪建議 3：不能等一下才查）
        seen = []
        def spawned():
            pid = self.kid_pid("default", 0)
            if pid not in (None, old):
                seen.append(pid_alive(old))
                return True
            return False
        wait_for(spawned, timeout=20)
        self.assertEqual(seen, [False])                                     # 新的拉起來那一刻舊的已經不在
        # 被打斷的 once 單：舊 cpu 收到 TERM 停掉手上那件、照常回音（stopped: true）；沒寫成的新主人對帳回 Interrupted。都不重派。
        reply = aos_client.wait_response(self.home, sent, timeout_ms=15000, poll_ms=5)
        stopped = (reply.get("result") or {}).get("stopped") is True
        interrupted = ((reply.get("error") or {}).get("data") or {}).get("code") == "Interrupted"
        self.assertTrue(stopped or interrupted, reply)
