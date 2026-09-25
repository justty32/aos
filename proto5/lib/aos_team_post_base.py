"""郵差共用的常數與小工具：紀錄型別、逾時與次數、崩潰測試點、時區、檔案時間、行程還在不在、動作編號、團隊識別、outbox 搬檔。"""
import hashlib
import os
from pathlib import Path
import signal
import time


RECORD_TYPE = 'aos_team_post_record'
JOB_TYPE = 'aos_team_verify_job'
CRASH_ENV = 'AOS_TEAM_POST_CRASH'          # 測試用：到了這個點就 SIGKILL 自己（模擬崩在窗口裡）
KERNEL_ENV = 'AOS_KERNEL_HOME'
WATCH_EVERY = 30                           # 秒：看停滯、期限多久一次
HEALTH_GRACE = 60                          # 秒：健康不是 ok 要持續多久才報
JOB_TIMEOUT = 600                          # 秒：驗收工作多久沒結果算壞了
JOB_TRIES = 3                              # 驗收工作跑不起來最多試幾次
CLI_TEAM = Path(__file__).resolve().parent.parent / 'cli' / 'aos-team'
CLERK_FILES = (('SESSION-LOG.md', '## 最新進度'), ('WAIT_USER.md', '## 待使用者項'))
EMPTY_LINE = '（目前無）'


def crash(point):
    if point in (os.environ.get(CRASH_ENV) or '').split(','):
        os.kill(os.getpid(), signal.SIGKILL)


def _zone(tz):
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(tz) if tz else None
    except Exception:
        return None


def _mtime(path):
    try:
        return os.stat(path).st_mtime
    except OSError:
        return None


def _pid_alive(pid):
    try:
        with open('/proc/%d/stat' % pid) as f:
            return f.read().rsplit(')', 1)[1].split()[0] != 'Z'
    except (OSError, IndexError):
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


# ------------------------------------------------------------ 共用小函式 ----

def add_effects(rec, effects, prefix=None):
    """動作加上 id（<紀錄 id>.e<第幾個>，重跑算出來一樣）與 done。"""
    prefix = prefix or rec['id']
    for e in effects or []:
        e = {k: v for k, v in e.items() if k not in ('id', 'done', 'result', 'error')}
        e.update(id='%s.e%d' % (prefix, len(rec['effects'])), done=False)
        rec['effects'].append(e)


def team_tag(root):
    """團隊的穩定識別（資料夾真路徑的雜湊前 8 碼）：kernel 上的名字都帶它，不同團隊不撞名。"""
    return hashlib.sha1(os.path.realpath(str(root)).encode()).hexdigest()[:8]


def archive(path, sub):
    """把 outbox 裡處理完的檔搬進同一格的 done/ 或 rejected/。outbox 是模型寫得到的地方：
    用資料夾的 fd 搬、不跟符號連結（done／rejected 被換成連結或檔＝先改名成 <名>.bad-<ns> 再建真的資料夾）。"""
    flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, 'O_NOFOLLOW', 0)
    box = os.open(str(path.parent), flags)
    try:
        try:
            os.mkdir(sub, dir_fd=box)
        except FileExistsError:
            pass
        try:
            dest = os.open(sub, flags, dir_fd=box)
        except OSError:
            os.rename(sub, '%s.bad-%d' % (sub, time.time_ns()), src_dir_fd=box, dst_dir_fd=box)
            os.mkdir(sub, dir_fd=box)
            dest = os.open(sub, flags, dir_fd=box)
        try:
            os.rename(path.name, path.name, src_dir_fd=box, dst_dir_fd=dest)
        except FileNotFoundError:
            pass                                  # 上一輪搬過了
        finally:
            os.close(dest)
    finally:
        os.close(box)
