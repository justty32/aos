"""aos-jail：照參數把一支程式關進 bwrap 跑（spec/aos-exec/aos-jail.md）。

純標準庫。不讀 access.json、不解指示詞，只照命令列做：組好 bwrap 的 argv、清環境、
最後 os.execvp（行程就是 bwrap，kernel 逾時砍得到）。build_argv 是純函式，方便測。
"""
import os
import re
import shutil
import sys

USAGE = ('aos-jail [--mount NAME=PATH]… [--mount-ro NAME=PATH]… [--chdir NAME] [--net on|off] '
         '[--setenv K=V]… -- PROG [ARGS…]')
NO_BWRAP = ('aos-jail: 找不到 bwrap（bubblewrap）；Arch/Manjaro: sudo pacman -S bubblewrap，'
            'Debian/Ubuntu: sudo apt install bubblewrap')
NAME = re.compile(r'[a-z0-9_-]+\Z')
BASE_PATH = '/usr/local/bin:/usr/bin:/bin'
HOST_ENV = ('LANG', 'LC_ALL', 'TZ', 'TERM')           # 主機有才帶
HOST_DIRS = ('/bin', '/lib', '/lib64', '/sbin')       # 連結就 --symlink、資料夾就 --ro-bind-try
ETC = ('ld.so.cache', 'passwd', 'group', 'nsswitch.conf', 'localtime', 'hosts')
ETC_NET = ('resolv.conf', 'ssl', 'ca-certificates')
SECRET_WORDS = ('KEY', 'TOKEN', 'SECRET', 'PASSWORD', 'CREDENTIAL')
TOOL_DIR = '/opt/tool'


class UsageError(Exception):
    pass


def secret_name(name):
    """--setenv 一律丟掉的名字：AOS_*、含金鑰字眼、SSH_AUTH_SOCK（不分大小寫）。"""
    upper = name.upper()
    return (upper.startswith('AOS_') or upper == 'SSH_AUTH_SOCK'
            or any(word in upper for word in SECRET_WORDS))


def _pair(flag, value):
    key, eq, rest = value.partition('=')
    if not eq or not key:
        raise UsageError('%s 要寫成 名字=值：%r' % (flag, value))
    return key, rest


def parse_args(argv):
    """命令列 → opts dict；錯＝UsageError。"""
    opts = {'mounts': [], 'chdir': None, 'net': False, 'setenv': [], 'prog': None, 'args': []}
    names = set()
    i = 0
    while i < len(argv):
        flag = argv[i]
        if flag == '--':
            rest = argv[i + 1:]
            if not rest or not rest[0]:
                raise UsageError('-- 後面要有要跑的程式')
            opts['prog'], opts['args'] = rest[0], rest[1:]
            break
        if flag not in ('--mount', '--mount-ro', '--chdir', '--net', '--setenv'):
            raise UsageError('不認得的參數 %r（程式要放在 -- 後面）' % flag)
        if i + 1 >= len(argv):
            raise UsageError('%s 後面少了值' % flag)
        value = argv[i + 1]
        i += 2
        if flag in ('--mount', '--mount-ro'):
            name, path = _pair(flag, value)
            if not NAME.match(name):
                raise UsageError('%s 的名字 %r 只能用小寫英數、底線、連字號' % (flag, name))
            if name in names:
                raise UsageError('名字 %s 掛了兩次' % name)
            if not os.path.isabs(path):
                raise UsageError('%s %s 的路徑要是絕對路徑' % (flag, name))
            names.add(name)
            opts['mounts'].append((name, path, flag == '--mount-ro'))
        elif flag == '--chdir':
            opts['chdir'] = value
        elif flag == '--net':
            if value not in ('on', 'off'):
                raise UsageError('--net 只收 on 或 off：%r' % value)
            opts['net'] = value == 'on'
        else:
            opts['setenv'].append(_pair(flag, value))
    if opts['prog'] is None:
        raise UsageError('少了 -- PROG')
    if opts['chdir'] is not None and opts['chdir'] not in names:
        raise UsageError('--chdir %s 不是掛上的名字（有：%s）' % (opts['chdir'], '、'.join(sorted(names)) or '沒有'))
    if '/' in opts['prog'] and not os.path.isabs(opts['prog']):
        raise UsageError('PROG 含 / 就要是絕對路徑：%s' % opts['prog'])
    return opts


def build_argv(opts, environ=None, bwrap='bwrap'):
    """opts（parse_args 的結果）→ (bwrap argv, 丟掉的環境變數名)。不碰檔案系統以外的東西。"""
    environ = os.environ if environ is None else environ
    argv = [bwrap, '--unshare-all']
    if opts['net']:
        argv.append('--share-net')
    argv += ['--die-with-parent', '--new-session', '--ro-bind', '/usr', '/usr']
    for d in HOST_DIRS:
        if os.path.islink(d):
            argv += ['--symlink', os.readlink(d), d]
        elif os.path.isdir(d):
            argv += ['--ro-bind-try', d, d]
    argv += ['--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp']
    for name in ETC + (ETC_NET if opts['net'] else ()):
        argv += ['--ro-bind-try', '/etc/' + name, '/etc/' + name]
    prog = opts['prog']
    if '/' in prog:
        real = os.path.realpath(prog)
        argv += ['--ro-bind', os.path.dirname(real), TOOL_DIR]
        prog = TOOL_DIR + '/' + os.path.basename(real)
    argv += ['--dir', '/work']
    for name, path, ro in opts['mounts']:
        argv += ['--ro-bind' if ro else '--bind', path, '/work/' + name]
    start = '/work/' + opts['chdir'] if opts['chdir'] else '/work'
    argv += ['--chdir', start, '--clearenv']
    env = {'PATH': BASE_PATH, 'HOME': '/tmp'}
    env.update((k, environ[k]) for k in HOST_ENV if k in environ)
    dropped = []
    for key, value in opts['setenv']:
        if secret_name(key):
            dropped.append(key)
        else:
            env[key] = value
    env['AOS_TOOL_ROOT'] = start
    for key, value in env.items():
        argv += ['--setenv', key, value]
    return argv + ['--', prog] + list(opts['args']), dropped


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        opts = parse_args(argv)
    except UsageError as exc:
        sys.stderr.write('aos-jail: 用法錯：%s\n用法：%s\n' % (exc, USAGE))
        return 2
    bwrap = shutil.which('bwrap')
    if bwrap is None:
        sys.stderr.write(NO_BWRAP + '\n')
        return 126
    cmd, dropped = build_argv(opts, bwrap=bwrap)
    for key in dropped:
        sys.stderr.write('aos-jail: 丟掉環境變數 %s（名字像金鑰或 AOS_*，不給牢裡的工具）\n' % key)
    sys.stderr.flush()
    try:
        os.execv(bwrap, cmd)
    except OSError as exc:
        sys.stderr.write('aos-jail: 跑不起 bwrap：%s\n' % exc)
        return 126


if __name__ == '__main__':
    sys.exit(main())
