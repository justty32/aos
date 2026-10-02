"""帳號模組驗收（plan m3m-daemon-modules.md 模組五）。

本檔：假 root namespace 裡真的切帳號（Runs、Errors、WithReload、WithCgroup、RootProtocol）。

兩組：
- `Names`、`Policies`、`NotRoot`：一般帳號就能跑（名單比對、設定錯、沒用 root 開回 1）。
- 其餘：用 `unshare --user --map-root-user --map-auto` 當假 root——namespace 裡自己是 root，
  UID 1～65536 對到 /etc/subuid 的子 UID，所以 `/etc/passwd` 裡的系統帳號（預設帳號、daemon、nobody）
  切得過去。拿不到（沒有 subuid、沒有那幾個帳號）就整組跳過，要等真 root 手動驗。
  別的 UID 進不了 /home/lorkhan（700），所以整份 src/py 先複製到 /tmp 底下 755 的資料夾再跑；
  測試資料夾 chmod 777。預設帳號用 http（Arch）；沒有就依序試 www-data（Debian／Ubuntu）、bin、sys。
  別的帳號用 daemon 與 nobody；補充群組照系統查（Arch 的 daemon 有 adm、bin，Ubuntu 沒有）。
  `Policies` 也要這三個帳號存在，找不到就跳過。
"""
import json
import os
import pwd
import signal
import stat
import subprocess
import threading
import unittest

from _util import PY
from _daemon_util import CLEAN_ENV, sh
from _cgroup_util import SCOPE, SKIP as CG_SKIP, alive
from _account_util import DEFAULT, NS, NsCase, OTHER, THIRD


WHO = 'echo "$(id -un) $(id -G) $HOME $USER $LOGNAME" > who.%s'


class Runs(NsCase):

    def test_users_groups_env(self):
        for n in ("a", "b", "c"):
            self.inst(sh(WHO % n), n + ".json")
        _, out, err = self.start_ns(self.cfg({"a.json": {}, "b.json": {"account": {"user": OTHER}},
                                              "c.json": {"account": {"user": THIRD}}}))
        self.wait_for(lambda: all(self.exists("who." + n) for n in "abc"), timeout=8)
        a, b, c = self.who("a"), self.who("b"), self.who("c")
        self.assertEqual((a["user"], b["user"], c["user"]), (DEFAULT, OTHER, THIRD))
        pb = pwd.getpwnam(OTHER)
        want = {str(g) for g in os.getgrouplist(OTHER, pb.pw_gid)}
        self.assertEqual(b["groups"], want)                       # 補充群組照 initgroups
        for name, w in ((DEFAULT, a), (OTHER, b), (THIRD, c)):
            self.assertEqual((w["home"], w["USER"], w["LOGNAME"]), (pwd.getpwnam(name).pw_dir, name, name))
        self.wait_for(lambda: all(self.results(out, n + ".json") == [0] for n in "abc"))
        self.assertEqual(err, [])

    def test_main_dropped_root_side_root(self):
        self.inst(sh("true"), "a.json")
        p, out, _ = self.start_ns(self.cfg({"a.json": {}}, control={"socket": "./aos.sock"}))
        self.wait_for(lambda: self.results(out, "a.json") == [0])
        main_uid = self.uid_line(p.pid)
        self.assertEqual(len(set(main_uid)), 1)                    # real／effective／saved／fs 都一樣
        self.assertNotIn(str(os.getuid()), main_uid)               # 不是 namespace 的 root（外面是自己）
        roots = self.children(p.pid)
        self.assertEqual(len(roots), 1)                            # root 端
        self.assertEqual(set(self.uid_line(roots[0])), {str(os.getuid())})
        st = os.stat(os.path.join(self.d, "aos.sock"))
        self.assertEqual(stat.S_IMODE(st.st_mode), 0o666)
        self.assertEqual(str(st.st_uid), main_uid[0])              # socket 歸預設帳號

    def test_outputs_owned_by_default(self):
        self.inst(sh("echo hi; echo oops >&2", stdout={"$opt": "inherit"}, stderr={"$opt": "inherit"}), "b.json")
        p, out, _ = self.start_ns(self.config({
            "interval_ms": 100000, "exec_out_path": "out.log", "exec_err_path": "err.log",
            "modules": {"account": {"user": DEFAULT, "allow": [OTHER]}},
            "insts": {"b.json": {"account": {"user": OTHER}}}}))
        self.wait_for(lambda: self.results(out, "b.json") == [0])
        self.assertIn("hi", self.read("out.log"))
        self.assertIn("oops", self.read("err.log"))
        self.assertEqual(os.stat(os.path.join(self.d, "out.log")).st_uid, int(self.uid_line(p.pid)[0]))

    def test_exit_code_and_signal(self):
        self.inst(sh("exit 7"), "x.json")
        self.inst(sh("kill -TERM $$"), "k.json")
        _, out, _ = self.start_ns(self.cfg({"x.json": {"account": {"user": OTHER}},
                                            "k.json": {"account": {"user": OTHER}}}))
        self.wait_for(lambda: self.results(out, "x.json") == [7] and self.results(out, "k.json") == [143])

    def test_sudo_user_default(self):
        self.inst(sh(WHO % "a"), "a.json")
        self.start_ns(self.cfg({"a.json": {}}, account={}), env=dict(CLEAN_ENV, SUDO_USER=DEFAULT))
        self.wait_for(lambda: self.exists("who.a"))
        self.assertEqual(self.who("a")["user"], DEFAULT)

    def test_ctl_from_other_user(self):
        # 別的帳號的任務連得上主程式（預設帳號）開的 socket（666）
        self.inst(sh('"$PY" "$CTL" status > st.json', envs={"PY": PY, "CTL": os.path.join(self.copy, "py", "bin",
                                                                                            "aos-ctl")}), "b.json")
        _, out, _ = self.start_ns(self.cfg({"b.json": {"account": {"user": OTHER}}},
                                           control={"socket": "./aos.sock"}))
        self.wait_for(lambda: self.results(out, "b.json") == [0])
        self.assertEqual(json.loads(self.read("st.json"))["inst"], "b.json")


class Errors(NsCase):

    def setUp(self):
        super().setUp()
        self.inst(sh("true"), "a.json")

    def test_config_errors_exit_1(self):
        cases = [
            ({"a.json": {"account": {"user": "root"}}}, None, "名單不准"),
            ({"a.json": {"account": {"user": "ftp"}}}, None, "名單不准"),
            ({"a.json": {"account": {"user": "aos-no-such-user"}}}, None, "no such user"),
            ({"a.json": {}}, {"user": "root"}, "root"),
            ({"a.json": {}}, {}, "沒有預設帳號"),
            ({"a.json": {}}, {"user": DEFAULT, "deny": [DEFAULT]}, "deny 比得到預設帳號"),
            ({"a.json": {}}, {"user": DEFAULT, "allow": ["*"], "deny": ["*"]}, "deny 比得到預設帳號"),
            ({"a.json": {}}, {"user": DEFAULT, "allow": ["a*b"]}, "結尾"),
        ]
        for insts, account, text in cases:
            r = self.run_ns(self.cfg(insts, account=account))
            self.assertEqual(r.returncode, 1, (insts, account, r.stderr))
            self.assertIn("aos-daemon: account: ", r.stderr)
            self.assertIn(text, r.stderr)

    def test_root_side_dies(self):
        self.inst(sh("sleep 0.2"), "b.json")
        p, out, _ = self.start_ns(self.cfg({"b.json": {"account": {"user": OTHER}}}))
        self.wait_for(lambda: self.results(out, "b.json") == [0])
        os.kill(self.children(p.pid)[0], signal.SIGKILL)
        self.assertEqual(p.wait(timeout=5), 1)

    def test_sigterm_root_side_follows(self):
        self.inst(sh("true"), "b.json")
        p, out, _ = self.start_ns(self.cfg({"b.json": {"account": {"user": OTHER}}}))
        self.wait_for(lambda: self.results(out, "b.json") == [0])
        root = self.children(p.pid)[0]
        p.terminate()
        self.assertEqual(p.wait(timeout=5), 0)
        self.wait_for(lambda: not alive(root))


class WithReload(NsCase):

    def test_reload_account(self):
        self.inst(sh("true"), "a.json")
        self.inst(sh(WHO % "b"), "b.json")
        account = {"user": DEFAULT, "allow": [OTHER, THIRD]}
        insts = {"a.json": {}}
        p, out, err = self.start_ns(self.cfg(insts, account=account, reload={}))
        self.wait_for(lambda: self.results(out, "a.json") == [0])
        has = lambda text: any(l.endswith(" " + text) for l in list(out))
        # 名單不准的帳號：整份不套用、stderr 一行、舊的照跑
        self.cfg(dict(insts, **{"b.json": {"account": {"user": "ftp"}}}), account=account, reload={})
        p.send_signal(signal.SIGHUP)
        self.wait_for(lambda: any("aos-daemon: reload: " in l and "名單不准" in l for l in list(err)))
        self.assertFalse(has("inst=b.json added"))
        # 准的帳號：加進來、用那個帳號跑
        self.cfg(dict(insts, **{"b.json": {"account": {"user": THIRD}}}), account=account, reload={})
        p.send_signal(signal.SIGHUP)
        self.wait_for(lambda: self.exists("who.b"))
        self.assertEqual(self.who("b")["user"], THIRD)
        # 名單改了：只警告、不套用
        self.cfg(dict(insts, **{"b.json": {"account": {"user": THIRD}}}),
                 account={"user": DEFAULT, "allow": [OTHER]}, reload={})
        p.send_signal(signal.SIGHUP)
        self.wait_for(lambda: has("reload: need restart: modules"))


@unittest.skipIf(CG_SKIP is not None, CG_SKIP or "")
class WithCgroup(NsCase):
    """跟收屍模組一起用：systemd-run 委派的 scope 裡再包 unshare。子樹交給預設帳號；
    別的帳號的子程序由 root 端放進框，留下的背景程序照樣被清掉。"""

    def start_cg(self, cfg):
        p = subprocess.Popen(SCOPE + NS + [PY, self.daemon, "--config", cfg], cwd=self.d, env=CLEAN_ENV,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
        out, err = [], []
        for stream, sink in ((p.stdout, out), (p.stderr, err)):
            threading.Thread(target=lambda s=stream, k=sink: [k.append(x.rstrip("\n")) for x in s],
                             daemon=True).start()
        self.addCleanup(self._stop, p)
        self.root = None
        self.wait_for(lambda: self._find_root(p), timeout=15)
        # 子樹歸預設帳號了，外面寫不進 cgroup.kill：在 namespace 裡（root）清
        self.addCleanup(subprocess.run, NS + ["sh", "-c", 'echo 1 > "$0/cgroup.kill"', self.root],
                        capture_output=True)
        return p, out, err

    def _find_root(self, p):
        try:
            with open("/proc/%d/cgroup" % p.pid) as f:
                rel = [l[3:].strip() for l in f if l.startswith("0::")][0]
        except FileNotFoundError:
            return False
        if os.path.basename(rel) != "daemon":
            return False
        self.root = "/sys/fs/cgroup" + os.path.dirname(rel)
        return True

    def test_reap_other_user(self):
        import aos_daemon_cgroup
        self.inst(sh("sleep 1000 & echo $! >> bg; exit 0"), "b.json")
        self.inst(sh("sleep 1000 & echo $! >> bga; exit 0"), "a.json")
        p, out, err = self.start_cg(self.config({
            "interval_ms": 100000, "modules": {"cgroup": {}, "account": {"user": DEFAULT, "allow": [OTHER]}},
            "insts": {"a.json": {}, "b.json": {"account": {"user": OTHER}}}}))
        has = lambda text: any(l.endswith(" " + text) for l in list(out))
        self.wait_for(lambda: has("inst=b.json reaped") and has("inst=a.json reaped"), timeout=8)
        for f in ("bg", "bga"):
            for pid in [int(x) for x in self.read(f).split()]:
                self.wait_for(lambda: not alive(pid))
        main_uid = int(self.uid_line(p.pid)[0])
        for inst in ("a.json", "b.json"):
            frame = os.path.join(self.root, aos_daemon_cgroup.frame_name(inst))
            self.assertEqual(os.stat(frame).st_uid, main_uid)       # 子樹交給預設帳號
        self.assertEqual(err, [])


class RootProtocol(NsCase):
    """直接對 root 端講話：開跑那一刻帳號查不到（A6：開起來之後才被刪）→ 回 error。"""

    def test_no_such_user_at_spawn(self):
        code = ("import json,os,socket,subprocess,sys\n"
                "a,b=socket.socketpair(socket.AF_UNIX,socket.SOCK_SEQPACKET)\n"
                "p=subprocess.Popen([sys.executable,%r,str(b.fileno())],pass_fds=[b.fileno()]); b.close()\n"
                "a.send(json.dumps({'default':%r,'allow':['*'],'deny':[]}).encode())\n"
                "n=os.open(os.devnull,os.O_WRONLY)\n"
                "for i,u in enumerate(['aos-no-such-user','root',%r]):\n"
                "    socket.send_fds(a,[json.dumps({'id':i,'user':u,'argv':['/bin/sh','-c','exit 3'],'cwd':'/',"
                "'env':{},'frame':None}).encode()],[n,n])\n"
                "    print(a.recv(65536).decode())\n"
                "a.close(); print(p.wait())\n"
                % (os.path.join(self.copy, "py", "bin", "aos-daemon-root"), DEFAULT, OTHER))
        r = subprocess.run(NS + [PY, "-c", code], capture_output=True, text=True, timeout=10)
        lines = r.stdout.splitlines()
        self.assertEqual(json.loads(lines[0]), {"id": 0, "error": "no such user aos-no-such-user"})
        self.assertEqual(json.loads(lines[1]), {"id": 1, "error": "not allowed: root is root"})
        self.assertEqual(json.loads(lines[2]), {"id": 2, "exit": 3})
        self.assertEqual(lines[3], "0")                            # 主程式那頭關了就退出、回 0


if __name__ == "__main__":
    unittest.main()
