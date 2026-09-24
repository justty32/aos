"""kernel 與端到端測試共用的真 daemon／cpu 家及有上限輪詢。"""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

import aos_client
import aos_home
from _daemon_util import read_json, wait_for

CLI = Path(__file__).resolve().parents[2] / "cli"
PY = sys.executable


class KernelCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aos-kernel-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root / "K"
        self.daemon = self.root / "D"
        self.daemon.mkdir()
        self.write(self.daemon / "info.json", {
            "_metainfo": {"_type": "daemon", "_version": 1}, "poll_ms": 5,
            "restart_delay_ms": 50, "stop_wait_ms": 150, "kill_wait_ms": 150})
        self.groups = set()
        self.daemon_process = None
        self.addCleanup(self.cleanup)

    def write(self, path, obj):
        aos_home.write_json(path, obj)
        return str(path)

    def cli(self, *args, timeout=10):
        """cli(子命令, K, 其他…)：第二個參數是 K 家時換成 --target K（09-24 fix-r4 起 K 不是位置參數）。"""
        args = [str(a) for a in args]
        if len(args) >= 2 and not args[1].startswith("-"):
            args = [args[0], "--target", args[1], *args[2:]]
        return self.raw_cli(*args, timeout=timeout)

    def raw_cli(self, *args, timeout=10, cwd=None, env=None):
        """原樣把參數交給 aos-kernel，不替你補 --target。"""
        return subprocess.run([PY, str(CLI / "aos-kernel"), *map(str, args)], cwd=cwd, env=env,
                              stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout)

    def good_cli(self, *args, timeout=10):
        result = self.cli(*args, timeout=timeout)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def initialize(self, cpus=None, **settings):
        config = self.write(self.root / "kernel-config.json", {"cpus": {"0": {}, "1": {}, "2": {}}})
        self.good_cli("init", self.home, "--config", config)
        self.info = read_json(self.home / "info.json")
        self.info.update(cpus=cpus or {"k": {"pool": "kernel"}, "0": {}, "llm": {"pool": "llm"}},
                         tick_ms=5, interval_ms=5, bad_after=3)
        self.info.update(settings)
        self.write(self.home / "info.json", self.info)

    def start_daemon(self):
        log = open(self.root / "daemon.log", "ab")
        self.addCleanup(log.close)
        self.daemon_process = subprocess.Popen(
            [PY, str(CLI / "aos-daemon"), "boot", "--target", str(self.daemon)],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=log, start_new_session=True)
        wait_for(lambda: self.dstate().get("pid") == self.daemon_process.pid)

    def boot(self):
        self.good_cli("boot", self.home, "--daemon-target", self.daemon)
        self.info = read_json(self.home / "info.json")
        wait_for(lambda: self.state().get("last_seq", 0) >= 1)

    def setup_running(self, **settings):
        self.initialize(**settings)
        self.start_daemon()
        self.boot()

    def state(self):
        return read_json(self.home / "state.json", {})

    def dstate(self):
        return read_json(self.daemon / "state.json", {})

    def call(self, method, params=None, **kwargs):
        return aos_client.call(self.home, method, params, timeout_ms=5000, poll_ms=5, **kwargs)

    def add(self, target, name="job", **options):
        response = self.call("add", dict(target=str(target), name=name, **options))
        self.assertEqual(response.get("result", {}).get("name"), name, response)
        return response

    def job(self, source="pass", name="job", **extra):
        return self.write(self.root / (name + ".json"), dict(argv=[PY, "-c", source], **extra))

    def kernel_stop(self):
        self.good_cli("halt", self.home)
        wait_for(lambda: self.state().get("phase") == "stopped", timeout=8)
        wait_for(lambda: not self.dstate().get("children"), timeout=8)

    def daemon_stop(self):
        aos_home.post_request(self.daemon, aos_client.new_name("stop"), {"jsonrpc": "2.0", "method": "stop"})
        self.assertEqual(self.daemon_process.wait(timeout=5), 0)

    def cleanup(self):
        daemon = self.daemon_process
        if daemon is not None and daemon.poll() is None:
            try:
                daemon.terminate()
                daemon.wait(timeout=4)
            except subprocess.TimeoutExpired:
                self.groups.update(child["pid"] for child in self.dstate().get("children", {}).values())
                daemon.kill()
                daemon.wait(timeout=4)
        for pid in self.groups:
            try:
                os.killpg(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def isolated_test(module, classname, method):
    """把會製造孤兒的单條測試放進自己當 init 的 driver，連 zombie 都收乾淨。"""
    script = r'''
import ctypes, os, signal, sys, time, unittest
if ctypes.CDLL(None,use_errno=True).prctl(36,1,0,0,0):
    raise OSError(ctypes.get_errno(),'prctl')
os.environ['AOS_TEST_SUBREAPER']='1'
suite=unittest.defaultTestLoader.loadTestsFromName(sys.argv[1])
result=unittest.TextTestRunner().run(suite)
until=time.monotonic()+3
while time.monotonic()<until:
    try: pid,_=os.waitpid(-1,os.WNOHANG)
    except ChildProcessError: break
    if not pid: time.sleep(.005)
sys.exit(not result.wasSuccessful())
'''
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(CLI.parent / "lib"), str(Path(__file__).parent)]))
    return subprocess.run([PY, "-c", script, "%s.%s.%s" % (module, classname, method)],
                          capture_output=True, text=True, env=env, timeout=20)
