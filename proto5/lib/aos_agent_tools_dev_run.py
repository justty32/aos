"""`tools test` 的跑一次：關牢探測、在假 agent 家裡起工具行程、收輸出（封頂、逾時、殺整組）。"""
import errno
import json
import os
from pathlib import Path
import shutil
import selectors
import signal
import stat
import subprocess
import time

from aos_agent_home import AgentError


TEST_TIMEOUT_MS = 30000                                  # tools test 對每一次執行的封頂
OUTPUT_CAP = 1024 * 1024        # tools test：stdout、stderr 各最多留多少位元組（留尾巴）
KILL_GRACE = 5                  # SIGKILL 之後最多再等幾秒
DRAIN_GRACE = 2                 # 主行程結束後，管子還被別人握著最多再收幾秒


# ------------------------------------------------------------------ tools test ----

def _tokens(tool):
    from aos_agent_context import tokens
    return tokens(json.dumps(tool['function'], ensure_ascii=False))


def jail_ready():
    """aos-jail 跑不跑得起來（真的開一次 bwrap 跑 true）。回 (可以?, 白話)。"""
    from aos_agent_access import JAIL
    if shutil.which('bwrap') is None:
        return False, '找不到 bwrap'
    try:
        r = subprocess.run([JAIL, '--', 'true'], stdin=subprocess.DEVNULL, capture_output=True, text=True,
                           timeout=15)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, 'aos-jail 跑不起來：%s' % e
    if r.returncode != 0:
        return False, 'aos-jail 跑不起來：%s' % (r.stderr.strip().splitlines() or ['退 %d' % r.returncode])[-1]
    return True, ''


class Result:
    def __init__(self, code=None, out='', err='', ms=0, timed_out=False, spawn_error=None, dropped=0,
                 stuck=None):
        self.code, self.out, self.err, self.ms = code, out, err, ms
        self.timed_out, self.spawn_error = timed_out, spawn_error
        self.dropped, self.stuck = dropped, stuck        # 丟掉的輸出位元組；殺不掉的行程說明


def _killpg(pid):
    try:
        os.killpg(pid, signal.SIGKILL)
    except OSError:
        pass


def pump(proc, data, limit, cap=None):
    """餵 stdin、收 stdout／stderr（每條只留最後 cap 位元組，邊讀邊丟），不靠執行緒、不會無限等：
    - 到 limit 秒整個行程群組 SIGKILL，再最多等 KILL_GRACE 秒；
    - 主行程結束後管子還被別人（另開 session 的子孫）握著，最多再收 DRAIN_GRACE 秒就關掉。
    回 (退出碼或 None, stdout bytes, stderr bytes, 逾時?, 丟了幾位元組, 殺不掉的說明或 None)。"""
    cap = OUTPUT_CAP if cap is None else cap
    sel = selectors.DefaultSelector()
    bufs = {proc.stdout: bytearray(), proc.stderr: bytearray()}
    dropped = 0
    for f in bufs:
        os.set_blocking(f.fileno(), False)
        sel.register(f, selectors.EVENT_READ)
    if data:
        os.set_blocking(proc.stdin.fileno(), False)
        sel.register(proc.stdin, selectors.EVENT_WRITE)
    else:
        proc.stdin.close()
    offset, timed_out, stop_at = 0, False, None
    deadline = time.monotonic() + limit
    try:
        while sel.get_map():
            now = time.monotonic()
            if stop_at is None and proc.poll() is not None:
                stop_at = now + DRAIN_GRACE
            if not timed_out and now >= deadline:
                timed_out = True
                _killpg(proc.pid)
                stop_at = now + KILL_GRACE
            if stop_at is not None and now >= stop_at:
                break
            ends = [now + 0.2] + ([deadline] if not timed_out else []) + ([stop_at] if stop_at else [])
            for key, _ in sel.select(max(min(ends) - now, 0)):
                f = key.fileobj
                if f is proc.stdin:
                    try:
                        offset += os.write(f.fileno(), data[offset:offset + 65536])
                    except BlockingIOError:
                        continue
                    except OSError:                       # 對方不讀了（BrokenPipe 等）
                        offset = len(data)
                    if offset >= len(data):
                        sel.unregister(f)
                        f.close()
                    continue
                try:
                    chunk = os.read(f.fileno(), 65536)
                except BlockingIOError:
                    continue
                if not chunk:
                    sel.unregister(f)
                    continue
                buf = bufs[f]
                buf += chunk
                if len(buf) > cap:
                    dropped += len(buf) - cap
                    del buf[:len(buf) - cap]
    finally:
        sel.close()
        for f in (proc.stdin, proc.stdout, proc.stderr):
            try:
                f.close()
            except OSError:
                pass
    _killpg(proc.pid)                                     # 同一群組留下的背景行程也收掉
    stuck = None
    try:
        proc.wait(KILL_GRACE)
    except subprocess.TimeoutExpired:
        stuck = '行程 %d 送了 SIGKILL 還是沒結束（可能卡在核心裡），沒等它' % proc.pid
    return proc.returncode, bytes(bufs[proc.stdout]), bytes(bufs[proc.stderr]), timed_out, dropped, stuck


class Runner:
    """拋棄式的假 agent 家：home/tools/<包>/（程式）＋home/workspace/（工作根目錄；關牢時掛成 /work/ws）。"""

    def __init__(self, home, jail):
        self.home, self.jail = home, jail
        self.ws = home / 'workspace'

    def decode(self, tool):
        """照 aos-agent 送件的方式解 _meta（中心＝家）；解不開丟 AgentError。"""
        import aos_inst
        try:
            return aos_inst.load_obj(tool['_meta'], str(self.home), env=os.environ)
        except aos_inst.InstError as e:
            raise AgentError('MetaInvalid', '_meta 解不開：%s: %s' % (e.code, e.msg))

    def argv(self, tool):
        """回 (argv, cwd, env)；關牢就照 aos-agent 的 jail_argv 包成 aos-jail。"""
        decoded = self.decode(tool)
        if self.jail:
            from aos_agent_batch import jail_argv
            access = {'mounts': {'ws': {'path': str(self.ws), 'ro': False}}, 'cwd': 'ws', 'net': False}
            return jail_argv(decoded, access), decoded['cwd'], dict(os.environ)
        env = {} if decoded['envs_clear'] else dict(os.environ)
        env.update(decoded['envs'])
        env.pop('AOS_TOOL_ROOT', None)                   # 不關牢時工作根目錄照 config.json，別吃到外面殼的設定
        env.pop('AOS_TOOL_FENCE', None)
        return decoded['argv'], decoded['cwd'], env

    def program(self, tool):
        """程式在不在、有沒有執行位（牢外看）；回白話的問題或 None。"""
        try:
            decoded = self.decode(tool)
        except AgentError as e:
            return e.msg
        if not decoded['argv']:
            return '_meta.argv 是空的'
        prog = decoded['argv'][0]
        if '/' in prog:
            full = os.path.join(decoded['cwd'], prog)
            if not os.path.isfile(full):
                return '找不到程式 %s' % prog
            if not os.access(full, os.X_OK):
                return '程式 %s 沒有執行位（chmod +x）' % prog
            return None
        if self.jail:
            return None                                   # 牢裡只找 /usr/local/bin:/usr/bin:/bin，跑了才知道
        return None if shutil.which(prog) else '在 PATH 上找不到程式 %s' % prog

    def run(self, tool, stdin):
        try:
            argv, cwd, env = self.argv(tool)
        except AgentError as e:
            return Result(spawn_error=e.msg)
        limit = tool.get('_timeout_ms', 60000) or TEST_TIMEOUT_MS
        limit = min(limit, TEST_TIMEOUT_MS) / 1000
        start = time.monotonic()
        try:
            proc = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, start_new_session=True)
        except OSError as e:
            return Result(spawn_error='跑不起來：%s' % (e.strerror or e))
        code, out, err, timed_out, dropped, stuck = pump(proc, stdin.encode('utf-8'), limit)
        ms = int((time.monotonic() - start) * 1000)
        return Result(code, out.decode('utf-8', 'replace'), err.decode('utf-8', 'replace'), ms, timed_out,
                      dropped=dropped, stuck=stuck)

    def write_file(self, rel, content):
        """固定案例的 files 寫進 workspace：從 workspace 的目錄 fd 一層層開，每層都不跟符號連結（O_NOFOLLOW），
        最後的檔也 O_NOFOLLOW、有硬連結（nlink > 1）不寫——前面的工具在 workspace 放的連結帶不出去。"""
        parts = Path(rel).parts
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, 'O_CLOEXEC', 0)
        fd = os.open(self.ws, flags)
        try:
            for part in parts[:-1]:
                try:
                    nxt = os.open(part, flags, dir_fd=fd)
                except FileNotFoundError:
                    os.mkdir(part, 0o755, dir_fd=fd)
                    nxt = os.open(part, flags, dir_fd=fd)
                os.close(fd)
                fd = nxt
            out = os.open(parts[-1], os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | getattr(os, 'O_CLOEXEC', 0),
                          0o644, dir_fd=fd)
            try:
                st = os.fstat(out)
                if not stat.S_ISREG(st.st_mode) or st.st_nlink > 1:
                    raise OSError(errno.EPERM, '%s 不是一般檔或有硬連結' % rel)
                os.ftruncate(out, 0)
                os.write(out, content.encode('utf-8'))
            finally:
                os.close(out)
        finally:
            os.close(fd)
