# 驗證 daemon 認 limits.user 的 sub:N（免 root 換成 subuid，線 subuid-1119）：設定驗證、helper 找不到與失敗、小格 ACL、與 fake helper 的握手；有真的 newuidmap 才跑真換身分。
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pathlib import Path
import shutil
import stat
import struct
import subprocess
import unittest

from support import ENV, PROTO, Fixture, dc, read, until, write

REAL = shutil.which('newuidmap') and shutil.which('newgidmap')


def sub_start(kind):
    """First /etc/sub{uid,gid} range start of this user, or None."""
    name = subprocess.check_output(['id', '-un'], text=True).strip()
    try:
        for line in Path('/etc/sub' + kind).read_text().splitlines():
            f = line.split(':')
            if len(f) == 3 and f[0] in (name, str(os.getuid())):
                return int(f[1])
    except OSError:
        pass
    return None


def acl_users(path, name):
    """Named-user entries (id, perm) of a POSIX ACL xattr."""
    raw = os.getxattr(path, name)
    out = []
    for i in range(4, len(raw), 8):
        tag, perm, ident = struct.unpack('<HHI', raw[i:i + 8])
        if tag == 0x02:
            out.append((ident, perm))
    return out


def blocked_ancestor(path):
    """First ancestor of path that others cannot search, or None."""
    p = Path('/')
    for part in Path(path).parts[1:]:
        p = p / part
        if not os.stat(p).st_mode & stat.S_IXOTH:
            return str(p)
    return None


class SubUid(unittest.TestCase):
    def fixture(self, name, **cfg):
        f = Fixture('subuid-' + name)
        self.addCleanup(f.close)
        write(f.config, dict(read(f.config), **cfg))
        return f

    def start(self, f, path, extra_env=None):
        f.log = open(f.root / 'daemon.log', 'a')
        f.err = open(f.root / 'daemon.err', 'a')
        env = dict(ENV, AOS_STACK=str(f.stack), PATH=path, **(extra_env or {}))
        f.proc = subprocess.Popen(['aos-daemon', '--enable-logs', str(f.config)], cwd=f.root,
                                  env=env, stdout=f.log, stderr=f.err)
        until(lambda: (lambda d: isinstance(d, dict) and d.get('pid') == f.proc.pid)(
            read(f.stack / 'procs_state.json', {})))
        until(lambda: read(f.stack / 'state_flux.json'))
        return f

    def script(self, f, name, body):
        p = f.root / (name + '.sh')
        p.write_text('#!/bin/sh\n# Run the subuid fixture body.\n' + body + '\n')
        p.chmod(0o755)
        return str(p)

    def fake_helpers(self, f, fail=False):
        """newuidmap/newgidmap stand-ins: log argv, map ns N/G to our own uid/gid (setgroups ends up denied)."""
        d = f.root / 'fake'
        d.mkdir(exist_ok=True)
        log = f.root / 'helpers.log'
        uid = ('echo "newuidmap: write to uid_map failed: Operation not permitted" >&2; exit 1' if fail else
               'printf "%s %s 1\\n" "$5" "$3" > /proc/$1/uid_map')
        gid = 'echo deny > /proc/$1/setgroups && printf "%s %s 1\\n" "$5" "$3" > /proc/$1/gid_map'
        for prog, body in (('newuidmap', uid), ('newgidmap', gid)):
            p = d / prog
            p.write_text('#!/bin/sh\n# Fake %s for the subuid tests.\necho "%s $*" >> %s\n%s\n' % (prog, prog, log, body))
            p.chmod(0o755)
        return d, log

    def add(self, f, specs):
        result = dc.ask(str(f.stack), {'procs_added': specs})
        self.assertTrue(result['applied'], result)

    def stopped(self, f, name='job'):
        return until(lambda: (r if (r := f.rows().get(name)) and r['phase'] == 'stopped' else None), timeout=15)

    def reachable(self, f, ready):
        """Wait until ready() or the row stops; a stop must be 04 item 1 (a folder the subuid cannot enter), then skip."""
        got = until(lambda: 'ready' if ready() else (r if (r := f.row()) and r['phase'] == 'stopped' else None), timeout=15)
        if got == 'ready':
            return
        if 'cannot reach ' not in (got.get('reason') or ''):   # 別的起不來是真的錯，照實報、不 skip
            self.fail('the proc stopped instead of getting ready: %s' % got.get('reason'))
        blocked = blocked_ancestor(f.root) or blocked_ancestor(PROTO / 'bin')
        if blocked:   # 有 ACL 時權限位不準，只在看得出來時對路徑
            self.assertIn('cannot reach ' + blocked, got['reason'])
        self.skipTest('the subuid cannot reach the fixture: %s' % got['reason'])

    def test_bad_config(self):
        cases = [
            ({'limits': {'user': 'sub:0'}}, 'limits.user "sub:0": sub:N needs N from 1 to 60000 (no leading zero)'),
            ({'limits': {'user': 'sub:05'}}, 'limits.user "sub:05": sub:N needs N from 1 to 60000 (no leading zero)'),
            ({'limits': {'user': 'sub:60001'}}, 'limits.user "sub:60001": sub:N needs N from 1 to 60000 (no leading zero)'),
            ({'group': 60000}, 'group must be an integer from 60001 to 65536'),
            ({'group': '60001'}, 'group must be an integer from 60001 to 65536'),
        ]
        for i, (cfg, message) in enumerate(cases):
            with self.subTest(cfg=cfg):
                f = self.fixture('bad-%d' % i, **cfg)
                r = subprocess.run(['aos-daemon', str(f.config)], cwd=f.root,
                                   env=dict(ENV, AOS_STACK=str(f.stack)), capture_output=True, text=True, timeout=10)
                self.assertEqual(r.returncode, 1)
                self.assertEqual(r.stderr.strip(), 'aos-daemon: error: CfgBad ' + message)

    def test_group_on_state(self):
        f = self.start(self.fixture('group', group=60005), ENV['PATH'])
        self.assertEqual(read(f.stack / 'state.json')['group'], 60005)

    def test_helpers_missing(self):
        if sub_start('uid') is None or sub_start('gid') is None:
            self.skipTest('no /etc/subuid or /etc/subgid line for this user')
        f = self.fixture('missing')
        empty = f.root / 'empty'
        empty.mkdir(exist_ok=True)
        self.start(f, str(PROTO / 'bin') + ':' + str(empty))
        self.add(f, {'job': {'exec': '/bin/true', 'limits': {'user': 'sub:5'}}})
        self.assertIn('LimitBad user sub:5: newuidmap not found on PATH (install the uidmap package)', self.stopped(f)['reason'])
        self.assertIsNone(f.proc.poll())

    def test_helper_fails(self):
        if sub_start('uid') is None or sub_start('gid') is None:
            self.skipTest('no /etc/subuid or /etc/subgid line for this user')
        f = self.fixture('fail')
        fake, log = self.fake_helpers(f, fail=True)
        self.start(f, str(fake) + ':' + ENV['PATH'])
        body = self.script(f, 'never', 'touch "$AOS_STACK/ran"')
        self.add(f, {'job': {'exec': body, 'limits': {'user': 'sub:5'}}})
        self.assertIn('LimitBad user sub:5: %s/newuidmap exited 1' % fake, self.stopped(f)['reason'])
        err = (f.cell / 'stderr.txt').read_text()
        self.assertIn('newuidmap: write to uid_map failed', err)
        self.assertFalse((f.cell / 'ran').exists())

    def test_handshake_and_acl_with_fake_helpers(self):
        ustart, gstart = sub_start('uid'), sub_start('gid')
        if ustart is None or gstart is None:
            self.skipTest('no /etc/subuid or /etc/subgid line for this user')
        f = self.fixture('fake', group=60002)
        fake, log = self.fake_helpers(f)
        self.start(f, str(fake) + ':' + ENV['PATH'])
        body = self.script(f, 'never', 'touch "$AOS_STACK/ran"')
        self.add(f, {'job': {'exec': body, 'limits': {'user': 'sub:5'}}})
        row = self.stopped(f)
        # fake newgidmap leaves setgroups denied, so the switch must stop there (fail closed: supplementary groups stay otherwise)
        self.assertIn('LimitBad user sub:5: setgroups: Operation not permitted', row['reason'])
        self.assertEqual(row['limits'], {'user': 'sub:5'})
        self.assertFalse((f.cell / 'ran').exists())
        lines = log.read_text().splitlines()
        self.assertEqual(len(lines), 2, lines)
        uid_args = lines[0].split()
        gid_args = lines[1].split()
        self.assertEqual(uid_args[0], 'newuidmap')
        self.assertEqual(uid_args[2:], ['0', str(os.getuid()), '1', '5', str(ustart + 4), '1'])
        self.assertEqual(gid_args[0], 'newgidmap')
        self.assertEqual(gid_args[2:], ['0', str(os.getgid()), '1', '60002', str(gstart + 60001), '1'])
        self.assertEqual(uid_args[1], gid_args[1])
        self.assertEqual(stat.S_IMODE(os.stat(f.cell).st_mode) & 0o707, 0o700)   # 群組那三位顯示的是 ACL 的 mask
        self.assertEqual(acl_users(f.cell, 'system.posix_acl_access'), [(ustart + 4, 7)])
        self.assertEqual(sorted(acl_users(f.cell, 'system.posix_acl_default')), sorted([(os.getuid(), 7), (ustart + 4, 7)]))
        self.assertIsNone(f.proc.poll())

    @unittest.skipUnless(REAL, 'needs newuidmap/newgidmap (apt install uidmap)')
    def test_real_switch(self):
        ustart, gstart = sub_start('uid'), sub_start('gid')
        if ustart is None or gstart is None:
            self.skipTest('no /etc/subuid or /etc/subgid line for this user')
        f = self.fixture('real')
        self.start(f, ENV['PATH'], {'SUBUID_PROBE': 'secret'})
        body = self.script(f, 'who', '\n'.join([
            'id -u > "$AOS_STACK/uid"',
            'printf "%s\\n" "$HOME" "${SUBUID_PROBE-unset}" "${GIT_CONFIG_VALUE_0-unset}" > "$AOS_STACK/env"',
            'echo hi > "$AOS_STACK/out"',
            'touch "$AOS_STACK/ready"',
            'exec sleep 30']))
        self.add(f, {'job': {'exec': body, 'ws': str(f.root), 'limits': {'user': 'sub:5', 'procs': 5}}})
        self.reachable(f, lambda: (f.cell / 'ready').exists())
        row = f.row()
        status = Path('/proc/%s/status' % row['pid']).read_text()
        uid_line = [l for l in status.splitlines() if l.startswith('Uid:')][0].split()
        self.assertEqual(uid_line[1:], [str(ustart + 4)] * 4)
        out = os.stat(f.cell / 'out')
        self.assertEqual((out.st_uid, out.st_gid), (ustart + 4, gstart + 60000))
        self.assertEqual((f.cell / 'uid').read_text().strip(), '5')
        self.assertEqual((f.cell / 'env').read_text().split('\n')[:3], ['/nonexistent', 'unset', str(f.root)])
        with open(f.cell / 'out', 'a') as w:   # 預設 ACL 把使用者加進去：使用者照改得動
            w.write('from the user\n')
        f.ctl('rm', 'job')
        until(lambda: 'job' not in f.rows(), timeout=15)
        self.assertFalse(Path('/proc/%s' % row['pid']).exists())

    @unittest.skipUnless(REAL, 'needs newuidmap/newgidmap (apt install uidmap)')
    def test_real_procs_counts_the_subuid(self):
        # procs 低於使用者自己的行程數也起得來（開 ns 之後才設 RLIMIT_NPROC），而且數的是這個 subuid：身體自己＋2 個子行程，第 3 個 fork 失敗
        ustart = sub_start('uid')
        if ustart is None or sub_start('gid') is None:
            self.skipTest('no /etc/subuid or /etc/subgid line for this user')
        mine = sum(1 for d in Path('/proc').iterdir() if d.name.isdigit() and self.owner(d) == os.getuid())
        self.assertGreater(mine, 3)
        f = self.fixture('real-procs')
        self.start(f, ENV['PATH'])
        # dash 的 fork 失敗會讓整支 sh 退出，所以改用 python 數（單執行緒：只算一個）
        body = self.script(f, 'forks', "exec python3 -c '%s'" % '\n'.join([
            'import os, signal, time',
            'signal.signal(signal.SIGTERM, lambda *a: os.killpg(0, signal.SIGKILL))',   # rm 只 SIGTERM 主行程（沒 cgroup 不收孤兒），自己帶走子行程
            'kids, err = [], ""',
            'for i in range(4):',
            '    try:',
            '        p = os.fork()',
            '    except OSError as e:',
            '        err = e.strerror',
            '        break',
            '    if p == 0:',
            '        time.sleep(30)',
            '        os._exit(0)',
            '    kids.append(p)',
            'open(os.environ["AOS_STACK"] + "/forks", "w").write("%d %s" % (len(kids), err))',
            'open(os.environ["AOS_STACK"] + "/ready", "w").close()',
            'time.sleep(30)']))
        self.add(f, {'job': {'exec': body, 'limits': {'user': 'sub:7', 'procs': 3}}})
        self.reachable(f, lambda: (f.cell / 'ready').exists())
        self.assertEqual((f.cell / 'forks').read_text(), '2 Resource temporarily unavailable')
        sid = str(f.row()['pid'])   # 只數這支 proc 的 session（daemon 替它 setsid）
        subs = [d for d in Path('/proc').iterdir() if d.name.isdigit() and self.owner(d) == ustart + 6 and self.session(d) == sid]
        self.assertEqual(len(subs), 3, [d.name for d in subs])
        f.ctl('rm', 'job')
        until(lambda: 'job' not in f.rows(), timeout=15)
        self.assertFalse([d for d in subs if d.exists()])

    @unittest.skipUnless(REAL, 'needs newuidmap/newgidmap (apt install uidmap)')
    def test_real_cannot_reach(self):
        # 04 第 1 條：工作區的祖先 subuid 走不進去＝點名那一層（不靠家目錄的權限：自己在 fixture 裡做一層 700）
        f = self.fixture('real-reach')
        self.start(f, ENV['PATH'])
        locked = f.root / 'locked'
        (locked / 'inner').mkdir(parents=True, exist_ok=True)
        locked.chmod(0o700)
        body = self.script(f, 'never', 'touch "$AOS_STACK/ran"')
        self.add(f, {'job': {'exec': body, 'ws': str(locked / 'inner'), 'limits': {'user': 'sub:8'}}})
        row = self.stopped(f)
        if 'cannot reach ' + str(locked) + ':' not in (row.get('reason') or ''):
            if 'cannot reach' in (row.get('reason') or ''):   # fixture 本身就走不到（家目錄沒開門）
                self.skipTest('the subuid cannot reach the fixture: %s' % row['reason'])
        self.assertIn('LimitBad user sub:8: cannot reach %s: Permission denied' % locked, row['reason'])
        self.assertFalse((f.cell / 'ran').exists())

    @staticmethod
    def session(d):
        try:
            return (d / 'stat').read_text().rsplit(')', 1)[1].split()[3]
        except (OSError, IndexError):
            return None

    @staticmethod
    def owner(d):
        try:
            return os.stat(d).st_uid
        except OSError:
            return None

    @unittest.skipUnless(REAL, 'needs newuidmap/newgidmap (apt install uidmap)')
    def test_real_cpu_hit(self):
        f = self.fixture('real-cpu')
        self.start(f, ENV['PATH'])
        body = self.script(f, 'cpu', 'while :; do :; done')
        self.add(f, {'job': {'exec': body, 'limits': {'user': 'sub:6', 'cpu_s': 1}}})
        row = self.stopped(f)
        if 'cannot reach' in (row.get('reason') or ''):
            self.skipTest('the subuid cannot reach the fixture: %s' % row['reason'])
        self.assertEqual((row['signal'], row['code'], row['limit_hit']), (24, 152, 'cpu_s'))


if __name__ == '__main__':
    unittest.main()
